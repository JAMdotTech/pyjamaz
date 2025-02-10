import os

from parameterized import parameterized

from typing import Optional

from dataclasses import dataclass

import json
import unittest
from os import path

from pyjamaz.app import AppConfig
from pyjamaz.exceptions import PyjamazAppError
from pyjamaz.settings import TEST_SUITE
from pyjamaz.state.base import AppContext
from pyjamaz.state.components import Disputes
from pyjamaz.storage import InMemoryStorage

from pyjamaz.models.block import Header, Extrinsic, ExtrinsicDisputes, Block, BlockContext
from pyjamaz.models.state import (DisputesState, AssurancesState, TimeslotState, ValidatorArchiveState,
                                  ValidatorPoolState, JamState, State)


@dataclass
class TestState(State):
    timeslot: TimeslotState
    disputes: DisputesState
    validator_pool: ValidatorPoolState
    validator_archive: ValidatorArchiveState
    assurances: AssurancesState


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'disputes'), directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestDisputes(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):

        cls.test_vector_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'disputes')

        # Set up ring data
        data_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'pyjamaz', 'data')
        with open(path.join(data_dir, 'zcash-srs-2-11-uncompressed.bin'), 'rb') as fp:
            cls.ring_data = fp.read()

        cls.config = AppConfig(
            ring_data=cls.ring_data,
            storage_engine=InMemoryStorage(),
            common_era=0
        )

    @staticmethod
    def create_block(test_vector_input: dict) -> Block:

        extrinsic = Extrinsic(
            tickets=[],
            disputes=ExtrinsicDisputes.from_json(test_vector_input['disputes']),
            preimages=[],
            assurances=[],
            guarantees=[]
        )

        return Block(
            header=Header(
                parent=bytes(32),
                parent_state_root=bytes(32),
                extrinsic_hash=extrinsic.generate_extrinsic_hash(),
                timeslot=0,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                author_index=0,
                entropy_source=bytes(96),
                seal=bytes(96)
            ),
            extrinsic=extrinsic
        )

    @staticmethod
    def create_jam_state(test_vector: dict) -> JamState:

        jam_state = JamState.create_genesis_state()
        jam_state.timeslot.number = test_vector['tau']
        jam_state.validator_pool = ValidatorPoolState.from_json({"validators": test_vector['kappa']})
        jam_state.validator_archive = ValidatorArchiveState.from_json({"validators": test_vector['lambda']})
        jam_state.disputes = DisputesState(
            good_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['good']],
            bad_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['bad']],
            wonky_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['wonky']],
            offenders=[bytes.fromhex(i[2:]) for i in test_vector['psi']['offenders']],
        )

        return jam_state

    @parameterized.expand(get_test_vector_files([TEST_SUITE], file_filter=''))
    async def test_vector(self, name, directory, test_file):
        with open(path.join(self.test_vector_dir, directory, test_file)) as f:
            test_vector = json.load(f)

        pre_state = self.create_jam_state(test_vector['pre_state'])

        block = self.create_block(test_vector['input'])

        # Process block
        try:
            disputes = Disputes(InMemoryStorage(), BlockContext(), AppContext())

            # Input validation
            disputes.validate_extrinsic_disputes(
                extrinsic_disputes=block.extrinsic.disputes,
                pre_state_timeslot=pre_state.timeslot,
                pre_state_validator_pool=pre_state.validator_pool,
                pre_state_validator_archive=pre_state.validator_archive
            )

            # STF
            output = disputes.state_transition(
                extrinsic_disputes=block.extrinsic.disputes,
                pre_state_disputes=pre_state.disputes
            )
            dispute_output = {'ok': {"offenders_mark": output.to_json()['offenders_mark']}}
            psi = output.post_state.to_json()
        except PyjamazAppError as e:
            dispute_output = {'err': e.custom_error_code.name}
            psi = pre_state.disputes.to_json()

        self.assertEqual(test_vector['output'], dispute_output)

        post_state = {
            'bad': psi['bad_set'],
            'good': psi['good_set'],
            'offenders': psi['offenders'],
            'wonky': psi['wonky_set'],
        }

        self.assertDictEqual(test_vector['post_state']['psi'], post_state)


if __name__ == '__main__':
    unittest.main()
