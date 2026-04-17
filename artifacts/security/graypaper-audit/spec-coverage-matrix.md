# Spec Coverage Matrix

This matrix maps security-relevant Gray Paper areas and companion resources to concrete code, current coverage, and logged gaps.

| Area | Primary modules | Current coverage | External vectors | Gap / owner |
| --- | --- | --- | --- | --- |
| Networking and JAMNPS transport | `pyjamaz/transport/protocol_jamnp_s.py`, `pyjamaz/transport/cert.py` | New parser regression tests in `test/test_transport_protocol_jamnp_s.py` | None wired today | Invalid-cert, ALPN, replay, and peer-identity tests are still missing. Owner: core maintainers |
| JSON-RPC boundary and subscriptions | `pyjamaz/rpc/ws_server.py`, `pyjamaz/rpc/rpc.py`, `pyjamaz/rpc/ws_server_subscriptions.py` | New boundary tests in `test/test_rpc_security.py` | None wired today | Read/write auth split, rate-limit coverage, and subscription abuse tests remain open. Owner: core maintainers |
| Block, extrinsic, and codec decoding | `pyjamaz/models/block.py`, `pyjamaz/models/common.py`, `pyjamaz/models/state.py` | `test/test_codec.py`, `test/test_serialization.py` | W3F codec fixtures under `test/fixtures/codec/w3f` | Fuzzing malformed lengths and oversized blobs remains partial. Owner: security audit backlog |
| SAFROLE, assurances, disputes, and report validation | `pyjamaz/validation.py`, `pyjamaz/runtime/pipelines/*`, `pyjamaz/state/components.py` | `test/test_safrole.py`, `test/test_assurances.py`, `test/test_disputes.py`, `test/test_reports.py` | JDT and W3F fixtures already present in `test/fixtures` | Manual review of rollback and dispute timing still required. Owner: core maintainers |
| Refine, Accumulate, and hostcalls | `pyjamaz/hostcalls/*`, `pyjamaz/runtime/extrinsics.py` | `test/test_hostcalls_general.py`, `test/test_hostcalls_accumulate.py`, `test/test_refine.py`, `test/test_accumulate.py` | Local fixtures under `test/fixtures/hostcalls` | Additional adversarial inputs for authorization and memory bounds are still needed. Owner: security audit backlog |
| PVM interpreters and parity | `pyjamaz/pvm/*` | `test/test_pvm_instructions.py`, pytest matrix in `scripts/security_audit.sh` | None beyond local fixtures | Dedicated cross-interpreter differential corpus is still missing. Treat unexplained mismatches as High severity. Owner: core maintainers |
| Storage and file-backed data paths | `pyjamaz/storage.py`, `pyjamaz/state/storage.py`, `pyjamaz/d3l.py` | `test/test_storage_engine.py`, `test/test_storage_value.py`, `test/test_state_trie_root.py` | None | File-permission, retention, and secret hygiene review is manual today. Owner: core maintainers |
| CLI, Docker, and release workflows | `pyjamaz/cli.py`, `Dockerfile*`, `docker-compose*.yml`, `.github/workflows/*` | Security audit harness and workflow | N/A | Release hardening and operator guidance are largely document-driven today. Owner: maintainers |

## Notable Existing Oracles

- The repo already consumes W3F JAM codec fixtures through `test/test_codec.py`.
- The audit harness runs the existing suite in `NUMBA_JIT`, `CPYTHON`, and `GRAYPAPER` modes to surface interpreter drift.
- `.semgrep/jam-security.yml` adds project-specific checks for insecure QUIC verification, unencrypted key output, unauthenticated RPC surfaces, and direct JAM decoding from network input.
