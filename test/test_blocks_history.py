import json
import os
import unittest
from copy import deepcopy
from os import path
from typing import Optional

from parameterized import parameterized

from pyjamaz.state.components import RecentHistory
from pyjamaz.storage import JSONStorage
from pyjamaz.types.block import Block, Header, Extrinsic, ExtrinsicDisputes, Guarantee, WorkReport, WorkPackageSpec
from pyjamaz.types.state import RecentHistoryState


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
                parent=bytes(32),
                parent_state_root=bytes.fromhex(test_vector["input"]["parent_state_root"][2:]),
                extrinsic_hash=bytes(32),
                timeslot=0,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                author_index=0,
                entropy_source=bytes(32),
                seal=bytes(32)
            ),
            extrinsic=Extrinsic(
                tickets=[],
                disputes=ExtrinsicDisputes(verdicts=[], culprits=[], faults=[]),
                preimages=[],
                assurances=[],
                guarantees=[
                    Guarantee(
                        report=WorkReport(
                            package_spec=WorkPackageSpec(
                                hash=bytes.fromhex(w[2:]),
                                len=0,
                                erasure_root=bytes(32),
                                exports_root=bytes(32),
                            ),
                            context=None,
                            core_index=0,
                            authorizer_hash=bytes(32),
                            auth_output=bytes(),
                            results=[]),
                        slot=0,
                        signatures=[]
                    ) for w in test_vector["input"]["work_packages"]]
            )
        )

        block.header.hash = bytes.fromhex(test_vector["input"]["header_hash"][2:])

        # TODO How to determine this from extrinsic? Merkle root of WorkPackageSpec.roots?
        accumulate_root = bytes.fromhex(test_vector["input"]["accumulate_root"][2:])

        pre_state = RecentHistoryState.from_json({'recent_history': test_vector["pre_state"]["beta"]})

        blocks_history = RecentHistory(self.storage_engine)
        blocks_history.pre_state = pre_state
        blocks_history.post_state = deepcopy(pre_state)

        blocks_history.state_transition(
            header=block.header, extrinsic_guarantees=block.extrinsic.guarantees,
            intermediate_state_recent_history=None, accumulate_root=accumulate_root
        )

        self.assertEqual(
            len(blocks_history.post_state.recent_history),
            len(test_vector['post_state']['beta']),
            'Length of history does not match'
        )

        for idx, block_info in enumerate(blocks_history.post_state.recent_history):
            self.assertDictEqual(
                block_info.to_json(), test_vector['post_state']['beta'][idx], f'block {idx} does not match'
            )


if __name__ == '__main__':
    unittest.main()
