import json
import os
import unittest
from os import path
from typing import Optional

from pyjamaz.exceptions import StateTransitionError
from parameterized import parameterized

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.state.components import Services
from pyjamaz.storage import InMemoryStorage
from pyjamaz.models.block import Header, Preimage
from pyjamaz.models.state import TimeslotState, ServicesState, ServiceAccount


def get_test_vector_files(file_filter: Optional[str] = None):
    test_vectors = []

    abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'preimages')
    for filename in os.listdir(str(abs_dir)):
        if filename.endswith('.json'):
            if file_filter is None or file_filter in filename:
                test_vectors.append((f'{filename}', filename))
    return test_vectors


class TestPreimages(unittest.TestCase):


    def setUp(self):
        self.storage_engine = InMemoryStorage()
        self.block_context = BlockContext()
        self.app_context = AppContext(transaction=self.storage_engine.transaction())

    @staticmethod
    def load_test_vector_data(test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'preimages', test_vector_file
        )
        with open(test_vector_file) as f:
            return json.load(f)

    @parameterized.expand(get_test_vector_files(file_filter=''))
    def test_vector(self, name, test_file):

        test_vector = self.load_test_vector_data(test_file)

        header = Header.default()

        header.timeslot = test_vector["input"]["slot"]

        # Set up pre-state
        post_state_timeslot = TimeslotState(number=header.timeslot)

        extrinsic_preimages = [Preimage.from_json(p) for p in test_vector["input"]["preimages"]]

        # Prepare block context
        self.block_context.reset()

        services = Services(self.storage_engine, self.block_context, self.app_context)

        pre_services = ServicesState(
            services={}
        )

        pre_services.set_storage_engine(self.storage_engine)
        pre_services.set_storage_transaction(self.app_context.transaction)

        # Store services and preimages in storage engine
        for s in test_vector["pre_state"]["accounts"]:
            service_account = ServiceAccount(
                code_hash=bytes(32),
                balance=s["id"],
                gas_limit_accumulate=0,
                gas_limit_on_transfer=0,
                footprint_storage_items=0,
                footprint_storage_bytes=0,
                storage_items={},
                preimages={},
                preimage_availability={}
            )
            pre_services.store_service_account(s["id"], service_account)
            pre_services.retrieve_service_account(s["id"])

            for preimage in s["data"]["preimages"]:
                pre_services.store_preimage(
                    service_account_id=s["id"], preimage_blob=bytes.fromhex(preimage["blob"][2:])
                )
                pre_services.retrieve_preimage(s["id"], blake2b_256_hash(bytes.fromhex(preimage["blob"][2:])))

            for preimage in s["data"]["lookup_meta"]:
                pre_services.store_preimage_availability(
                    service_account_id=s["id"],
                    preimage_hash=bytes.fromhex(preimage["key"]["hash"][2:]),
                    preimage_length=preimage["key"]["length"],
                    value=preimage["value"]
                )
                pre_services.retrieve_preimage_availability(s["id"], bytes.fromhex(preimage["key"]["hash"][2:]), preimage["key"]["length"])

        try:

            services.validate_extrinsic_preimages(
                extrinsic_preimages=extrinsic_preimages,
                pre_state_services=pre_services,
            )

            output = services.state_transition_after_preimages(
                extrinsic_preimages=extrinsic_preimages,
                intermediate_state_after_transfers=pre_services,
                post_state_timeslot=post_state_timeslot,

            )

            services_output = {
                'ok': None
            }

            # Retrieve created items in working state
            for p in extrinsic_preimages:
                _ = output.post_state.retrieve_preimage(p.requester, blake2b_256_hash(p.blob))
                _ = output.post_state.retrieve_preimage_availability(p.requester, blake2b_256_hash(p.blob), len(p.blob))

            # Transform post_state to test format
            post_state = {
                'accounts': [
                    {
                        "id": s[0],
                        "data": {
                            "preimages": [
                                {
                                    "hash": p[0],
                                    "blob": p[1]
                                } for p in sorted(s[1]["preimages"], key=lambda item: item[0])
                            ],
                            "lookup_meta": [
                                {
                                    "key": {
                                        "hash": h[0][0],
                                        "length": h[0][1]
                                    },
                                    "value": h[1]
                                } for h in s[1]["preimage_availability"]],
                        }
                    } for s in output.post_state.to_json()["services"]
                ]
            }

        except StateTransitionError as e:
            services_output = {'err': e.custom_error_code.name}
            post_state = {
                "accounts": test_vector['pre_state']['accounts'],
            }

        self.assertDictEqual(test_vector['output'], services_output)

        self.assertListEqual(
            test_vector['post_state']['accounts'], post_state['accounts'], f'{name} fails'
        )


if __name__ == '__main__':
    unittest.main()
