# Findings

Severity rubric:

- `Critical`: consensus safety failure, key compromise, or remote code execution.
- `High`: authentication bypass, state corruption, or unbounded denial of service.
- `Medium`: partial denial of service, information leak, or unsafe default that materially raises attack surface.
- `Low`: hardening, hygiene, or operational issues that should be closed before wider exposure.

## F-001: QUIC transport disables peer verification and does not bind peer identity

- Severity: `High`
- Status: `Open`
- Affected files: `pyjamaz/transport/protocol_jamnp_s.py`, `pyjamaz/transport/cert.py`
- Broken security property: Mutual peer authentication and authenticated transport for JAMNPS.
- Evidence:
  - The client and server QUIC configurations set `verify_mode=ssl.CERT_NONE`.
  - The handshake comment explicitly notes that certificate and ALPN validation are TODOs.
  - Generated certificates omit key usage and EKU constraints, which weakens role binding even before peer verification is added.
- Repro steps:
  1. Start two nodes with arbitrary self-generated certificates.
  2. Connect over JAMNPS.
  3. Observe that the session completes without certificate chain validation or peer identity checks.
- Remediation:
  - Require verified peer certificates on both client and server paths.
  - Bind the certificate subject or SAN to the expected validator identity or peer ID.
  - Enforce the negotiated ALPN value before accepting application data.
  - Decide whether test deployments use a shared CA or an explicit allowlist.
- Required regression coverage:
  - Add transport tests that reject invalid certificates and mismatched ALPN once the hardening lands.

## F-002: WebSocket RPC exposes mutating methods without authentication

- Severity: `High`
- Status: `Open`
- Affected files: `pyjamaz/rpc/ws_server.py`, `pyjamaz/rpc/rpc.py`
- Broken security property: Remote mutation control and least-privilege exposure of state-changing methods.
- Evidence:
  - `ws_server.py` accepts any WebSocket client and dispatches directly into `RPC_REQUESTS`.
  - `rpc.py` registers mutating methods including `submitWorkPackage`, `submitWorkPackageBundle`, and `submitPreimage`.
  - No authentication, authorization, source filtering, or read-only/write split exists at the RPC boundary.
- Repro steps:
  1. Connect any WebSocket client to the configured RPC port.
  2. Send a JSON-RPC request for `submitPreimage` or `submitWorkPackage`.
  3. Observe that the request reaches application logic without prior authentication.
- Remediation:
  - Add an authentication layer or explicit local-only binding for mutating methods.
  - Split RPC into read-only and privileged surfaces if operationally simpler.
  - Add rate limits and request accounting to reduce abuse if the port remains reachable.
- Required regression coverage:
  - Add request tests that prove anonymous clients cannot hit mutating methods after hardening.

## F-003: JAMNPS frame parsing could desynchronize on fragmented or concatenated frames

- Severity: `Medium`
- Status: `Remediated in this branch`
- Affected files: `pyjamaz/transport/protocol_jamnp_s.py`
- Broken security property: Robust stream framing for untrusted transport input.
- Evidence:
  - The previous parser reused the first header when multiple frames shared one read and assumed the header always arrived atomically.
  - That allowed parser desynchronization across fragmented or concatenated frames and made malformed length handling brittle.
- Repro steps:
  1. Deliver a header in multiple QUIC chunks or concatenate two frames into one receive event.
  2. Observe that the original parser read header bytes from the wrong buffer slice.
- Remediation:
  - Replace the ad hoc framing logic with per-stream incremental parsers and explicit maximum payload bounds.
- Regression coverage:
  - `test/test_transport_protocol_jamnp_s.py`

## F-004: Certificates are serialized to disk without private-key encryption

- Severity: `Low`
- Status: `Open`
- Affected files: `pyjamaz/transport/cert.py`
- Broken security property: Private-key-at-rest hygiene for validator node material.
- Evidence:
  - `generate_cert` writes PKCS#8 output with `serialization.NoEncryption()`.
  - The runtime CLI stores generated `cert.key` material under node data directories.
- Repro steps:
  1. Generate node credentials through the CLI.
  2. Inspect the resulting key file on disk.
  3. Observe that the private key is unencrypted PEM.
- Remediation:
  - Decide whether keys are always ephemeral and filesystem-protected or whether encryption at rest is required.
  - If keys remain unencrypted, document the operator expectation and permissions model explicitly.
- Required regression coverage:
  - Add CLI or transport tests once key handling policy is finalized.

## F-005: Local working tree contains generated private-key material

- Severity: `Low`
- Status: `Open`
- Affected paths: `pyjamaz/data/db/`, `db/`
- Broken security property: Workspace secret hygiene.
- Evidence:
  - The current working tree contains generated `cert.key` files under local data directories.
  - `git ls-files` shows these files are not currently committed, so this is an operational hygiene issue rather than a repository-secret incident.
- Repro steps:
  1. List local node data directories in the workspace.
  2. Observe PEM-encoded private keys under the generated DB paths.
- Remediation:
  - Keep these paths ignored.
  - Avoid using real secrets in shared worktrees and rotate if any environment was reused beyond local testing.
- Required regression coverage:
  - Secret scan output from `gitleaks` must remain part of the audit artifact set.
