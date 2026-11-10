# Chapter 14 and Appendix H: Implementation Analysis

Date: 2026-11-09

Repository: `/Users/arjan/Development/pyjamaz`

Specification: [Graypaper 0.8.0, June 3, 2026](</Users/arjan/Documents/Jamdot Tech/Graypaper/graypaper-0.8.0.pdf>), Chapter 14 (pages 26–29) and Appendix H (pages 71–73).

Updated after implementing the Chapter 14 availability data flow in the working tree. The original local-recovery analysis has been revised to describe the resulting runtime and transport behavior.

Specification precedence is the [v0.8.0 release](https://github.com/jam-conformance/jam-test-vectors/releases/tag/v0.8.0) at `d3c089c9a1d5352ad353626d7a2db8589f137b2a`, the explicitly selected additional [PR #563](https://github.com/gavofyork/graypaper/pull/563) exception, then GP 0.8.0. Delegated networking follows [JAMNP-S v1 at e0b7d291](https://github.com/zdave-parity/jam-np/blob/e0b7d2910afc0a7406043a4c79828edbcc357c2e/simple.md).

## Assessment

**Appendix H recovery and Chapter 14's submission, availability artifacts, peer data services and local retention flow are implemented. Full guarantee coordination, assurance voting and audit judgments remain Chapters 15–17 work. The selected PR #563 equality and footprint policies are retained.**

The analysis compared the specification with the relevant code, reran tests and reproduced several boundary cases.

“Implemented” below means the calculation or behavior exists in executable code. It does not automatically mean the corresponding distributed node workflow is complete.

## Chapter 14: Equation-by-equation status

Chapter 14 defines deterministic calculations and data services used by later validator roles. The GP-facing interfaces retain their original arguments and return values; convenience functions compose those calculations.

| GP reference | Requirement | Current implementation |
|---|---|---|
| **14.1** | Segments contain exactly 4,104 bytes | **Implemented.** Import verification enforces this size; export host calls pad segments to it. |
| **14.2–14.3** | Work-package and work-item structures, including manifests and tagged import references | **Implemented.** Models, codecs and the distinction between segment roots and tagged package hashes exist. Package validation enforces 1–16 items. |
| **14.4** | At most eight dependencies | **Implemented.** Counts unique tagged package references plus context prerequisites, following the equation. |
| **14.5** | Package-wide export, import and extrinsic limits | **Implemented.** Limits are 3,072 exports, 3,072 imports and 128 extrinsics. |
| **14.6–14.8** | Package footprint and import-proof allowance | **Implemented.** Includes authorization/configuration bytes, payloads, imported segments and declared extrinsic lengths. `W_F = 4,488`; the package footprint limit is 13,791,360 bytes. |
| **14.9** | Aggregate refinement and accumulation gas budgets | **Different from the printed equation.** The PDF uses `<`; the implementation permits equality. |
| **14.10** | Convert each work item into its digest | **Implemented.** Copies identifiers, gas allowance, result and manifest counters, and hashes the payload. |
| **14.11** | Authorizer identity and historical authorization-code lookup | **Implemented.** Authorizer hash uses the authorization-code hash and configuration. Code lookup checks historical availability at the lookup-anchor slot. |
| **14.12** | Construct paged proofs for exported segments | **Implemented.** Encoding, decoding, canonical-count checks, padding validation and direct-proof reconstruction exist. |
| **14.13** | Compute `Ξ(p,c,l,v)` | **Implemented.** Authorization precedes bundle validation/acquisition. Runtime and public `Ξ` share the authorized report calculation, with one authorization per unchanged attempt. |
| **14.14** | Package-hash-to-export-root correspondence | **Implemented.** Recent/pending report mappings and canonical source records establish correspondence. Builder mappings are checked against known reports. Local artifacts remain distinct from chain-backed sources. |
| **14.15** | `X`, `L_l`, `S_l` and `J_l` | **Implemented.** Local imports/full exports precede guarantor requests and coded segment/proof-page recovery. Every import is verified before storage and manifest-order bundle construction. |
| **14.16** | Assemble the auditable bundle `B(p,l)` | **Implemented.** A shared canonical codec covers production RPC, client and fuzzer submission, including import justifications. Truncation, conflicting data, noncanonical encoding and trailing data are rejected. |
| **14.17** | Derive the package availability specification from the computed bundle and exports | **Implemented.** Report construction calls `A` with the package hash, assembled bundle, flattened exports and explicit assurer count. |
| **14.18** | Calculate availability commitments | **Implemented.** `availability_spec` returns only the GP specification; `build_availability_artifacts` shares its calculation and retains encoded rows and proofs for distribution. |
| **14.19** | Zero padding | **Implemented.** Encoding pads to the required alignment; blob recovery verifies discarded padding is zero. |

The main implementation locations are [package validation, imports and availability calculations](/Users/arjan/Development/pyjamaz/pyjamaz/availability.py:25), [report computation](/Users/arjan/Development/pyjamaz/pyjamaz/refinement.py:25), and [digest construction](/Users/arjan/Development/pyjamaz/pyjamaz/models/common.py:513).

Some TODO comments in the package models are outdated: the corresponding limits are now enforced by `validate_work_package`. Those comments should not be interpreted as evidence that the limits are absent.

### Gas-limit compatibility policy

The gas boundary is a deliberate compatibility policy, rather than an unimplemented check. On page 27, equation 14.9 requires:

```text
sum(accumulation budgets) < G_A
sum(refinement budgets)   < G_R
```

The code rejects only values *greater than* the limit, therefore permitting equality. Its comments and documentation explicitly attribute this to PR #563. Acceptance was reproduced with both declared budgets exactly at their limits. See the [validation check](/Users/arjan/Development/pyjamaz/pyjamaz/availability.py:49) and [documented policy](/Users/arjan/Development/pyjamaz/docs/stfs/rho.md:34).

This is the selected additional exception to the release/GP source policy. No alternative strict-14.9 mode is introduced.

### Authorization ordering

Cheap package/core checks precede Is-Authorized, which runs against a detached service-state snapshot. Bundle hashing, import-proof validation and peer recovery follow successful authorization. Staged CE133/146 submissions use a bounded initial QUIC receive window and expand it after authorization.

The runtime binds that result to the package, requested core, committed head/root and ordered validator keys. It reuses the result through the private authorized-report calculation and restarts when those inputs become stale. Public `Ξ(p,c,l,v)` retains its signature and report-only return value. See [report computation](/Users/arjan/Development/pyjamaz/pyjamaz/refinement.py) and [runtime orchestration](/Users/arjan/Development/pyjamaz/pyjamaz/runtime/pipelines/refine.py).

### Result and export behavior

The result and export behavior is implemented carefully. Equation 14.13’s precedence is reflected in the code:

- Oversized output becomes `digest_oversize`.
- An incorrect export count becomes `bad_exports`.
- Failed items contribute exactly their declared number of zero segments.
- Later items receive export offsets that include those declared positions.
- Successful output sizes accumulate together with the authorization trace.

This preserves the meaning of subsequent segment indexes even when an earlier item fails. These cases are covered by the migrated export-padding tests.

### Local imports into the real refine PVM

Imported segments now reach the real refine PVM. The local path supports:

- Direct segment-root references and tagged work-package references.
- Direct import proofs or reconstructed proof pages.
- Recovery using the source report’s assurer count.
- Persistent storage of individually verified imports.
- Fallback to complete stored export sets.
- Multiple work items, duplicate imports and manifest ordering.
- `fetch` selector 5 for another item’s imports and selector 6 for the current item’s imports.

The runtime retries when local data is missing or corrupt. Recovered imports and complete stored exports produce identical bundle and report bytes in integration tests. See [runtime acquisition](/Users/arjan/Development/pyjamaz/pyjamaz/runtime/pipelines/refine.py:125) and [verified import storage](/Users/arjan/Development/pyjamaz/pyjamaz/d3l.py:51).

### Production bundle RPC ingestion

The RPC preserves `[core_index, encoded_bundle]` and queues the complete canonical bundle. The client accepts import segments and required justifications; import-free calls remain compatible. The queued core is honored, and execution validates the supplied bundle after authorization. The same codec is used by the fuzzer adapter. See [bundle codec](/Users/arjan/Development/pyjamaz/pyjamaz/bundle.py), [RPC](/Users/arjan/Development/pyjamaz/pyjamaz/rpc/rpc.py) and [client](/Users/arjan/Development/pyjamaz/pyjamaz/rpc/ws_client.py).

## Appendix H: Mathematical implementation

Appendix H is implemented through a small Python interface backed by the native erasure library. The absence of separate Python functions for every mathematical definition is not a missing feature: splitting, joining, transposition and field operations are implemented within the encoding/recovery path.

| GP reference | Definition | Assessment |
|---|---|---|
| **H.1** | Compute `D(v)` | **Implemented.** Selects the largest permitted divisor that allows segments to encode without padding. |
| **H.2** | Split a byte sequence | **Implemented within the native layout and Python slicing operations.** No separate public function is necessary. |
| **H.3** | Join subsequences | **Implemented.** Includes the systematic recovery fast path. |
| **H.4** | Transposition | **Implemented.** Native encoding/recovery operates on the required two-byte columns; availability construction also transposes segment data into validator rows. |
| **H.5** | `Cᵛₖ(d)` chunk encoding | **Implemented as `encode_chunks`.** Validates dimensions and returns `v` chunks of `2k` bytes. |
| **H.6** | `Rᵛₖ(c)` indexed recovery | **Implemented as `recover_chunks`.** Requires exactly `D(v)` indexed chunks, uses ordered concatenation for systematic chunks, otherwise invokes native recovery. |
| **H.7–H.8** | Field polynomial and GF(2¹⁶) construction | **Implemented through the native dependency.** The inspected backend uses `0x1002D`, matching the PDF’s polynomial. |
| **H.9–H.10** | Word representation, Cantor basis and validator-index representation | **Implemented through the native dependency.** All 16 basis values were compared with the PDF and matched. |
| **H.11–H.12** | Interpolation and evaluation of the generator polynomial | **Implemented through the native dependency.** Encoding and recovery are exercised against pinned external vectors. |

The Python interfaces and equation mappings are in [erasure.py](/Users/arjan/Development/pyjamaz/pyjamaz/erasure.py:8). The native adapter’s per-column encoding and recovery are visible in [the binding implementation](/Users/arjan/Development/py-jam-erasure-bindings/rust/src/lib.rs:100).

The resulting dimensions also match the parameterized specification:

| Assurers `v` | Original chunks `D(v)` | Bytes per chunk for one 4,104-byte segment |
|---:|---:|---:|
| 6 | 3 | 1,368 |
| 9 | 4 | 1,026 |
| 1,020 | 228 | 18 |
| 1,023 | 342 | 12 |

The `1,020` case matters: `D(v)` is constrained by divisibility, so using a simple “one-third plus one” formula everywhere would be incorrect. The current implementation handles this.

The convenience functions `encode_blob`, `recover_blob` and `recover_segment` correctly sit around the GP-defined transformations. They manage arbitrary blob lengths, select a deterministic threshold from surplus shards, handle empty inputs and check zero padding before trimming.

### Recovery and authentication

Erasure recovery does not authenticate data. Authentication occurs when `recover_import` verifies the resulting segment against the committed export root.

The analysis reproduced a case containing five valid shards and one corrupt systematic shard. The convenience function selected the systematic set, and import verification rejected the result. Selecting the valid parity subset succeeded. H.6 assumes valid input chunks. The peer acquisition layer now follows CE139 with a CE140 retry using individually proven chunks if reconstructed segment/proof verification fails; the mathematical helper remains a deterministic recovery function.

## Distributed availability implementation

The availability runtime supplies the data services consumed by Chapters 15–17.

| Capability | Implementation | Boundary |
|---|---|---|
| **Acquiring imports** | Verified local imports/full exports, CE148 guarantor requests, CE139 ordinary shards, CE140 proven retry | Four requests in flight, five-second timeouts, one peer pass per recovery phase; insufficient data is retryable |
| **Original assuring set** | Source records preserve validator order, core, guarantor identities and registration/assurance block references | Historical metadata is reconstructed only when retained block/state context suffices; otherwise data remains unavailable |
| **Availability artifacts** | Encoded bundle chunks, export/proof-page rows and outer co-paths persist before report readiness | Each successful report attempt encodes one `(package hash,v)` artifact set |
| **Chunk proofs** | Appendix E.2 well-balanced traces, complete-row, audit-chunk and combined segment-chunk verification | Root-first proof order, singleton hashing, exact dimensions and indexes are checked |
| **Chunk distribution** | Accepted guarantees enqueue assigned-shard acquisition through CE137; CE138/147 and CE139/140/148 serve retained data | Readiness is exposed without producing assurance votes |
| **Availability eligibility** | Canonical source lookup follows the selected branch and historical peer identities | Builder-provided mappings do not establish chain-backed metadata; local retention expiry is not a consensus rule |
| **Retention** | Atomic versioned records, audit payloads until assurance finality, segment rows for at least 672 epochs | Real `finalize` drives pruning; active requests/shared data remain protected and segment proofs survive audit-payload deletion |
| **Transport** | Pinned v1 genesis ALPN, mutual Ed25519/SAN identity and independent incremental QUIC stream readers | Includes partial frames, FIN, rejection, resets, timeouts and cancellation; UP0/block requests are retained |
| **Assuring and auditing** | Verified data acquisition/storage/serving and readiness | Full guarantee coordination, assurance voting, audit selection and judgment production remain Chapters 15–17 |

The implementation is in [availability calculations](/Users/arjan/Development/pyjamaz/pyjamaz/availability.py), [storage](/Users/arjan/Development/pyjamaz/pyjamaz/d3l.py), [runtime data services](/Users/arjan/Development/pyjamaz/pyjamaz/runtime/availability.py) and [transport](/Users/arjan/Development/pyjamaz/pyjamaz/transport/protocol_jamnp_s.py). Retained bundle-chunk hashes and co-paths permit long-lived CE140 proofs after audit payload deletion.

The PDF also describes preparing distributions for two differently sized validator sets around an epoch change. The calculations can be invoked with different `v` values; automatic dual preparation remains a deferred reward optimization.

## Verification and confidence

The final implementation regression run produced:

- **693 passed, two skipped and 14 expected failures** across recovery, refinement, hostcalls, reports, traces and the new submission/artifact/storage/lifecycle/transport tests. This extends the earlier 497-pass baseline.
- **Six additional passes with the Graypaper interpreter** for local and peer recovered-import integration through the real PVM.
- **17 transport tests**, included in the 693 passes, cover genuine QUIC exchanges. The six-node integration persists source metadata, corrupts CE139 responses, recovers through CE140 and consumes imports through real PVM `fetch` selectors 5/6, requiring identical bundle/report bytes to complete stored exports.
- Byte-for-byte encoding and systematic/parity/mixed recovery against **12 pinned Tiny and Full erasure vectors**.
- Recovery round trips for **340 validator counts**.
- Proof-page tests around 64-leaf boundaries and at the 3,072-export limit.
- Tests for malformed proofs, noncanonical encoding, nonzero padding, corrupt storage, retries and equivalent reports from recovered versus complete exports.
- Lifecycle tests cover successful/failed commits, historical guarantors and resized assurer sets, missing-source backfill, assurance reconstruction, fork selection, active requests, 672-epoch boundaries and real finalization.

An additional broader run found seven stale tests in the pre-existing untracked `test/test_fuzzer_refinement_batch.py`: they require an absent `fuzzer traces --results-file` option. That batch-CLI feature is outside this change. Existing reference expectations were not rewritten.

The [erasure tests](/Users/arjan/Development/pyjamaz/test/test_erasure.py), [import-recovery tests](/Users/arjan/Development/pyjamaz/test/test_import_recovery.py), [peer/PVM tests](/Users/arjan/Development/pyjamaz/test/test_peer_availability.py), [lifecycle tests](/Users/arjan/Development/pyjamaz/test/test_availability_lifecycle.py) and [QUIC tests](/Users/arjan/Development/pyjamaz/test/test_jamnp_transport.py) support these conclusions.

The 340-count check is round-trip evidence, not 340 independent byte-level reference oracles. Likewise, the availability-root construction test independently assembles the structure but shares the native erasure backend. Additional external golden outputs for complete `B`, `A` and `Ξ` calculations would strengthen the conformance evidence.

The 14 expected failures are documented conflicts in upstream report vectors: those vectors expect acceptance despite inconsistent export counts. The tests first verify the implementation’s rejection, then mark the original acceptance expectation as a known conflict. They are not 14 new failures caused by recovery.

## Overview

| Area | Overall status |
|---|---|
| **Appendix H mathematical transformations** | **Implemented**, with native-backed field arithmetic and substantial test evidence |
| **Chapter 14 package rules and report calculations** | **Implemented**, retaining the selected PR #563 exception and authorization-first ordering |
| **Local recovered imports into refinement** | **Implemented and integration-tested** |
| **Production bundle RPC ingestion** | **Implemented**, including import justifications and requested cores |
| **Distributed shard acquisition, proofs and distribution** | **Implemented for the selected availability streams** |
| **Historical assurer routing and availability lifecycle** | **Implemented**, with unavailable historical context reported explicitly |
| **Complete honest-assurer and auditor operation** | **Outside this change: Chapters 15–17 coordination, voting and judgments** |

## Recommendations

1. Connect the existing data-readiness services to the remaining Chapters 15–17 coordination, assurance and audit workflows.
2. Add independent external golden `B`, `A` and full-report outputs when available. Current root-structure checks share the native erasure backend; the pinned erasure vectors provide an independent oracle for that backend.
3. Keep aioquic pinned to 1.3.0 while its small mutual-TLS/receive-window integration hooks use private interfaces, and rerun the QUIC identity/framing/flow-control suite on upgrades.
4. Evaluate large-package throughput before adding optimizations or simultaneous preparation for differently sized validator sets. Both remain deliberately deferred.

Existing pre-v1 certificates containing IP SANs must be regenerated; v1 requires the single DNS SAN derived from the Ed25519 key. The CLI certificate initializer now derives that name correctly. Startup also requires the genesis header hash for the v1 ALPN, supplied by persisted genesis data or an explicit transport constructor argument.
