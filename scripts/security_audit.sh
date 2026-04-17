#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-${REPO_ROOT}/artifacts/security/graypaper-audit}"
OUTPUT_DIR="${OUTPUT_DIR:-${ARTIFACT_ROOT}/output}"
SUMMARY_FILE="${OUTPUT_DIR}/summary.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTEST_ARGS="${PYTEST_ARGS:-}"

PIP_AUDIT_VERSION="${PIP_AUDIT_VERSION:-2.7.3}"
BANDIT_VERSION="${BANDIT_VERSION:-1.7.9}"
SEMGREP_VERSION="${SEMGREP_VERSION:-1.78.0}"
SYFT_VERSION="${SYFT_VERSION:-1.20.0}"
GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.18.4}"

INSTALL_PYTHON_TOOLS=1
RUN_PYTEST_MATRIX=1
STRICT_FINDINGS="${STRICT_FINDINGS:-0}"

declare -a FAILURES=()

usage() {
  cat <<'EOF'
Usage: scripts/security_audit.sh [--install-python-tools] [--skip-python-tools-install] [--skip-pytest-matrix]

Environment:
  PYTHON_BIN            Python executable to use. Default: python3
  PYTEST_ARGS           Extra arguments passed to each pytest invocation.
  STRICT_FINDINGS       When set to 1, exit non-zero if any scan or test step fails.
  PIP_AUDIT_VERSION     pip-audit version pin.
  BANDIT_VERSION        bandit version pin.
  SEMGREP_VERSION       semgrep version pin.
  SYFT_VERSION          Recorded syft version pin.
  GITLEAKS_VERSION      Recorded gitleaks version pin.
EOF
}

while (($#)); do
  case "$1" in
    --install-python-tools)
      INSTALL_PYTHON_TOOLS=1
      ;;
    --skip-python-tools-install)
      INSTALL_PYTHON_TOOLS=0
      ;;
    --skip-pytest-matrix)
      RUN_PYTEST_MATRIX=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

mkdir -p "${OUTPUT_DIR}"

cat > "${OUTPUT_DIR}/tool-versions.json" <<EOF
{
  "pip_audit": "${PIP_AUDIT_VERSION}",
  "bandit": "${BANDIT_VERSION}",
  "semgrep": "${SEMGREP_VERSION}",
  "syft": "${SYFT_VERSION}",
  "gitleaks": "${GITLEAKS_VERSION}"
}
EOF

cat > "${SUMMARY_FILE}" <<EOF
# Gray Paper Security Audit Summary

- Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Artifact root: ${ARTIFACT_ROOT}
- Authoritative references:
  - https://graypaper.com/graypaper.pdf
  - https://graypaper.com/resources/
  - https://wiki.polkadot.com/learn/learn-jam-chain/
  - https://github.com/w3f/jamtestvectors/

## Step Results
EOF

append_summary() {
  printf -- "- \`%s\`: %s\n" "$1" "$2" >> "${SUMMARY_FILE}"
}

run_step() {
  local name="$1"
  shift
  local logfile="${OUTPUT_DIR}/${name}.log"

  echo "==> ${name}"
  if "$@" > "${logfile}" 2>&1; then
    append_summary "${name}" "ok"
    return 0
  fi

  local exit_code=$?
  FAILURES+=("${name}:${exit_code}")
  append_summary "${name}" "exit ${exit_code} (see $(basename "${logfile}"))"
  return "${exit_code}"
}

mark_skipped() {
  local name="$1"
  local reason="$2"

  printf 'skipped: %s\n' "${reason}" > "${OUTPUT_DIR}/${name}.skip.txt"
  append_summary "${name}" "skipped (${reason})"
}

if [[ "${INSTALL_PYTHON_TOOLS}" == "1" ]]; then
  run_step python_tools_install \
    "${PYTHON_BIN}" -m pip install \
    "pip-audit==${PIP_AUDIT_VERSION}" \
    "bandit==${BANDIT_VERSION}" \
    "semgrep==${SEMGREP_VERSION}" || true
else
  mark_skipped python_tools_install "requested by flag"
fi

run_step pip_audit \
  "${PYTHON_BIN}" -m pip_audit -r "${REPO_ROOT}/requirements.txt" -f json -o "${OUTPUT_DIR}/pip-audit.json" || true

run_step bandit \
  "${PYTHON_BIN}" -m bandit -r "${REPO_ROOT}/pyjamaz" "${REPO_ROOT}/scripts" -x "${REPO_ROOT}/test" -f json -o "${OUTPUT_DIR}/bandit.json" || true

run_step semgrep \
  "${PYTHON_BIN}" -m semgrep scan \
  --config "${REPO_ROOT}/.semgrep/jam-security.yml" \
  --json \
  --output "${OUTPUT_DIR}/semgrep.json" \
  "${REPO_ROOT}/pyjamaz" "${REPO_ROOT}/scripts" "${REPO_ROOT}/.github" || true

if command -v syft >/dev/null 2>&1; then
  run_step syft \
    bash -lc "cd '${REPO_ROOT}' && syft dir:. -o cyclonedx-json > '${OUTPUT_DIR}/sbom.cyclonedx.json'" || true
else
  mark_skipped syft "binary not found in PATH"
fi

if command -v gitleaks >/dev/null 2>&1; then
  run_step gitleaks \
    gitleaks dir "${REPO_ROOT}" --no-banner --report-format json --report-path "${OUTPUT_DIR}/gitleaks.json" || true
else
  mark_skipped gitleaks "binary not found in PATH"
fi

if [[ "${RUN_PYTEST_MATRIX}" == "1" ]]; then
  for interpreter in NUMBA_JIT CPYTHON GRAYPAPER; do
    run_step "pytest_${interpreter}" \
      bash -lc "cd '${REPO_ROOT}' && PVM_INTERPRETER='${interpreter}' '${PYTHON_BIN}' -m pytest ${PYTEST_ARGS} --junitxml='${OUTPUT_DIR}/pytest-${interpreter}.xml'" || true
  done
else
  mark_skipped pytest_matrix "requested by flag"
fi

cat >> "${SUMMARY_FILE}" <<EOF

## Audit Backlog
- Findings ledger: [findings.md](../findings.md)
- Threat model: [threat-model.md](../threat-model.md)
- Spec coverage matrix: [spec-coverage-matrix.md](../spec-coverage-matrix.md)
- Release gate: [release-gate.md](../release-gate.md)
EOF

if [[ "${STRICT_FINDINGS}" == "1" && "${#FAILURES[@]}" -gt 0 ]]; then
  echo "Security audit recorded failing steps: ${FAILURES[*]}" >&2
  exit 1
fi

exit 0
