import json
import os
import unittest
from os import path
from typing import Optional

from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.settings import TEST_SUITE
from pyjamaz.state.base import AppContext
from pyjamaz.state.components import Assurances
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Guarantee, BlockContext, Extrinsic, ExtrinsicDisputes
from pyjamaz.models.state import AssurancesState, ValidatorPoolState, ValidatorArchiveState, TimeslotState, \
    ServicesState, RecentHistoryState, AuthorizerPoolsState, AccumulationHistoryState, EntropyState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'reports', TEST_SUITE)
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
        cls.storage_engine = InMemoryStorage()
        cls.block_context = BlockContext()
        cls.app_context = AppContext()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'reports', TEST_SUITE, test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

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

        pre_services = ServicesState.from_json(
            {"services": {s["id"]: {
                "code_hash": bytes.fromhex(s["data"]["service"]["code_hash"][2:]),
                "balance": s["data"]["service"]["balance"],
                "gas_limit_accumulate": s["data"]["service"]["min_item_gas"],
                "gas_limit_on_transfer": s["data"]["service"]["min_memo_gas"],
                "footprint_storage_items": s["data"]["service"]["items"],
                "footprint_storage_bytes": s["data"]["service"]["bytes"],
                "threshold_balance": 0,
                "storage_items": {},
                "preimages": {},
                "preimage_availability": {}

            } for s in test_vector["pre_state"]["accounts"]}}
        )

        pre_services.set_storage_engine(self.storage_engine)

        intermediate_state_recent_history = RecentHistoryState.from_json(
            {"recent_history": test_vector["pre_state"]["recent_blocks"]}
        )

        pre_authorizer_pools = AuthorizerPoolsState.from_json(
            {"authorizer_pools": test_vector["pre_state"]["auth_pools"]}
        )

        pre_accumulation_history = AccumulationHistoryState(accumulation_history=[])

        post_entropy = EntropyState.from_json({"entropy": test_vector["pre_state"]["entropy"]})

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


        assurances = Assurances(self.storage_engine, self.block_context, self.app_context)
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
                post_entropy=post_entropy,
                post_state_timeslot=post_state_timeslot,
                post_state_validator_archive=post_state_validator_archive
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
                    post_state['assurances'][idx]["report"]["segment_root_lookup"] = [{
                        "segment_tree_root": sr, "work_package_hash": wh
                    } for wh, sr in post_state['assurances'][idx]["report"]["segment_root_lookup"]]

        except StateTransitionError as e:
            assurances_output = {'err': e.custom_error_code.name}
            post_state = {
                "assurances": test_vector['pre_state']['avail_assignments'],
            }

        self.assertDictEqual(test_vector['output'], assurances_output)

        self.assertListEqual(
            test_vector['post_state']['avail_assignments'], post_state['assurances'], f'{name} fails'
        )


if __name__ == '__main__':
    unittest.main()
