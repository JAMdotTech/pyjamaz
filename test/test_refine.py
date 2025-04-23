import logging
import os
import unittest

from jamcodec.base import JamBytes
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.logger import setup_logging
from pyjamaz.models.common import WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.models.trace import Trace
from pyjamaz.refine import work_result_computation
from pyjamaz.storage import InMemoryStorage


class TestRefine(unittest.TestCase):
    def test_refine(self):
        log_level = logging.DEBUG
        setup_logging(log_level)

        abs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'refine')

        with open(os.path.join(abs_dir, '1_011.bin'), 'rb') as fp:
            trace = Trace.from_jam_bytes(JamBytes(fp.read()))

            state_db = InMemoryStorage()

            for k, v, name, metadata in trace.pre_state.keyvals:
                state_db.put(bytes(k), bytes(v))

        # Create services state obj
        services_state = ServicesState(services={})
        services_state.set_storage_engine(state_db)

        work_package = WorkPackage.from_json({
          "authorization": "0x3078",
          "auth_code_host": 0,
          "authorizer": {
            "code_hash": "0xc16326432b5b3213dfd1609495e13c6b276cb474d679645337e5c2c09f19b53c",
            "params": "0x"
          },
          "context": {
            "anchor": "0x70673b829c2942f2f7c7500ff0385322724fbe396c22ecacf7a6c659a4f19a76",
            "state_root": "0xeb96381bf89897dc578b87c5aeedb6d88813e6427b03b46549afdfcdc74ab55c",
            "beefy_root": "0x3a737f530c0ebf8e881127dd7fa281cefc0274b1e69432d5b20b030e3d1aa07d",
            "lookup_anchor": "0x1ad632d793d2779c87b05a7d47bae63d791f0f1c334c1538f7b5c325dc0b6a1b",
            "lookup_anchor_slot": 22,
            "prerequisites": []
          },
          "items": [
            {
              "service": 2953942612,
              "code_hash": "0xccbea4bf12716bc7f7583dd834aac2ca1b05af8dc5be285336156d0de73d9b9e",
              "payload": "0x",
              "refine_gas_limit": 5678,
              "accumulate_gas_limit": 9876,
              "import_segments": [],
              "extrinsic": [
                {
                  "hash": "0x7dd6f308800976d86755ccdf9f1ddcf9ac2614ce49006677a41b819f37527f4c",
                  "len": 36
                }
              ],
              "export_count": 0
            },
            {
              "service": 1065941251,
              "code_hash": "0xf40e27b819519561cf8f8a33309b2453a78117a3e33fcd331a0bab714f1f9e14",
              "payload": "0x",
              "refine_gas_limit": 5678,
              "accumulate_gas_limit": 9876,
              "import_segments": [],
              "extrinsic": [],
              "export_count": 0
            }
          ]
        })

        self.assertEqual('0925ae794608fc21807ae92ede46ce7ba168ce9c2130c24a396fa4c6ab6e6146', work_package.hash().hex())

        # Set code
        work_package.set_authorization_code(services_state)
        # TODO refactor to ExtrinsicStore
        extrinsic = bytes.fromhex('5ce80c45773689de2d89e283850c58ac87293ee50f07812f1db87ae694b71f30ba120000')

        work_report = work_result_computation(
            work_package=work_package,
            core_index=0,
            services_state=services_state,
            extrinsics={
                blake2b_256_hash(extrinsic): extrinsic
            }
        )

        self.assertIsNotNone(work_report.to_jam_bytes())


if __name__ == '__main__':
    unittest.main()
