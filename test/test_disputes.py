import os

from parameterized import parameterized

from typing import Optional

from dataclasses import dataclass

import json
import unittest
from os import path

from pyjamaz.app import PyjamazApp, AppConfig
from pyjamaz.exceptions import PyjamazAppError
from pyjamaz.state.base import State
from pyjamaz.state.components import Disputes
from pyjamaz.storage import InMemoryStorage

from pyjamaz.models.block import Header, Extrinsic, ExtrinsicDisputes, Block
from pyjamaz.models.state import (DisputesState, AssurancesState, TimeslotState, ValidatorArchiveState,
                                  ValidatorPoolState, JamState)


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
            good_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_g']],
            bad_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_b']],
            wonky_set=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_w']],
            offenders=[bytes.fromhex(i[2:]) for i in test_vector['psi']['psi_o']],
        )

        return jam_state

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    async def test_vector(self, name, directory, test_file):
        with open(path.join(self.test_vector_dir, directory, test_file)) as f:
            test_vector = json.load(f)

        pre_state = self.create_jam_state(test_vector['pre_state'])

        block = self.create_block(test_vector['input'])

        # Initialize app
        app = PyjamazApp(config=self.config)
        await app.store_jam_state(pre_state)

        # Process block
        try:
            app.state = app.retrieve_jam_state()
            output = await app.import_block(block, validate=False)
            dispute_output = {'ok': {"offenders_mark": output.to_json()['offenders_mark']}}
        except PyjamazAppError as e:
            dispute_output = {'err': e.custom_error_code.name}

        self.assertEqual(test_vector['output'], dispute_output)

        psi = app.components.disputes.retrieve_state().to_json()

        post_state = {
            'psi_b': psi['bad_set'],
            'psi_g': psi['good_set'],
            'psi_o': psi['offenders'],
            'psi_w': psi['wonky_set'],
        }

        self.assertDictEqual(test_vector['post_state']['psi'], post_state)


if __name__ == '__main__':
    unittest.main()
