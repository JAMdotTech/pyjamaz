import json
import os
import unittest
from os import path
from math import floor
from typing import Optional

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.settings import TEST_SUITE
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.common import WorkReport, WorkPackageSpec, RefinementContext, Assurance as AssuranceStateItem
from pyjamaz.models.block import ExtrinsicDisputes, Verdict, Judgement
from pyjamaz.state.components import Assurances
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.models.block import Header, Assurance
from pyjamaz.models.state import AssurancesState, ValidatorPoolState, TimeslotState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'assurances', TEST_SUITE)
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestAssurances(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.storage_engine = InMemoryStorageEngine()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'assurances', TEST_SUITE, test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @staticmethod
    def create_work_report(core_index: int) -> WorkReport:
        return WorkReport(
            package_spec=WorkPackageSpec(
                hash=bytes([core_index + 1]) * 32,
                length=0,
                erasure_root=bytes([core_index + 2]) * 32,
                exports_root=bytes([core_index + 3]) * 32,
                exports_count=0,
            ),
            context=RefinementContext(
                anchor=bytes(32),
                state_root=bytes(32),
                beefy_root=bytes(32),
                lookup_anchor=bytes(32),
                lookup_anchor_slot=0,
                prerequisites=[],
            ),
            core_index=core_index,
            authorizer_hash=bytes([core_index + 4]) * 32,
            auth_gas_used=0,
            auth_output=b'',
            segment_root_lookup={},
            results=[],
        )

    @staticmethod
    def create_verdict(target: bytes, positive_votes: int) -> Verdict:
        total_votes = 1 + floor(gp_const.VALIDATOR_COUNT / 3) * 2
        votes = [
            Judgement(vote=index < positive_votes, index=index, signature=bytes(64))
            for index in range(total_votes)
        ]
        return Verdict(target=target, age=0, votes=votes)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]
        header.parent = bytes.fromhex(test_vector["input"]["parent"][2:])

        extrinsic_assurances = [Assurance.from_json(a) for a in test_vector["input"]["assurances"]]
        pre_state_assurances = AssurancesState.from_json({"assurances": test_vector["pre_state"]["avail_assignments"]})
        pre_state_validator_pool = ValidatorPoolState.from_json(
            {"validators": test_vector["pre_state"]["curr_validators"]}
        )

        post_state_timeslot = TimeslotState(number=header.timeslot)

        # Prepare block context
        block_context = BlockContext()
        block_context.reset()
        app_context = AppContext()

        assurances = Assurances(block_context, app_context)
        try:

            assurances.validate_after_disputes(
                extrinsic_assurances=extrinsic_assurances,
                pre_state_validator_pool=pre_state_validator_pool,
                header=header,
            )

            intermediate_output = assurances.state_transition_after_assurances(
                extrinsic_assurances=extrinsic_assurances,
                intermediate_state_assurances_after_disputes=pre_state_assurances,
                header=header
            )

            output = assurances.state_transition_after_guarantees(
                extrinsic_guarantees=[],
                intermediate_state_assurances_after_assurances=intermediate_output.intermediate_state_after_assurances,
                post_state_timeslot=post_state_timeslot,
                pre_state_validator_pool=pre_state_validator_pool
            )


            assurances_output = {'ok': {'reported': intermediate_output.to_json()['reported']}}
            post_state = output.post_state.to_json()
        except StateTransitionError as e:
            assurances_output = {'err': e.custom_error_code.name}
            post_state = {
                "assurances": test_vector['pre_state']['avail_assignments'],
            }

        self.assertDictEqual(test_vector['output'], assurances_output)

        self.assertListEqual(
            test_vector['post_state']['avail_assignments'], post_state['assurances'], f'{name} fails'
        )

    def test_state_transition_after_disputes_clears_bad_verdict_targets(self):
        disputed_report = self.create_work_report(core_index=0)
        untouched_report = self.create_work_report(core_index=1)
        pre_state_assurances = AssurancesState(
            assurances=[
                AssuranceStateItem(report=disputed_report, timeout=3),
                AssuranceStateItem(report=untouched_report, timeout=4),
            ]
        )
        disputes = ExtrinsicDisputes(
            verdicts=[self.create_verdict(disputed_report.hash(), positive_votes=0)],
            culprits=[],
            faults=[],
        )

        output = Assurances(BlockContext(), AppContext()).state_transition_after_disputes(
            extrinsic_disputes=disputes,
            pre_state_assurances=pre_state_assurances,
        )

        self.assertIsNone(output.intermediate_state_after_disputes.assurances[0])
        self.assertIsNotNone(output.intermediate_state_after_disputes.assurances[1])
        self.assertIsNotNone(pre_state_assurances.assurances[0])

    def test_state_transition_after_disputes_keeps_positive_verdict_targets(self):
        preserved_report = self.create_work_report(core_index=0)
        pre_state_assurances = AssurancesState(
            assurances=[
                AssuranceStateItem(report=preserved_report, timeout=3),
                None,
            ]
        )
        disputes = ExtrinsicDisputes(
            verdicts=[
                self.create_verdict(
                    preserved_report.hash(),
                    positive_votes=floor(gp_const.VALIDATOR_COUNT * 2 / 3) + 1,
                )
            ],
            culprits=[],
            faults=[],
        )

        output = Assurances(BlockContext(), AppContext()).state_transition_after_disputes(
            extrinsic_disputes=disputes,
            pre_state_assurances=pre_state_assurances,
        )

        self.assertIsNotNone(output.intermediate_state_after_disputes.assurances[0])


if __name__ == '__main__':
    unittest.main()
