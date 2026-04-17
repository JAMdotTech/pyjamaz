# Threat Model

## Assets

- Validator identity material: Ed25519 and Bandersnatch keys, generated certificates, and derived peer identity.
- Consensus-critical state: blocks, headers, extrinsics, assurances, disputes, preimages, and state roots.
- VM execution integrity: Refine and Accumulate inputs, hostcall boundaries, gas accounting, and interpreter parity.
- Availability data: work-package blobs, segment stores, D3L entries, and file-backed storage.
- Release integrity: Python dependencies, Docker images, CI workflows, and generated artifacts.

## Trust Boundaries

| Boundary | Untrusted inputs | Main code paths | Primary concerns |
| --- | --- | --- | --- |
| QUIC/JAMNPS peer boundary | Block announcements, block requests, fragmented stream frames | `pyjamaz/transport/protocol_jamnp_s.py`, `pyjamaz/transport/cert.py` | Mutual auth, frame parsing, replay, DOS, peer identity binding |
| WebSocket RPC boundary | JSON-RPC requests and subscriptions from any network client | `pyjamaz/rpc/ws_server.py`, `pyjamaz/rpc/rpc.py`, `pyjamaz/rpc/ws_server_subscriptions.py` | Unauthenticated writes, request validation, subscription abuse, size limits |
| Codec and deserialization boundary | External JAM bytes, preimages, state blobs, PVM code | `pyjamaz/models/*`, `pyjamaz/state/*`, `pyjamaz/pvm/types.py` | Bounds checks, malformed length handling, decode consistency |
| PVM and hostcall boundary | Refine and Accumulate program input, memory slices, hostcall registers | `pyjamaz/pvm/*`, `pyjamaz/hostcalls/*` | Memory safety, gas invariants, authorization, interpreter divergence |
| Local operator and release boundary | Seeds, cert files, Docker config, CI secrets | `pyjamaz/cli.py`, `docker-compose*.yml`, `.github/workflows/*` | Secret hygiene, deterministic configs, supply chain drift |

## Highest-Risk Abuse Cases

1. Remote peer connects over QUIC without trusted identity and injects malicious or replayed traffic.
2. Anonymous RPC client submits work packages or preimages into a reachable node.
3. Malformed or oversized JAM payload desynchronizes the frame parser or decoder and causes denial of service.
4. PVM or hostcall divergence produces different outcomes across interpreters for the same corpus.
5. Supply-chain changes or leaked local key material weaken node integrity outside the protocol logic.

## Review Order

1. Transport and RPC trust boundaries.
2. Untrusted decoding and state-transition boundaries.
3. PVM, hostcalls, and interpreter parity.
4. Storage, CLI key handling, Docker, and CI release surfaces.
