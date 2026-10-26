import json
import os
import unittest
from copy import deepcopy
from os import path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch

from parameterized import parameterized

import pyjamaz.settings as settings
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.models.block import Header, Guarantee, Extrinsic, ExtrinsicDisputes
from pyjamaz.models.common import WorkReport
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
        reporters = set()
        for guarantee, gas_used in zip(vector['input']['guarantees'], gas_amounts, strict=True):
            guarantee['report']['auth_gas_used'] = gas_used
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
        return vector

    @parameterized.expand([
        ('zero', [0], True, '0.8.0', False),
        ('below_budget', [GAS_INVOKE - 1], True, '0.8.0', False),
        ('exact_budget', [GAS_INVOKE], True, '0.8.0', False),
        ('above_budget', [GAS_INVOKE + 1], True, '0.8.0', True),
        ('uint64_max', [2**64 - 1], True, '0.8.0', True),
        ('independent_reports', [GAS_INVOKE, GAS_INVOKE], True, '0.8.0', False),
        ('second_report_above_budget', [GAS_INVOKE, GAS_INVOKE + 1], True, '0.8.0', True),
        ('compat_disabled', [2**64 - 1], False, '0.8.0', False),
        ('other_gp_version', [GAS_INVOKE + 1], True, '0.7.2', False),
    ])
    def test_authorization_gas_limit(self, name, gas_amounts, compatibility, gp_version, rejected):
        vector = self.authorization_gas_vector(gas_amounts)
        if rejected:
            vector['output'] = {'err': 'authorizer_gas_too_high'}
            vector['post_state']['avail_assignments'] = vector['pre_state']['avail_assignments']
        with patch.object(settings, 'GP080_AUTH_GAS_LIMIT_COMPAT', compatibility), \
                patch.object(settings, 'GP_VERSION', gp_version):
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
        override = self.app_context.skip_lookup_anchor_ancestry
        token = override.set(True)
        try:
            self.check_vector(test_file, vector, retain_ancestry=False)
        finally:
            override.reset(token)


if __name__ == '__main__':
    unittest.main()
