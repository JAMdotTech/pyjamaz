# import json
# import logging
# import os
# import unittest
#
# from jamcodec.base import JamBytes
# from pyjamaz.hashing import blake2b_256_hash
# from pyjamaz.logger import setup_logging
# from pyjamaz.models.app import ChainspecDump
# from pyjamaz.models.common import WorkPackage
# from pyjamaz.models.state import ServicesState
# from pyjamaz.refine import work_result_computation
# from pyjamaz.storage import InMemoryStorage
#
#
# class TestRefine(unittest.TestCase):
#     def test_refine(self):
#         log_level = logging.DEBUG
#         setup_logging(log_level)
#
#         abs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pyjamaz', 'data', 'chainspecs')
#         state_db = InMemoryStorage()
#
#         # Load chainspec
#         with open(os.path.join(abs_dir, f'dev-spec.json'), 'r') as fp:
#             chainspec_data = json.load(fp)
#
#         # Store state data
#         for k, v in chainspec_data["genesis_state"].items():
#             state_db.put(bytes.fromhex(k), bytes.fromhex(v))
#
#         # Create services state obj
#         services_state = ServicesState(services={})
#         services_state.set_storage_engine(state_db)
#
#         work_package = WorkPackage.from_json({
#           "authorization": "0x3078",
#           "auth_code_host": 0,
#           "authorizer": {
#             "code_hash": "0x4c4e4f63481b4b2b4726611dee56d0d8d1a3e163808b3ef678ab25dfa7c32419",
#             "params": "0x"
#           },
#           "context": {
#             "anchor": "0x70673b829c2942f2f7c7500ff0385322724fbe396c22ecacf7a6c659a4f19a76",
#             "state_root": "0xeb96381bf89897dc578b87c5aeedb6d88813e6427b03b46549afdfcdc74ab55c",
#             "beefy_root": "0x3a737f530c0ebf8e881127dd7fa281cefc0274b1e69432d5b20b030e3d1aa07d",
#             "lookup_anchor": "0x1ad632d793d2779c87b05a7d47bae63d791f0f1c334c1538f7b5c325dc0b6a1b",
#             "lookup_anchor_slot": 22,
#             "prerequisites": []
#           },
#           "items": [
#             {
#               "service": 0,
#               "code_hash": "0x7d952fd5905548e08a9a7d8fca521139f7e2573a2207d6a6d0e706a13070487b",
#               "payload": "0x",
#               "refine_gas_limit": 5678,
#               "accumulate_gas_limit": 9876,
#               "import_segments": [],
#               "extrinsic": [
#                 {
#                   "hash": "0x7dd6f308800976d86755ccdf9f1ddcf9ac2614ce49006677a41b819f37527f4c",
#                   "len": 36
#                 }
#               ],
#               "export_count": 0
#             },
#             {
#               "service": 1065941251,
#               "code_hash": "0xf40e27b819519561cf8f8a33309b2453a78117a3e33fcd331a0bab714f1f9e14",
#               "payload": "0x",
#               "refine_gas_limit": 5678,
#               "accumulate_gas_limit": 9876,
#               "import_segments": [],
#               "extrinsic": [],
#               "export_count": 0
#             }
#           ]
#         })
#
#         # self.assertEqual('0925ae794608fc21807ae92ede46ce7ba168ce9c2130c24a396fa4c6ab6e6146', work_package.hash().hex())
#
#         # Set code
#         work_package.set_authorization_code(services_state)
#         # TODO refactor to ExtrinsicStore
#         extrinsic = bytes.fromhex('5ce80c45773689de2d89e283850c58ac87293ee50f07812f1db87ae694b71f30ba120000')
#
#         work_report = work_result_computation(
#             work_package=work_package,
#             core_index=0,
#             services_state=services_state,
#             extrinsics={
#                 blake2b_256_hash(extrinsic): extrinsic
#             }
#         )
#
#         self.assertIsNotNone(work_report.to_jam_bytes())
#
#
# if __name__ == '__main__':
#     unittest.main()

from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.hostcalls.models import PvmIsAuthorizedOutput, PvmRefineOutput
from pyjamaz.models.common import WorkExecResult, WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.storage import InMemoryStorageEngine


def _parallel_refine_test_work_package() -> WorkPackage:
    return WorkPackage.from_json({
        "authorization": "0x",
        "auth_code_host": 0,
        "auth_code_hash": "0x" + "11" * 32,
        "authorizer_config": "0x",
        "context": {
            "anchor": "0x" + "22" * 32,
            "state_root": "0x" + "33" * 32,
            "beefy_root": "0x" + "44" * 32,
            "lookup_anchor": "0x" + "55" * 32,
            "lookup_anchor_slot": 22,
            "prerequisites": []
        },
        "items": [
            {
                "service": 1,
                "code_hash": "0x" + "66" * 32,
                "payload": "0x01",
                "refine_gas_limit": 100,
                "accumulate_gas_limit": 200,
                "import_segments": [],
                "extrinsic": [],
                "export_count": 0
            },
            {
                "service": 2,
                "code_hash": "0x" + "77" * 32,
                "payload": "0x02",
                "refine_gas_limit": 101,
                "accumulate_gas_limit": 201,
                "import_segments": [],
                "extrinsic": [],
                "export_count": 0
            }
        ]
    })


def test_work_result_computation_parallel_refine_is_deterministic(monkeypatch):
    def fake_is_authorized(*_args, **_kwargs):
        return PvmIsAuthorizedOutput(
            work_exec_result=WorkExecResult(ok=b"auth"),
            gas_used=7,
        )

    def fake_refine(*_args, work_item_index, **_kwargs):
        return PvmRefineOutput(
            work_exec_result=WorkExecResult(ok=f"item-{work_item_index}".encode()),
            export_segments=[],
            gas_used=10 + work_item_index,
        )

    monkeypatch.setattr("pyjamaz.app.pvm_invoke_is_authorized", fake_is_authorized)
    monkeypatch.setattr("pyjamaz.app.pvm_invoke_refine", fake_refine)

    app = PyjamazApp(
        AppConfig(
            ring_data=b"",
            storage_engine=InMemoryStorageEngine(),
            common_era=0,
        )
    )
    services_state = ServicesState()
    services_state.historical_preimage_lookup = lambda *_args, **_kwargs: None
    extrinsics = [[], []]

    monkeypatch.setattr("pyjamaz.settings.REFINE_WORKERS", 1)
    sequential = app.work_result_computation(
        work_package=_parallel_refine_test_work_package(),
        core_index=0,
        services_state=services_state,
        extrinsics=extrinsics,
    )

    monkeypatch.setattr("pyjamaz.settings.REFINE_WORKERS", 2)
    parallel = app.work_result_computation(
        work_package=_parallel_refine_test_work_package(),
        core_index=0,
        services_state=services_state,
        extrinsics=extrinsics,
    )

    assert parallel.hash() == sequential.hash()
    assert parallel.package_spec.exports_root == sequential.package_spec.exports_root
    assert [r.result.ok for r in parallel.results] == [b"item-0", b"item-1"]
