# Fixture sources

The upstream fixtures listed below match
[davxy/jam-test-vectors v0.8.0](https://github.com/davxy/jam-test-vectors/releases/tag/v0.8.0),
pinned to commit `d3c089c9a1d5352ad353626d7a2db8589f137b2a`.
They are distributed under upstream's
[CC0 1.0 Universal license](https://github.com/davxy/jam-test-vectors/blob/d3c089c9a1d5352ad353626d7a2db8589f137b2a/LICENSE).

Paths in the first column are relative to this directory. Imported files are
byte-for-byte copies; STF tests vendor JSON only, while codec tests retain both
JSON and binary representations.

| Local fixtures | Upstream path | Files |
| --- | --- | ---: |
| `accumulate/tiny/*.json` | `stf/accumulate/tiny/*.json` | 63 |
| `assurances/tiny/*.json` | `stf/assurances/tiny/*.json` | 11 |
| `authorizations/tiny/*.json` | `stf/authorizations/tiny/*.json` | 3 |
| `disputes/tiny/*.json` | `stf/disputes/tiny/*.json` | 29 |
| `blocks-history/*.json` | `stf/history/tiny/*.json` | 4 |
| `preimages/*.json` | `stf/preimages/tiny/*.json` | 8 |
| `reports/tiny/*.json` | `stf/reports/tiny/*.json` | 44 |
| `safrole/tiny/*.json` | `stf/safrole/tiny/*.json` | 21 |
| `statistics/tiny/*.json` | `stf/statistics/tiny/*.json` | 4 |
| `codec/w3f/*.{json,bin}` | `codec/tiny/*.{json,bin}` | 30 |
| `trie.json` | `trie/trie.json` | 1 |
| `shuffle_tests.json` | `shuffle/shuffle_tests.json` | 1 |

The trie JSON uses 32-byte generated keys. Its upstream `trie/merkle.py` drops
the final byte when encoding leaves; the test applies that same conversion to
31-byte state keys without modifying the fixture.

Other fixtures, including `codec/jdt`, `pvm`, `hostcalls`, `cli`, `state_trie`,
and `ed25519_vectors.json`, are project-specific or separately sourced. They are
not covered by this release provenance or its license statement. Full-profile
STF and codec corpora, erasure vectors, and block traces are not vendored here.

## Running the release vectors

The default Tiny profile uses these vendored fixtures. To select an external
release checkout, set `JAM_TEST_VECTORS` to its root or its `stf` directory.
For Full, run the following from the repository root using the project's active
Python environment:

```sh
JAM_TEST_VECTORS=/path/to/jam-test-vectors JAM_FUZZ=1 JAM_FUZZ_SPEC=full \
PVM_INTERPRETER=CPYTHON python -m pytest \
  test/test_accumulate.py test/test_assurances.py test/test_authorizations.py \
  test/test_blocks_history.py test/test_disputes.py test/test_preimages.py \
  test/test_reports.py test/test_safrole.py test/test_statistics.py \
  test/test_codec.py test/test_merkle_trie.py test/test_shuffle.py
```

This selects the release-vector harnesses; other unit tests may assume Tiny.
The 18 custom JDT codec tests use Tiny fixtures and are intentionally skipped in
Full. Selecting the external corpus does not imply that all production behavior
passes its vectors.

The release documents a deviation for `bless_from_non_manager`: it accepts
non-manager `bless` calls where GP 0.8.0 returns `HUH`. The setting
`GP080_NON_MANAGER_BLESS_COMPAT` in `pyjamaz/settings.py` controls this behavior
and is currently enabled. Set it to `False` to enforce the printed GP rule.
Compatibility only applies while `GP_VERSION` is `0.8.0`; memory, gas, and
service-ID checks remain active. Fixture expectations are unchanged.

The release also adopts GP #533's `grow_heap` behavior: query calls cost only
the base charge, and insufficient gas is drained to zero without changing
registers or memory. `GP080_GROW_HEAP_OOG_COMPAT` in `pyjamaz/settings.py` is
enabled for these vectors. Set it to `False` for the printed GP 0.8.0 B.15-B.16
rules, which retain gas on failed growth and can produce a different state
root through accumulation gas statistics.

GP #538 rounds the stack reservation to 64 KiB zones when computing the
`grow_heap` upper bound. `GP080_GROW_HEAP_STACK_COMPAT` is enabled for this rule;
set it to `False` to retain the printed page-rounded bound. This changes the
heap limit without moving the stack's mapped pages. All three compatibility
settings apply only while `GP_VERSION` is `0.8.0`. Disable both `grow_heap`
settings to use its printed GP 0.8.0 rules.

The remaining release deviations are always enforced: conditional moves count
the destination as a source register for gas pricing, and program blobs reject
more than 2²⁵ code bytes or 2²⁴ jump-table entries before decoding their payloads
(GP #559). These limits apply to both standard programs and nested machines.

## Report export-count conflicts

The pinned report STF vectors use synthetic availability export counts that
disagree with their digest export totals. All 14 accepted Tiny vectors (21
reports) and all 16 accepted Full vectors (23 reports) have this inconsistency.
For example, `report_curr_rotation-1.json` declares three package exports but
17 in its digest. GP 14.10, 14.13 and 14.17-14.18 imply equality, including
zero-segment padding for failed refinements.

The source vectors are not rewritten. For each affected vector, the test
first verifies `exports_count_mismatch` and unchanged availability state, then
marks the source's acceptance expectation as a known conflict (`xfail`). A
different rejection or unexpected acceptance fails the test before that mark.
Synthetic validation tests align their counts and re-sign modified reports;
dedicated tests exercise inconsistent counts without that alignment.

## External block traces

The same pinned release supplies `traces/fuzzy_light`: 200 Tiny inputs plus
`genesis.bin`, not vendored here. Keep genesis and all preceding trace inputs
together so replay can reconstruct the actual header ancestry. For example:

```sh
JAM_FUZZ=1 JAM_FUZZ_SPEC=tiny PVM_INTERPRETER=CPYTHON \
  python -m pyjamaz.cli traces /path/to/fuzzy_light
```

The command uses memory storage, skips historical wall-clock checks, and exits
with an error if a pre-state or post-state root differs. Other validation stays
active, using the configured compatibility settings. Blocks 152–155 are expected
to be rejected with `bad_code_hash` and keep their pre-state roots; all 200
post-state roots must match. Omit `--prompt` for automated runs.

Mismatch diagnostics are written beside the inputs. Use a temporary directory
containing copies or symlinks of all `.bin` files to keep the source corpus clean.
