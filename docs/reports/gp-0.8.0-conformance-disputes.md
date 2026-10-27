# GP 0.8.0 conformance disputes

Updated 2026-10-27. All six issues are fixed. Replaying all **41 trace directories** through both `traces` and socket-based `fuzzer traces` produced **61 matching candidate post-state roots and zero mismatches per command**. Expected block rejections still produce error messages.

Scope: the **29 originally disputed traces** in the [PyJAMaz summary](/Users/arjan/Development/jam-conformance/fuzz-reports/0.8.0/summaries/pyjamaz.txt). Equation numbers refer to the supplied [Graypaper 0.8.0](</Users/arjan/Documents/Jamdot Tech/Graypaper/graypaper-0.8.0.pdf>).

## 1. Lookup-anchor ancestry — 12 traces

- **Cause:** PyJAMaz required historical lookup-anchor evidence even when ancestry was disabled by the session handshake. Shortened trace replay also initialized the chain incorrectly.
- **GP / protocol:** 5.3 defines ancestry; 11.37 checks lookup age; 11.38 checks historical commitments. The [fuzzer protocol](https://github.com/davxy/jam-conformance/blob/v0.8.0/fuzz-proto/README.md#features) negotiates the intersection of supported features.
- **Applied fix:** Pass negotiated ancestry support into block import and skip only the historical check when disabled. Preserve age checks and strict normal-operation validation. Both replay commands initialize shortened chains from their first record as a trusted checkpoint; socket replay uses a fresh session per chain.
- **References:** [commit 9491e289](https://github.com/JAMdotTech/pyjamaz-poc/commit/9491e289), [ancestry guard](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1040), [replay initialization](/Users/arjan/Development/pyjamaz/pyjamaz/cli.py:686).

## 2. Validator appears as both culprit and faulty voter — 1 trace

- **Cause:** Adding culprit evidence updated the offender set before fault evidence was checked, incorrectly rejecting the same validator's second evidence entry.
- **GP:** 10.6–10.7 check eligibility against prior offenders; 10.9 requires uniqueness within each list. 10.18 unions posterior offenders; 10.19 concatenates evidence markers.
- **Applied fix:** Check both lists against a frozen prior offender set. Store the validator once in posterior state and preserve both marker entries. Within-list uniqueness and signature checks remain enforced.
- **References:** [commit d673ad3e](https://github.com/JAMdotTech/pyjamaz-poc/commit/d673ad3e), [offender handling](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1751).

## 3. Authorization gas exceeds invocation budget — 5 traces

- **Cause:** PyJAMaz accepted the field's unsigned-64-bit range without enforcing the authorization invocation budget.
- **GP:** B.1 supplies `G_I`; A.48 bounds consumed gas by supplied gas; 14.13 copies consumption into the report.
- **Applied fix:** Require `auth_gas_used ≤ 50,000,000` per report. Equality is allowed; excess returns `authorizer_gas_too_high`.
- **References:** [commit eeb128c7](https://github.com/JAMdotTech/pyjamaz-poc/commit/eeb128c7), [gas check](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1262).

## 4. Impossible refinement-load claims — 3 original traces

- **Cause:** Digest load fields were accepted without checking whether their totals could describe an admissible package.
- **GP:** 14.5–14.10 define package limits and digest mapping; B.5/A.48 bound consumed gas.
- **Applied fix:** Sum all digests per report, including failed results. Require gas `< G_R`, imports/exports each `≤ 3,072`, extrinsics `≤ 128`, and `4,488 × imports + extrinsic_bytes ≤ 13,791,360`. Reject with `refine_load_too_high`. This also catches an originally green trace, `1792933529_8343`.
- **References:** [commit 9593f911](https://github.com/JAMdotTech/pyjamaz-poc/commit/9593f911), [load check](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1288).

## 5. Excessive auditable-bundle length — 4 traces

- **Cause:** PyJAMaz accepted near-4-GiB length claims without a bound derived from admissible bundle contents.
- **GP:** §14.3 and 14.6–14.8 bound contents; 14.16/14.18 define serialized, unpadded bundle length. Appendix C supplies encoding overhead.
- **Applied fix:** Enforce a conservative **13,904,950-byte** ceiling, including serialization metadata. This is a derived ceiling, not a printed GP constant or tight maximum. Using the footprint limit alone would reject valid bundles. Excess returns `bundle_length_too_high`; one affected trace is rejected earlier for authorization gas.
- **References:** [commit 3ceec392](https://github.com/JAMdotTech/pyjamaz-poc/commit/3ceec392), [length check](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1313), [bound derivation](/Users/arjan/Development/pyjamaz/docs/stfs/rho.md:38).

## 6. Package export count disagrees with digest exports — 4 traces

- **Cause:** Package and digest export counts were never compared. The producer also padded failures using the actual returned count instead of the declared count.
- **GP:** 14.10 copies declared counts; 14.13 preserves cardinality on failure; 14.17–14.18 concatenate and count exports.
- **Applied fix:** Require `package_spec.exports_count == Σ digest.exports` per report, including failures. Reject mismatches with `exports_count_mismatch`. Pad failed production to the declared count, preserving subsequent segment positions.
- **References:** [commit de8aa275](https://github.com/JAMdotTech/pyjamaz-poc/commit/de8aa275), [count check](/Users/arjan/Development/pyjamaz/pyjamaz/state/components.py:1319), [producer padding](/Users/arjan/Development/pyjamaz/pyjamaz/app.py:1314).

## Interpretation and verification

Issues 3–6 enforce necessary bounds derived from Chapter 14 construction during report admission. Chapter 11 does not repeat each predicate explicitly; these checks do not replace reproduction/auditing under 17.16. The authorization-gas, refinement-load and bundle-length compatibility switches were removed; export-count validation was added without a switch.

- **Tests:** Reports and producer tests: Tiny **105 passed / 14 xfailed**; Full **107 passed / 16 xfailed**. The xfails expose unchanged canonical fixtures that expect acceptance of inconsistent export counts; tests assert correct rejection before marking that source conflict. See [fixture notes](/Users/arjan/Development/pyjamaz/test/fixtures/SOURCE.md:81).
- **Replay evidence:** [socket results](/tmp/jam080-fuzzer-all-verify-_m6wb_jc/results.json), [ordinary CLI results](/tmp/jam080-fuzzer-all-verify-_m6wb_jc/direct-results.json). These replay recorded PolkaJam outcomes; they are not a fresh PolkaJam run. Its exact bundle-size boundary remains unverified.
