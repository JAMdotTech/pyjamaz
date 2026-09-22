#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"
SCRIPT_DIR="$(pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"
BUILDER="${BUILDER:-$SCRIPT_DIR/corevm-builder}"
TRACE="${TRACE:-$SCRIPT_DIR/doom-clean.bin}"
STAGE="${STAGE:-current}"
CHANGE="${CHANGE:-current worktree}"

if [[ ! -x "$BUILDER" ]]; then
  echo "corevm-builder not found or not executable: $BUILDER" >&2
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "python not found or not executable: $PYTHON" >&2
  exit 1
fi

if [[ ! -f "$TRACE" ]]; then
  echo "trace not found: $TRACE" >&2
  exit 1
fi

exec "$PYTHON" bench_refine_corevm.py \
  --repo "$REPO_DIR" \
  --trace "$TRACE" \
  --python "$PYTHON" \
  --stage "$STAGE" \
  --change "$CHANGE" \
  --warmups 1 \
  --runs 1 \
  --max-refines-per-run 1 \
  --no-profile \
  --builder "$BUILDER" \
  --service c36351c2 \
  "$@"
