# Release Gate

## Pass Criteria

- The security audit harness runs and publishes artifacts for dependency, secret, SBOM, static-analysis, and pytest-matrix checks.
- Every security-relevant Gray Paper area is mapped in `spec-coverage-matrix.md` and marked as covered, manually reviewed, or logged as an explicit gap.
- Every confirmed finding has severity, repro notes, remediation guidance, and required regression coverage recorded in `findings.md`.
- No open `Critical` or `High` findings remain without explicit risk sign-off.

## Current Status

- Overall status: `Blocked`
- Blocking findings:
  - `F-001` QUIC transport lacks peer verification and identity binding.
  - `F-002` WebSocket RPC exposes mutating methods without authentication.
- Non-blocking but tracked:
  - `F-004` unencrypted key-at-rest handling for generated certificates.
  - `F-005` local workspace key hygiene.
  - Remaining `0.8.0` spec-drift review for accumulation and adjacent `PyjamazApp.state_transition` sections.
- Remediated in this branch:
  - `F-003` JAMNPS frame parser desynchronization on fragmented or concatenated frames.
  - `F-006` dispute-stage assurance pruning for non-positive verdicts.

## Evidence Bundle

- Local harness: `scripts/security_audit.sh`
- CI job: `.github/workflows/security-audit.yml`
- Generated outputs: `artifacts/security/graypaper-audit/output/`
