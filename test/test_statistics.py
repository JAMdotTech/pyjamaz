import json
import os
import unittest
from os import path
from typing import Optional

from parameterized import parameterized

from pyjamaz.settings import TEST_SUITE
from pyjamaz.state.base import AppContext
from pyjamaz.state.components import Statistics
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Extrinsic, BlockContext
from pyjamaz.models.state import StatisticsState, TimeslotState, ValidatorPoolState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'statistics', TEST_SUITE)
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestStatistics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.storage_engine = InMemoryStorage()
        cls.block_context = BlockContext()
        cls.app_context = AppContext()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'statistics', TEST_SUITE, test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]
        header.author_index = test_vector["input"]["author_index"]

        extrinsic = Extrinsic.from_json(test_vector["input"]["extrinsic"])

        pre_state_statistics = StatisticsState.from_json(test_vector["pre_state"]["statistics"])

        pre_state_timeslot = TimeslotState(number=test_vector["pre_state"]["slot"])
        post_state_timeslot = TimeslotState(number=test_vector["post_state"]["slot"])
        post_state_validator_pool = ValidatorPoolState.from_json({"validators": test_vector["post_state"]["curr_validators"]})

        statistics = Statistics(self.storage_engine, self.block_context, self.app_context)

        self.block_context.reporters = []
        self.block_context.accumulation_statistics = {}
        self.block_context.deferred_transfer_statistics = {}

        for guarantee in extrinsic.guarantees:
            for signature in guarantee.signatures:
                self.block_context.reporters.append(
                    post_state_validator_pool.validators[signature.validator_index].ed25519
                )

        output = statistics.state_transition(
            extrinsic_guarantees=extrinsic.guarantees,
            extrinsic_preimages=extrinsic.preimages,
            extrinsic_assurances=extrinsic.assurances,
            extrinsic_tickets=extrinsic.tickets,
            pre_state_timeslot=pre_state_timeslot,
            post_state_timeslot=post_state_timeslot,
            post_state_validator_pool=post_state_validator_pool,
            pre_state_statistics=pre_state_statistics,
            header=header
        )

        output_json =output.post_state.to_json()

        # TODO temp stats output mod until: https://github.com/davxy/jam-test-vectors/issues/39
        output_json['services']= []

        self.assertDictEqual(
            test_vector['post_state']['statistics'], output_json, f'{name} fails'
        )


if __name__ == '__main__':
    unittest.main()
