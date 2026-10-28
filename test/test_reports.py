import json
import os
import unittest
from copy import deepcopy
from os import path
from types import SimpleNamespace
from typing import Optional

from parameterized import parameterized
import pytest

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.models.block import Header, Guarantee, Extrinsic, ExtrinsicDisputes
from pyjamaz.models.common import WorkReport, WorkPackage, WorkItem, ImportSegment, WorkItemExtrinsic, RefinementContext
from pyjamaz.models.state import AssurancesState, ValidatorPoolState, ValidatorArchiveState, TimeslotState, \
    ServicesState, RecentHistoryState, AuthorizerPoolsState, AccumulationHistoryState, EntropyState, DisputesState, \
    ServiceAccount, PendingChanges, AccumulationQueueState
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, MAXIMUM_AGE_LOOKUP_ANCHOR, GAS_INVOKE
from pyjamaz.settings import TEST_SUITE
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.storage import StateStorage
from pyjamaz.state.components import Assurances
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.signing import Ed25519Keypair
try:
    from test.vector_fixtures import stf_vector_dir
except ModuleNotFoundError:  # Direct script execution.
    from vector_fixtures import stf_vector_dir


VECTOR_DIR = stf_vector_dir("reports", TEST_SUITE)


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = VECTOR_DIR
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


def reformat_work_report(work_report_data: dict) -> dict:
    work_report_data["segment_root_lookup"] = {
        s["work_package_hash"]: s["segment_tree_root"] for s in work_report_data["segment_root_lookup"]
    }
    return work_report_data

class TestReports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        storage_engine = InMemoryStorageEngine()
        cls.block_context = BlockContext()

        cls.app_context = AppContext(state_storage=StateStorage(storage_engine))

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = VECTOR_DIR / test_vector_file
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):
        test_vector = self.load_test_vector_data(test_file)
        inconsistent = any(
            g['report']['package_spec']['exports_count'] !=
            sum(result['refine_load']['exports'] for result in g['report']['results'])
            for g in test_vector['input']['guarantees']
        )
        if 'ok' in test_vector['output'] and inconsistent:
            # Assert the GP-derived rejection before reporting the unchanged
            # upstream acceptance expectation as a known vector conflict.
            test_vector['output'] = {'err': 'exports_count_mismatch'}
            test_vector['post_state']['avail_assignments'] = test_vector['pre_state']['avail_assignments']
            self.check_vector(name, test_vector)
            pytest.xfail('Canonical vector accepts inconsistent export counts; GP-0.8.0-eq:14.10 / GP-0.8.0-eq:14.13 / GP-0.8.0-eq:14.18 require equality')
        self.check_vector(name, test_vector)

    def check_vector(self, name, test_vector, *, retain_ancestry=True):

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]

        # Set up pre-state
        post_state_timeslot = TimeslotState(number=header.timeslot)

        # extrinsic_guarantees = [Guarantee.from_json(a) for a in test_vector["input"]["guarantees"]]
        extrinsic_guarantees = [Guarantee.from_json({
            "report": reformat_work_report(i["report"]),
            "slot": i["slot"],
            "signatures": i["signatures"]
        }) for i in test_vector["input"]["guarantees"]]

        extrinsic = Extrinsic(
            tickets=[],
            disputes=ExtrinsicDisputes(verdicts=[], culprits=[], faults=[]),
            preimages=[],
            assurances=[],
            guarantees=extrinsic_guarantees
        )

        header.extrinsic_hash = extrinsic.generate_extrinsic_hash()

        pre_state_assurances = AssurancesState.from_json({"assurances": test_vector["pre_state"]["avail_assignments"]})
        post_state_validator_pool = ValidatorPoolState.from_json(
            {"validators": test_vector["pre_state"]["curr_validators"]}
        )

        post_state_validator_archive = ValidatorArchiveState.from_json(
            {"validators": test_vector["pre_state"]["prev_validators"]}
        )

        pre_services = ServicesState()
        pre_services.set_state_storage(self.app_context.state_storage)
        pre_services.pending_changes = PendingChanges()

        for s in test_vector["pre_state"]["accounts"]:
            pre_services.store_service_account(s["id"], ServiceAccount.from_json({
                "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                "balance": s["data"]["service"]["balance"],
                "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                "footprint_storage_items": s["data"]["service"]["items"],
                "footprint_storage_bytes": s["data"]["service"]["bytes"],
                "threshold_balance": 0,
                "storage_items": {},
                "preimages": {},
                "preimage_availability": {},
                "deposit_offset": s["data"]["service"]["deposit_offset"],
                "creation_slot": s["data"]["service"]["creation_slot"],
                "last_accumulation_slot": s["data"]["service"]["last_accumulation_slot"],
                "parent_service": s["data"]["service"]["parent_service"]

            }))



        intermediate_state_recent_history = RecentHistoryState.from_json(
            {
                'recent_blocks': test_vector["pre_state"]["recent_blocks"]['history'],
                'accumulation_output_log': test_vector["pre_state"]["recent_blocks"]['mmr']['peaks']
            }
        )

        pre_authorizer_pools = AuthorizerPoolsState.from_json(
            {"authorizer_pools": test_vector["pre_state"]["auth_pools"]}
        )

        pre_accumulation_history = AccumulationHistoryState(accumulation_history=[])
        pre_accumulation_queue = AccumulationQueueState(
            accumulation_queue=[[] for _ in range(EPOCH_TIMESLOTS)]
        )

        # Equation 11.35 is an off-state check against the retained ancestor
        # header set. Populate that set from the vector's declared contexts.
        self.app_context.state_storage.ancestors.clear()
        for guarantee in (extrinsic_guarantees if retain_ancestry else []):
            lookup_header = Header.default()
            lookup_header.timeslot = guarantee.report.context.lookup_anchor_slot
            setattr(lookup_header, "_hash", guarantee.report.context.lookup_anchor)
            self.app_context.state_storage.add_ancestor(lookup_header)
            # The component corpus delegates ancestor-chain validation to the
            # caller. Supply a child commitment for its declared lookup root.
            lookup_child = Header.default()
            lookup_child.parent = lookup_header.hash
            lookup_child.parent_state_root = guarantee.report.context.lookup_anchor_state_root
            lookup_child.timeslot = lookup_header.timeslot + 1
            self.app_context.state_storage.add_ancestor(lookup_child)

        post_entropy = EntropyState.from_json({"entropy": test_vector["pre_state"]["entropy"]})

        post_disputes = DisputesState.from_json({
            "good_set": [],
            "bad_set": [],
            "wonky_set": [],
            "offenders": test_vector["pre_state"]["offenders"]
        })

        # Prepare block context
        self.block_context.reset()
        self.block_context.set_guarantor_assignments(
            post_entropy=post_entropy,
            post_timeslot=post_state_timeslot,
            post_validator_pool=post_state_validator_pool
        )
        self.block_context.set_prev_guarantor_assignments(
            post_entropy=post_entropy,
            post_timeslot=post_state_timeslot,
            post_validator_pool=post_state_validator_pool,
            post_validator_archive=post_state_validator_archive
        )


        assurances = Assurances(self.block_context, self.app_context)
        try:
            assurances.validate_guarantees(
                extrinsic_guarantees=extrinsic_guarantees,
                pre_services_state=pre_services,
                intermediate_state_recent_history=intermediate_state_recent_history,
                pre_authorizer_pools=pre_authorizer_pools,
                intermediate_state_assurances_after_assurances=pre_state_assurances,
                post_state_validator_pool=post_state_validator_pool,
                header=header,
                pre_accumulation_history=pre_accumulation_history,
                pre_accumulation_queue=pre_accumulation_queue,
                post_entropy=post_entropy,
                post_state_timeslot=post_state_timeslot,
                post_state_validator_archive=post_state_validator_archive,
                post_state_disputes=post_disputes,
            )

            output = assurances.state_transition_after_guarantees(
                extrinsic_guarantees=extrinsic_guarantees,
                intermediate_state_assurances_after_assurances=pre_state_assurances,
                pre_state_validator_pool=post_state_validator_pool,
                post_state_timeslot=post_state_timeslot
            )
            assurances_output = {
                'ok': {
                    'reported': output.to_json()['reported'],
                    'reporters': output.to_json()['reporters']
                }
            }
            post_state = output.post_state.to_json()

            # Reformat JSON output confirm test format
            for idx, assignment in enumerate(post_state['assurances']):
                if post_state['assurances'][idx]:
                    post_state['assurances'][idx]["guarantee"]["report"]["segment_root_lookup"] = [{
                        "segment_tree_root": sr, "work_package_hash": wh
                    } for wh, sr in post_state['assurances'][idx]["guarantee"]["report"]["segment_root_lookup"]]

        except StateTransitionError as e:
            assurances_output = {'err': e.custom_error_code.name}
            post_state = {
                "assurances": test_vector['pre_state']['avail_assignments'],
            }

        self.assertDictEqual(test_vector['output'], assurances_output)

        self.assertListEqual(
            test_vector['post_state']['avail_assignments'], post_state['assurances'], f'{name} fails'
        )

    def authorization_gas_vector(self, gas_amounts):
        filename = 'multiple_reports-1.json' if len(gas_amounts) > 1 else 'report_curr_rotation-1.json'
        vector = self.load_test_vector_data(filename)
        for guarantee, gas_used in zip(vector['input']['guarantees'], gas_amounts, strict=True):
            guarantee['report']['auth_gas_used'] = gas_used
        self.resign_guarantees(vector)
        return vector

    def resign_guarantees(self, vector, *, align_export_counts=True):
        reporters = set()
        for guarantee in vector['input']['guarantees']:
            if align_export_counts:
                total = sum(result['refine_load']['exports'] for result in guarantee['report']['results'])
                # Synthetic boundary tests use coherent availability counts.
                # Oversized load tests still need an encodable u16 field.
                if total <= 2**16 - 1:
                    guarantee['report']['package_spec']['exports_count'] = total
            report = WorkReport.from_json(reformat_work_report(deepcopy(guarantee['report'])))
            message = b'jam_guarantee' + blake2b_256_hash(report.to_jam_bytes().to_bytes())
            for credential in guarantee['signatures']:
                index = credential['validator_index']
                key = Ed25519Keypair.from_seed(blake2b_256_hash(b'auth-gas-test' + index.to_bytes(4, 'little')))
                public_key = '0x' + key.public_key.hex()
                vector['pre_state']['curr_validators'][index]['ed25519'] = public_key
                credential['signature'] = '0x' + key.sign(message).hex()
                reporters.add(public_key)
            vector['post_state']['avail_assignments'][report.core_index]['guarantee'] = deepcopy(guarantee)
        vector['output']['ok']['reporters'] = sorted(reporters)

    @parameterized.expand([
        ('zero', [0], False),
        ('below_budget', [GAS_INVOKE - 1], False),
        ('exact_budget', [GAS_INVOKE], False),
        ('above_budget', [GAS_INVOKE + 1], True),
        ('uint64_max', [2**64 - 1], True),
        ('independent_reports', [GAS_INVOKE, GAS_INVOKE], False),
        ('second_report_above_budget', [GAS_INVOKE, GAS_INVOKE + 1], True),
    ])
    def test_authorization_gas_limit(self, name, gas_amounts, rejected):
        vector = self.authorization_gas_vector(gas_amounts)
        if rejected:
            vector['output'] = {'err': 'authorizer_gas_too_high'}
            vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        self.check_vector(name, vector)

    def check_refinement_load_vector(self, loads_by_report, rejected, *, failed=False):
        filename = 'multiple_reports-1.json' if len(loads_by_report) > 1 else 'report_curr_rotation-1.json'
        vector = self.load_test_vector_data(filename)
        fields = ('gas_used', 'imports', 'exports', 'extrinsic_count', 'extrinsic_size')
        for guarantee, loads in zip(vector['input']['guarantees'], loads_by_report, strict=True):
            original = guarantee['report']['results'][0]
            guarantee['report']['results'] = []
            for load in loads:
                digest = deepcopy(original)
                digest['refine_load'] = {field: load.get(field, 0) for field in fields}
                if failed:
                    digest['result'] = {'out_of_gas': None}
                guarantee['report']['results'].append(digest)
        self.resign_guarantees(vector)
        if rejected:
            vector['output'] = {'err': 'refine_load_too_high'}
            vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        self.check_vector('refinement load', vector)

    @parameterized.expand([
        ('zero', [[{}]], False),
        ('gas_below_limit', [[{'gas_used': gp_const.GAS_REFINE - 1}]], False),
        ('gas_at_limit', [[{'gas_used': gp_const.GAS_REFINE}]], False),
        ('gas_above_limit', [[{'gas_used': gp_const.GAS_REFINE + 1}]], True),
        ('gas_split_at_limit', [[{'gas_used': gp_const.GAS_REFINE - 1}, {'gas_used': 1}]], False),
        ('gas_split_above_limit', [[{'gas_used': gp_const.GAS_REFINE - 1}, {'gas_used': 2}]], True),
        ('imports_at_limit', [[{'imports': 3072}]], False),
        ('imports_above_limit', [[{'imports': 3073}]], True),
        ('imports_split_above_limit', [[{'imports': 1536}, {'imports': 1537}]], True),
        ('exports_at_limit', [[{'exports': 3072}]], False),
        ('exports_above_limit', [[{'exports': 3073}]], True),
        ('exports_split_above_limit', [[{'exports': 1536}, {'exports': 1537}]], True),
        ('extrinsic_count_at_limit', [[{'extrinsic_count': 128}]], False),
        ('extrinsic_count_above_limit', [[{'extrinsic_count': 129}]], True),
        ('extrinsic_count_split_above_limit', [[{'extrinsic_count': 64}, {'extrinsic_count': 65}]], True),
        ('extrinsic_size_at_limit', [[{'extrinsic_size': 13791360}]], False),
        ('extrinsic_size_above_limit', [[{'extrinsic_size': 13791361}]], True),
        ('extrinsic_size_split_above_limit', [[{'extrinsic_size': 13791360}, {'extrinsic_size': 1}]], True),
        ('footprint_at_limit', [[{'imports': 3072, 'extrinsic_size': 4224}]], False),
        ('footprint_above_limit', [[{'imports': 3072, 'extrinsic_size': 4225}]], True),
        ('footprint_split_above_limit', [[{'imports': 3072}, {'extrinsic_size': 4225}]], True),
        ('independent_reports', [[{'gas_used': gp_const.GAS_REFINE - 1, 'imports': 3072, 'exports': 3072,
                                   'extrinsic_count': 128, 'extrinsic_size': 4224}]] * 2, False),
        ('second_report_above_limit', [[{}], [{'imports': 3073}]], True),
    ])
    def test_refinement_load_limits(self, name, loads_by_report, rejected):
        self.check_refinement_load_vector(loads_by_report, rejected)

    @parameterized.expand([(field,) for field in
                           ('gas_used', 'imports', 'exports', 'extrinsic_count', 'extrinsic_size')])
    def test_refinement_load_sums_do_not_wrap_uint64(self, field):
        self.check_refinement_load_vector([[{field: 2**64 - 1}, {field: 1}]], rejected=True)

    @parameterized.expand([(False,), (True,)])
    def test_refinement_load_includes_failed_results(self, rejected):
        self.check_refinement_load_vector([[{'imports': 3073 if rejected else 1,
                                            'gas_used': gp_const.GAS_REFINE - 1}]], rejected, failed=True)

    def test_refinement_gas_at_limit_is_accepted_for_failed_results(self):
        self.check_refinement_load_vector([[{'gas_used': gp_const.GAS_REFINE}]], rejected=False, failed=True)

    def check_bundle_length_vector(self, lengths, rejected):
        filename = 'multiple_reports-1.json' if len(lengths) > 1 else 'report_curr_rotation-1.json'
        vector = self.load_test_vector_data(filename)
        for guarantee, length in zip(vector['input']['guarantees'], lengths, strict=True):
            guarantee['report']['package_spec']['length'] = length
        self.resign_guarantees(vector)
        if rejected:
            vector['output'] = {'err': 'bundle_length_too_high'}
            vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        self.check_vector('auditable bundle length', vector)

    @parameterized.expand([
        ('zero', [0], False),
        ('footprint_limit', [13791360], False),
        ('serialized_limit', [13904950], False),
        ('above_limit', [13904951], True),
        ('uint32_max', [2**32 - 1], True),
        ('independent_reports', [13904950, 13904950], False),
        ('second_report_above_limit', [17180, 13904951], True),
    ])
    def test_bundle_length_limit(self, name, lengths, rejected):
        self.check_bundle_length_vector(lengths, rejected)

    def bundle_length_test_package(self, items, *, authorization=b'', config=b'', prerequisites=()):
        vector = self.load_test_vector_data('report_curr_rotation-1.json')
        context = RefinementContext.from_json(vector['input']['guarantees'][0]['report']['context'])
        context.prerequisites = list(prerequisites)
        return WorkPackage(auth_code_host=42, auth_code_hash=bytes(32), context=context,
                           authorization=authorization, authorizer_config=config, items=items)

    def test_bundle_length_allows_serialization_above_footprint_limit(self):
        item = WorkItem(service=42, code_hash=bytes(32), refine_gas_limit=1, accumulate_gas_limit=1,
                        export_count=0, payload=bytes(gp_const.MAXIMUM_SIZE_WORK_PACKAGE),
                        import_segments=[], extrinsic=[])
        package = self.bundle_length_test_package([item])
        # With no imported/extrinsic content, GP-0.8.0-eq:14.16 is just E(package).
        length = package.to_jam_bytes().length
        self.assertEqual(length, gp_const.MAXIMUM_SIZE_WORK_PACKAGE + 268)
        self.check_bundle_length_vector([length], rejected=False)

    def test_bundle_length_allows_maximal_manifest_overhead(self):
        items = [WorkItem(service=42, code_hash=bytes(32), refine_gas_limit=1, accumulate_gas_limit=1,
                          export_count=0, payload=bytes(248),
                          import_segments=[ImportSegment.from_segment_root(bytes(32), 0)] * 192,
                          extrinsic=[]) for _ in range(16)]
        items[0].extrinsic = [WorkItemExtrinsic.from_blob(b'')] * 128
        package = self.bundle_length_test_package(items, authorization=bytes(128), config=bytes(128),
                                                 prerequisites=[bytes([i]) * 32 for i in range(8)])
        self.assertEqual(16 * 248 + 128 + 128 + 3072 * 4488, gp_const.MAXIMUM_SIZE_WORK_PACKAGE)
        # GP-0.8.0-eq:14.16 appends raw segments and 12-hash paths, each with one
        # length byte. Empty extrinsic bodies add no bytes to the bundle.
        length = package.to_jam_bytes().length + 3072 * (4104 + 1 + 12 * 32)
        self.assertEqual(length, 13904899)
        self.check_bundle_length_vector([length], rejected=False)

    @parameterized.expand([
        ('zero', [0], [[0]], False, False),
        ('sum', [3], [[1, 2]], False, False),
        ('too_few', [2], [[1, 2]], True, False),
        ('too_many', [4], [[1, 2]], True, False),
        ('trace_count_two', [2], [[0, 0, 0]], True, False),
        ('trace_count_uint16_max', [65535], [[0, 0]], True, False),
        ('trace_count_at_limit', [3072], [[0, 0, 0, 0]], True, False),
        ('matched_at_limit', [3072], [[1536, 1536]], False, False),
        ('independent_reports', [2, 3], [[1, 1], [1, 2]], False, False),
        ('opposite_mismatches_do_not_cancel', [2, 3], [[1], [4]], True, False),
        ('second_report', [0, 2], [[0], [0]], True, False),
        ('failed_result_counted', [2], [[2]], False, True),
        ('failed_result_mismatch', [2], [[0]], True, True),
    ])
    def test_export_count_matches_digests(self, name, counts, exports_by_report, rejected, failed):
        filename = 'multiple_reports-1.json' if len(counts) > 1 else 'report_curr_rotation-1.json'
        vector = self.load_test_vector_data(filename)
        for guarantee, count, exports in zip(vector['input']['guarantees'], counts, exports_by_report, strict=True):
            report = guarantee['report']
            original = report['results'][0]
            report['package_spec']['exports_count'] = count
            report['results'] = []
            for exported in exports:
                digest = deepcopy(original)
                digest['refine_load']['exports'] = exported
                if failed:
                    digest['result'] = {'panic': None}
                report['results'].append(digest)
        self.resign_guarantees(vector, align_export_counts=False)
        if rejected:
            vector['output'] = {'err': 'exports_count_mismatch'}
            vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        self.check_vector(name, vector)

    def test_missing_lookup_ancestry_is_rejected_by_default(self):
        vector = self.load_test_vector_data('report_curr_rotation-1.json')
        vector['output'] = {'err': 'lookup_anchor_not_recent'}
        vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        self.check_vector('missing lookup ancestry', vector, retain_ancestry=False)

    def test_fuzzer_without_ancestry_still_rejects_expired_lookup(self):
        vector = self.load_test_vector_data('report_curr_rotation-1.json')
        lookup_slot = vector['input']['guarantees'][0]['report']['context']['lookup_anchor_slot']
        vector['input']['slot'] = lookup_slot + MAXIMUM_AGE_LOOKUP_ANCHOR + 1
        vector['output'] = {'err': 'anchor_not_recent'}
        vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        override = self.app_context.skip_lookup_anchor_ancestry
        token = override.set(True)
        try:
            self.check_vector('expired lookup ancestry', vector, retain_ancestry=False)
        finally:
            override.reset(token)

    @parameterized.expand([
        ('report_curr_rotation-1.json',),
        ('anchor_not_recent-1.json',),
        ('bad_anchor_slot-1.json',),
        ('bad_state_root-1.json',),
        ('bad_beefy_mmr-1.json',),
    ])
    def test_fuzzer_without_ancestry_keeps_other_report_checks(self, test_file):
        vector = self.load_test_vector_data(test_file)
        if 'ok' in vector['output']:
            self.resign_guarantees(vector)
        override = self.app_context.skip_lookup_anchor_ancestry
        token = override.set(True)
        try:
            self.check_vector(test_file, vector, retain_ancestry=False)
        finally:
            override.reset(token)


if __name__ == '__main__':
    unittest.main()
