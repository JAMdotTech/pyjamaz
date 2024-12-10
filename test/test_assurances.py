import json
import os
import unittest
from os import path
from typing import Optional

from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.state.components import Assurances
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Assurance
from pyjamaz.models.state import AssurancesState, ValidatorPoolState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'assurances', 'tiny')
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
            path.dirname(path.abspath(__file__)), 'fixtures', 'assurances', 'tiny', test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]
        header.parent = test_vector["input"]["parent"]

        extrinsic_assurances = [Assurance.from_json(a) for a in test_vector["input"]["assurances"]]
        pre_state_assurances = AssurancesState.from_json({"assurances": test_vector["pre_state"]["avail_assignments"]})
        post_state_validator_pool = ValidatorPoolState.from_json(
            {"validators": test_vector["pre_state"]["curr_validators"]}
        )

        assurances = Assurances(self.storage_engine)
        try:
            output = assurances.state_transition_after_assurances(
                extrinsic_assurances=extrinsic_assurances,
                intermediate_state_assurances_after_disputes=pre_state_assurances,
                post_state_validator_pool=post_state_validator_pool
            )
            assurances_output = {'ok': {'reported': output.to_json()['reported']}}
            post_state = output.intermediate_state_after_assurances.to_json()
        except StateTransitionError as e:
            assurances_output = {'err': e.custom_error_code.name}
            post_state = {
                "assurances": test_vector['pre_state']['avail_assignments'],
            }

        self.assertEqual(test_vector['output'], assurances_output)

        self.assertListEqual(
            test_vector['post_state']['avail_assignments'], post_state['assurances'], f'{name} fails'
        )


if __name__ == '__main__':
    unittest.main()
