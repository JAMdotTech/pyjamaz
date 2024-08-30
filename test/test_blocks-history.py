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
from pyjamaz.serialization import Serializable
from pyjamaz.state.base import StateManager
from pyjamaz.state.components import Timeslot, Entropy, ValidatorArchive, ValidatorPool, Safrole, ValidatorQueue, \
    BlocksHistory
from pyjamaz.state.exceptions import StateTransitionError
from pyjamaz.storage import JSONStorage, RocksDBStorage, LevelDBStorage
from pyjamaz.types.safrole import SafroleTestState, SafroleInput, SafroleOutput
from pyjamaz.types.block import Block, Header, Extrinsic, OutputMarks
from pyjamaz.types.state import JamState, TimeslotState, EntropyState, SafroleState, ValidatorQueueState, \
    ValidatorPoolState, ValidatorArchiveState, BlocksHistoryState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'blocks-history')
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestBlockHistory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        storage_dir = path.join(path.dirname(path.abspath(__file__)), '..', 'data')

        # cls.storage_engine = LevelDBStorage(path.join(storage_dir, "db"))
        cls.storage_engine = JSONStorage(path.join(storage_dir, "storage.json"))

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'blocks-history', test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        block = Block(
            header=Header(
                hash=bytes.fromhex(test_vector["input"]["header_hash"][2:]),
                parent_hash=bytes(32),
                parent_state_root=bytes.fromhex(test_vector["input"]["parent_state_root"][2:]),
                extrinsic_root=bytes(32),
                timeslot=0,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                block_author_index=0,
                vrf_signature=bytes(32),
                block_seal=bytes(32)
            ),
            extrinsic=Extrinsic(
                tickets=[],
                work_report_hashes=[bytes.fromhex(w[2:]) for w in test_vector["input"]["work_packages"]],
                accumulate_root=bytes.fromhex(test_vector["input"]["accumulate_root"][2:])
            )
        )

        pre_state = BlocksHistoryState.from_json({'blocks': test_vector["pre_state"]["beta"]})

        state_manager = StateManager(self.storage_engine)
        blocks_history = BlocksHistory(state_manager)

        blocks_history.initialize(
            pre_state=pre_state,
            output_marks=OutputMarks()
        )

        blocks_history.state_transition(block)

        self.assertEqual(
            len(blocks_history.post_state.blocks),
            len(test_vector['post_state']['beta']),
            'Length of history does not match'
        )

        for idx, block_info in enumerate(blocks_history.post_state.blocks):
            self.assertDictEqual(
                block_info.to_json(), test_vector['post_state']['beta'][idx], f'block {idx} does not match'
            )


if __name__ == '__main__':
    unittest.main()
