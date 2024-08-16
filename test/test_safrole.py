import json
import os
import unittest
from copy import deepcopy
from dataclasses import dataclass
from os import path
from typing import Optional

from parameterized import parameterized

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.mixins import SerializableMixin
from pyjamaz.state.managers import Timeslot, Entropy, ValidatorArchive, ValidatorPool, Safrole, ValidatorQueue
from pyjamaz.storage import JSONStorage, RocksDBStorage
from pyjamaz.types.safrole import State, Input, Output
from pyjamaz.types.block import Block, Header, Extrinsic
from pyjamaz.types.state import JamState, TimeslotState, EntropyState, SafroleState, ValidatorQueueState, \
    ValidatorPoolState, ValidatorArchiveState


@dataclass
class Testcase(SerializableMixin):
    input: Input  # Input.
    pre_state: State  # Pre-execution state.
    output: Output  # Output.
    post_state: State  # Post-execution state.


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestSafroleVector(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up ring data
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'pyjamaz', 'data')
        with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
            cls.ring_data = fp.read()

        cls.config = AppConfig(
            ring_data=cls.ring_data,
            storage_engine=RocksDBStorage("../data/db")
            # storage_engine=JSONStorage("../data/storage.json")
        )

    @staticmethod
    def load_test_vector_data(directory, test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory, test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    def test_vector(self, name, directory, test_file):

        test_vector = self.load_test_vector_data(directory, test_file)
        test_case = Testcase.deserialize(test_vector)

        # TODO make type factory to bootstrap state SCALE types with correct constants
        # if directory == 'tiny':
        #     gp_const.VALIDATOR_COUNT = 6
        #     gp_const.EPOCH_TIMESLOTS = 12
        #     gp_const.TICKET_SUBMISSION_END_SLOT = 10
        # else:
        #     gp_const.VALIDATOR_COUNT = 1023
        #     gp_const.EPOCH_TIMESLOTS = 600
        #     gp_const.TICKET_SUBMISSION_END_SLOT = 500

        # Build initial state
        jam_state = JamState(
            timeslot=TimeslotState(
                number=test_case.pre_state.tau
            ),
            entropy=EntropyState(
                entropy=test_case.pre_state.eta
            ),
            safrole=SafroleState(
                ticket_accumulator=test_case.pre_state.gamma_a,
                validators=test_case.pre_state.gamma_k,
                slot_sealer_series=test_case.pre_state.gamma_s,
                ring_commitment=test_case.pre_state.gamma_z,
            ),
            validator_queue=ValidatorQueueState(
                validators=test_case.pre_state.iota
            ),
            validator_pool=ValidatorPoolState(
                validators=test_case.pre_state.kappa
            ),
            validator_archive=ValidatorArchiveState(
                validators=test_case.pre_state.lambda_
            )
        )

        # Convert test case input to block
        test_case_input = deepcopy(test_case.input)

        block = Block(
            header=Header(
                timeslot=test_case_input.slot,
                vrf_signature=test_case_input.entropy
            ),
            extrinsic=Extrinsic(
                tickets=test_case_input.extrinsic
            )
        )

        # Initialize app
        app = PyjamazApp(config=self.config)
        app.init_state(jam_state)

        # Process block
        result = app.process_block(block)
        output = result[0]

        self.assertEqual(test_case.output, output, f'{name}: output does not match')
        self.assertEqual(test_case.post_state.tau, app.get_state(Timeslot).number, f'{name}:tau does not match')
        self.assertEqual(test_case.post_state.eta, app.get_state(Entropy).entropy, f'{name}: eta does not match')
        self.assertEqual(test_case.post_state.lambda_, app.get_state(ValidatorArchive).validators, f'{name}: lambda_ does not match')
        self.assertEqual(test_case.post_state.kappa, app.get_state(ValidatorPool).validators, f'{name}: kappa does not match')
        self.assertEqual(test_case.post_state.gamma_k, app.get_state(Safrole).validators, f'{name}: gamma_k does not match')
        self.assertEqual(test_case.post_state.iota, app.get_state(ValidatorQueue).validators, f'{name}: iota does not match')
        self.assertEqual(test_case.post_state.gamma_a, app.get_state(Safrole).ticket_accumulator, f'{name}: gamma_a does not match')
        self.assertEqual(test_case.post_state.gamma_s, app.get_state(Safrole).slot_sealer_series, f'{name}: gamma_s does not match')
        self.assertEqual(test_case.post_state.gamma_z, app.get_state(Safrole).ring_commitment, f'{name}: gamma_z does not match')


if __name__ == '__main__':
    unittest.main()
