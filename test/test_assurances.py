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
from pyjamaz.models.block import Header, Assurance, BlockContext
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
        cls.storage_engine = InMemoryStorage()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'assurances', TEST_SUITE, test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

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

        assurances = Assurances(self.storage_engine, block_context, app_context)
        try:

            assurances.validate_after_disputes(
                extrinsic_assurances=extrinsic_assurances,
                pre_state_validator_pool=pre_state_validator_pool,
                header=header,
            )

            intermediate_output = assurances.state_transition_after_assurances(
                extrinsic_assurances=extrinsic_assurances,
                intermediate_state_assurances_after_disputes=pre_state_assurances
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


if __name__ == '__main__':
    unittest.main()
