import json
import os
import unittest
from os import path
from typing import Optional

from parameterized import parameterized

from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.components import RecentHistory
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Guarantee
from pyjamaz.models.common import RefinementContext, WorkPackageSpec, WorkReport
from pyjamaz.models.state import RecentHistoryState


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
        cls.storage_engine = InMemoryStorage()
        cls.block_context = BlockContext()
        cls.app_context = AppContext()

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

        header = Header(
            parent=bytes(32),
            parent_state_root=bytes.fromhex(test_vector["input"]["parent_state_root"][2:]),
            extrinsic_hash=bytes(32),
            timeslot=0,
            epoch_marker=None,
            tickets_marker=None,
            offenders_marker=[],
            author_index=0,
            entropy_source=bytes(96),
            seal=bytes(96)
        )

        header.hash = bytes.fromhex(test_vector["input"]["header_hash"][2:])

        extrinsic_guarantees = [
            Guarantee(
                report=WorkReport(
                    package_spec=WorkPackageSpec(
                        hash=bytes.fromhex(work_package['hash'][2:]),
                        length=0,
                        erasure_root=bytes(32),
                        exports_root=bytes.fromhex(work_package['exports_root'][2:]),
                        exports_count=0
                    ),
                    context=RefinementContext(
                        anchor=bytes(32),
                        state_root=bytes(32),
                        beefy_root=bytes(32),
                        lookup_anchor=bytes(32),
                        lookup_anchor_slot=0,
                        prerequisites=[]
                    ),
                    core_index=0,
                    authorizer_hash=bytes(32),
                    auth_output=bytes(),
                    segment_root_lookup={},
                    results=[],
                    auth_gas_used=0
        ),
                slot=0,
                signatures=[]
            ) for work_package in test_vector["input"]["work_packages"]
        ]

        # TODO How to determine this from extrinsic? Merkle root of WorkPackageSpec.roots?
        accumulate_root = bytes.fromhex(test_vector["input"]["accumulate_root"][2:])

        pre_state = RecentHistoryState.from_json({'recent_history': test_vector["pre_state"]["beta"]})

        blocks_history = RecentHistory(self.storage_engine, self.block_context, self.app_context)

        intermediate_state_recent_history = blocks_history.state_transition_intermediate(
            header=header,
            pre_state_recent_history=pre_state
        ).intermediate_state

        output = blocks_history.state_transition(
            header=header,
            extrinsic_guarantees=extrinsic_guarantees,
            intermediate_state_recent_history=intermediate_state_recent_history,
            beefy_commitment_map=accumulate_root
        )

        self.assertEqual(
            len(output.post_state.recent_history),
            len(test_vector['post_state']['beta']),
            'Length of history does not match'
        )

        for idx, block_info in enumerate(output.post_state.recent_history):
            self.assertDictEqual(
                block_info.to_json(), test_vector['post_state']['beta'][idx], f'block {idx} does not match'
            )


if __name__ == '__main__':
    unittest.main()
