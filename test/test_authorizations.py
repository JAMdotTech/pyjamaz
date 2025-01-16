import json
import os
import unittest
from os import path
from typing import Optional

from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.models.common import WorkReport
from pyjamaz.settings import TEST_SUITE
from pyjamaz.state.base import AppContext
from pyjamaz.state.components import AuthorizerPools
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Guarantee, BlockContext
from pyjamaz.models.state import AuthorizerPoolsState, AuthorizerQueuesState


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'authorizations', TEST_SUITE)
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestAuthorizations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.storage_engine = InMemoryStorage()
        cls.block_context = BlockContext()
        cls.app_context = AppContext()

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'authorizations', TEST_SUITE, test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]

        # Set up pre-state
        extrinsic_guarantees = [
            Guarantee(
                report=WorkReport(
                    package_spec=None,
                    context=None,
                    core_index=a["core"],
                    authorizer_hash=bytes.fromhex(a["auth_hash"][2:]),
                    auth_output=b'',
                    segment_root_lookup=[],
                    results=[]
                ),
                slot=0,
                signatures=[]
            ) for a in test_vector["input"]["auths"]
        ]

        pre_authorizer_pools = AuthorizerPoolsState.from_json(
            {"authorizer_pools": test_vector["pre_state"]["auth_pools"]}
        )
        pre_authorizer_queues = AuthorizerQueuesState.from_json(
            {"authorizer_queues": test_vector["pre_state"]["auth_queues"]}
        )

        # Prepare block context
        self.block_context.initialize()

        # Execute STF
        authorizer_pools = AuthorizerPools(self.storage_engine, self.block_context, self.app_context)
        try:

            output = authorizer_pools.state_transition(
                header=header,
                extrinsic_guarantees=extrinsic_guarantees,
                pre_state_authorizer_pools=pre_authorizer_pools,
                post_state_authorizer_queues=pre_authorizer_queues
            )

            post_state = output.post_state.to_json()
        except StateTransitionError as e:
            post_state = pre_authorizer_pools.to_json()

        post_authorizer_pools = AuthorizerPoolsState.from_json(
            {"authorizer_pools": test_vector["post_state"]["auth_pools"]}
        )
        post_authorizer_queues = AuthorizerQueuesState.from_json(
            {"authorizer_queues": test_vector["post_state"]["auth_queues"]}
        )

        # Check output of STF with test vector
        for c in range(len(post_state["authorizer_pools"])):
            self.assertListEqual(post_state["authorizer_pools"][c], post_authorizer_pools.to_json()["authorizer_pools"][c], f'{name} core {c} fails')

        self.assertEqual(pre_authorizer_queues, post_authorizer_queues, f'{name} fails')


if __name__ == '__main__':
    unittest.main()
