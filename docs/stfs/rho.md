::: pyjamaz.state.components.Assurances

Each guaranteed work report must have
`auth_gas_used <= GAS_INVOKE` (50,000,000). An excess is rejected with
`authorizer_gas_too_high` before the report is installed. The budget applies
independently to each report; exactly the budget is permitted. The encoded
field remains an unsigned 64-bit gas value.
Error code 28 is a PyJAMaz extension to the official reports STF vocabulary;
the fuzzer protocol transmits its name as an error string.

GP B.1 invokes Is-Authorized with `G_I`, and A.48 ensures consumed gas cannot
exceed the supplied budget. PyJAMaz applies this derived sanity bound during
report admission. Accumulation gas is checked separately under 11.33.

Refinement-load totals are checked independently for each guaranteed report,
including all digests whose refinement result is an error:

- Refinement gas used must be at most the profile's `G_R`.
- Imports and exports must each total at most 3,072 (`W_M` and `W_X`).
- Extrinsics must total at most 128 (`T`).
- `4,488 * total_imports + total_extrinsic_size` must be at most 13,791,360
  (`W_I`, named in PR #563). The import footprint `W_F` is computed from
  GP-0.8.0-eq:14.7 using the logical segment size, independently of
  erasure-shard dimensions.

Violations return `refine_load_too_high` (PyJAMaz error extension 29). These
are report-admission sanity checks derived from package limits in 14.5-14.9,
the item-to-digest mapping in 14.10, report construction in 14.13, and the
invocation gas bound in B.5/A.48. The footprint is only the report-visible
lower bound of 14.6: payload, configuration and authorization-token lengths
are absent from the report. The refinement-load check does not validate serialized bundle
length or package/digest export-count equality.

For Chapter 14, the specification order is the changes, fixes and stated
deviations in the [v0.8.0 conformance release](https://github.com/jam-conformance/jam-test-vectors/releases/tag/v0.8.0),
pinned to commit `d3c089c9a1d5352ad353626d7a2db8589f137b2a`; the additional
selected [graypaper PR #563](https://github.com/gavofyork/graypaper/pull/563)
exception for inclusive gas limits and the existing footprint/bundle bounds;
then GP 0.8.0 for the remaining behavior. Networking delegated by the GP follows
[JAMNP-S v1 at e0b7d291](https://github.com/zdave-parity/jam-np/blob/e0b7d2910afc0a7406043a4c79828edbcc357c2e/simple.md).

PyJAMaz follows [graypaper PR #563](https://github.com/gavofyork/graypaper/pull/563)
for inclusive gas limits. Before authorization or refinement, the report producer
checks that declared budgets across all items total at most `G_R` for refinement
and `G_A` for accumulation. This updates the strict inequalities in
GP-0.8.0-eq:14.9. GP-0.8.0-eq:B.5 / GP-0.8.0-eq:A.48 bound consumption by
those budgets, so reported refinement gas may equal `G_R`.

Report admission rejects
`package_spec.length > MAXIMUM_SIZE_AUDITABLE_BUNDLE` with
`bundle_length_too_high` (PyJAMaz error extension 30). The conservative
serialized-bundle ceiling is 13,904,950 bytes, inclusive (`W_B` in PR #563),
derived as follows:

| Component | Maximum bytes | GP reference |
| --- | ---: | --- |
| Input footprint (`W_I`) | 13,791,360 | 14.6-14.8 |
| Authorization service and code hash | 36 | C.31 |
| Context including eight prerequisites | 425 | C.26, 14.4 |
| Token/configuration prefixes and item count | 9 | C.5, C.7, C.31 |
| Sixteen items' fixed fields and blob/vector prefixes | 992 | C.32 |
| 3,072 import references and proof-length prefixes | 107,520 | C.37, 14.15-14.16 |
| 128 extrinsic manifests | 4,608 | C.32 |

The footprint already allows 4,104 bytes of data and twelve 32-byte proof
hashes per import through `W_F = 4,488`; those bytes are not counted again.
The additional bytes cover metadata omitted from the footprint, including
one prefix per import's proof path. The prefix allowances are conservative
maxima under 14.4-14.8 and C.5. This ceiling includes metadata beyond `W_I`,
as specified by PR #563. It uses package-wide maxima independently of reported
load counters.

Equation 14.18 records the unpadded serialized bundle length defined by
14.16. Erasure padding, shard sizes, exported segments and their paged proofs
do not increase this field. Applying the input limit as `length <= W_I` is too strict:
a single `W_I`-byte payload with empty token/configuration/manifests satisfies
GP-0.8.0-eq:14.6 yet serializes to `W_I + 268` bytes. A test also covers all
sixteen items, 3,072 imports, 128 extrinsic manifests and eight prerequisites
at the content footprint limit; its encoded bundle length is 13,904,899 bytes.

These admission checks enforce necessary bounds derived from honest package
and report construction. They do not replace report reproduction and auditing
under 17.16.

Each report must also satisfy
`package_spec.exports_count == sum(result.refine_load.exports for result in results)`.
Mismatches are rejected with `exports_count_mismatch` (PyJAMaz error extension
31), after the other guarantee checks and before installing any report. The
sum is per report and includes failed results. The refinement-load export cap
in 14.5 applies separately; equality with the digest total is necessary even
when the declared count is within the 3,072-segment limit.

Equation 14.10 copies each work-item's declared export count into its digest.
Equation 14.13 supplies exactly that many segments, replacing exports on error
with zero segments of the declared count. Equations 14.17-14.18 set the
availability count to the length of their concatenation. The report producer
therefore pads failures to `work_item.export_count`, including underproduction,
overproduction, execution failure and oversized output. This also preserves
later items' segment positions.

The canonical report vectors contain inconsistent synthetic export metadata:
14 accepted Tiny vectors (21 reports) and 16 Full vectors (23 reports) expect
acceptance despite count mismatches. They remain unchanged. The tests first
assert rejection with `exports_count_mismatch`, then report their original
acceptance expectations as known conflicts (`xfail`). Synthetic boundary tests
use coherent counts and re-sign their modified reports. See `test/fixtures/SOURCE.md`.
