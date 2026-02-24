import json
import os
import unittest
from unittest.mock import Mock, MagicMock
from copy import deepcopy
from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.hostcalls.general import (
    hc_gas,
    hc_read,
    hc_write,
    hc_info,
    hc_lookup,
    hc_fetch,
)

from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.types import PVMCode, PVMProgram
from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_R, MEM_W
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.models.state import ServiceAccount, ServicesState
from pyjamaz.models.common import WorkPackage, WorkItem, AccumulationOperand, DeferredTransfer, AccumulationInput
from pyjamaz.exceptions import StateKeyNoResult


def load_test_vectors(directory):
    directory = path.join(path.dirname(path.abspath(__file__)), directory)
    test_vectors = []
    if directory.endswith('.json'):
        with open(directory) as f:
            test_vector = json.load(f)
            test_vectors = [(directory, test_vector)]
    else:
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                with open(os.path.join(directory, filename)) as f:
                    test_vector = json.load(f)
                    test_vectors.append((filename, test_vector))

    return test_vectors


def _build_segments(initial_page_map, initial_memory):
    segments = []
    for page_map in initial_page_map or []:
        segments.append({
            "address": page_map["address"],
            "length": page_map["length"],
            "acl": MEM_W if page_map["is-writable"] else MEM_R,
            "contents": bytearray(page_map["length"]),
        })

    for mem_block in initial_memory or []:
        addr = mem_block["address"]
        data = bytes(mem_block["contents"])
        if not data:
            continue

        remaining = len(data)
        cursor = 0
        while remaining > 0:
            segment = next(
                (seg for seg in segments if seg["address"] <= addr < seg["address"] + seg["length"]),
                None
            )
            if segment is None:
                raise ValueError(f"Initial memory block not covered by page map at address {addr}")
            seg_off = addr - segment["address"]
            chunk = min(segment["length"] - seg_off, remaining)
            if chunk <= 0:
                raise ValueError(f"Invalid page map for memory block at address {addr}")
            segment["contents"][seg_off:seg_off + chunk] = data[cursor:cursor + chunk]
            addr += chunk
            cursor += chunk
            remaining -= chunk

    return segments


def create_mock_service_account(
        code_hash=None,
        balance=1000000,
        threshold_balance=100,
        gas_limit_accumulate=1000000,
        gas_limit_on_transfer=1000000,
        footprint_storage_bytes=0,
        footprint_storage_items=0,
        storage_items=None,
        preimages=None,
        deposit_offset=0,
        creation_slot=0,
        last_accumulation_slot=0,
        parent_service=0
):
    service_account = Mock(spec=ServiceAccount)
    service_account.code_hash = code_hash or b'\x00' * 32
    service_account.balance = balance
    service_account.threshold_balance = threshold_balance
    service_account.gas_limit_accumulate = gas_limit_accumulate
    service_account.gas_limit_on_transfer = gas_limit_on_transfer
    service_account.footprint_storage_bytes = footprint_storage_bytes
    service_account.footprint_storage_items = footprint_storage_items
    service_account.storage_items = storage_items or {}
    service_account.preimages = preimages or {}
    service_account.deposit_offset = deposit_offset
    service_account.creation_slot = creation_slot
    service_account.last_accumulation_slot = last_accumulation_slot
    service_account.parent_service = parent_service

    service_account.update_footprint_add_storage_item = Mock()
    service_account.update_footprint_remove_storage_item = Mock()
    service_account.update_footprint_update_storage_item = Mock()

    return service_account


def create_mock_services_state(service_accounts=None, storage_items=None, preimages=None):
    services = Mock(spec=ServicesState)
    services.services = service_accounts or {}

    def retrieve_service_account(service_id, skip_pending_changes=True):
        if service_id in services.services:
            return services.services[service_id]
        raise StateKeyNoResult(f"Service account {service_id} not found")

    services.retrieve_service_account = Mock(side_effect=retrieve_service_account)

    storage_items_dict = storage_items or {}
    def retrieve_storage_item(service_account_id, storage_item_hash):
        key = (service_account_id, storage_item_hash.hex() if isinstance(storage_item_hash, bytes) else storage_item_hash)
        if key in storage_items_dict:
            return storage_items_dict[key]
        raise StateKeyNoResult(f"Storage item not found")

    def store_storage_item(service_account_id, storage_key=None, storage_item_hash=None, value=None):
        # Support both old parameter name (storage_item_hash) and new (storage_key)
        hash_value = storage_key if storage_key is not None else storage_item_hash
        key = (service_account_id, hash_value.hex() if isinstance(hash_value, bytes) else hash_value)
        storage_items_dict[key] = value

    def delete_storage_item(service_account_id, storage_item_hash):
        key = (service_account_id, storage_item_hash.hex() if isinstance(storage_item_hash, bytes) else storage_item_hash)
        if key in storage_items_dict:
            del storage_items_dict[key]

    services.retrieve_storage_item = Mock(side_effect=retrieve_storage_item)
    services.store_storage_item = Mock(side_effect=store_storage_item)
    services.delete_storage_item = Mock(side_effect=delete_storage_item)
    services.store_service_account = Mock()

    preimages_dict = preimages or {}
    def retrieve_preimage(service_account_id, preimage_hash):
        key = (service_account_id, preimage_hash.hex() if isinstance(preimage_hash, bytes) else preimage_hash)
        if key in preimages_dict:
            return preimages_dict[key]
        raise StateKeyNoResult(f"Preimage not found")

    services.retrieve_preimage = Mock(side_effect=retrieve_preimage)

    return services


class TestHCGeneral(unittest.TestCase):

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general/'))
    def test_instruction(self, name, test_vector):
        skip_tests = [
        ]
        if any(skip_test in name for skip_test in skip_tests):
            self.skipTest(f"Skipping {name} - overlapping memory regions not supported")

        # Set NumPy to ignore overflow warnings
        pvm_code = PVMCode.from_jam_bytes(
            #JamBytes(bytes(test_vector["pvm-program"]))
            #Grrrrrrr just a dummy program (for now)
            JamBytes(bytes([0,0,3,210,135,9,1]))
        )
        pvm_regs = test_vector["initial-registers"]

        segments = _build_segments(
            test_vector.get("initial-page-map", []),
            test_vector.get("initial-memory", []),
        )
        pvm_memory = PVMMemory()
        for segment in segments:
            pvm_memory.add_segment(
                segment["address"],
                segment["length"],
                segment["acl"],
                bytes(segment["contents"]),
            )

        non_rom = [seg for seg in segments if seg["address"] >= 2 * 65536]
        non_rom.sort(key=lambda seg: seg["address"])
        if len(non_rom) >= 1:
            heap_seg = non_rom[0]
            pvm_memory.heap_base = heap_seg["address"]
            pvm_memory.heap_ptr = heap_seg["address"] + heap_seg["length"]
        if len(non_rom) >= 2:
            pvm_memory.stack_base = non_rom[1]["address"]
        if len(non_rom) > 2:
            raise Exception("Invalid memory pages")

        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program)

        invocation_output = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.resume),
            gas_limit=test_vector.get("gas", 1000000),  # Use test gas or default to plenty
            registers=np.array(pvm_regs, dtype=np.uint64),
            memory=deepcopy(pvm_memory)
        )

        service_id = test_vector.get("service_id", 0)

        service_config = test_vector.get("service_account", {})
        service = create_mock_service_account(
            code_hash=bytes.fromhex(service_config.get("code_hash", "00" * 32)),
            balance=service_config.get("balance", 1000000),
            threshold_balance=service_config.get("threshold_balance", 100),
            gas_limit_accumulate=service_config.get("gas_limit_accumulate", 1000000),
            gas_limit_on_transfer=service_config.get("gas_limit_on_transfer", 1000000),
            footprint_storage_bytes=service_config.get("footprint_storage_bytes", 0),
            footprint_storage_items=service_config.get("footprint_storage_items", 0),
            deposit_offset=service_config.get("deposit_offset", 0),
            creation_slot=service_config.get("creation_slot", 0),
            last_accumulation_slot=service_config.get("last_accumulation_slot", 0),
            parent_service=service_config.get("parent_service", 0)
        )

        other_services = {}
        for other_id, other_config in test_vector.get("other_services", {}).items():
            other_services[int(other_id)] = create_mock_service_account(
                code_hash=bytes.fromhex(other_config.get("code_hash", "00" * 32)),
                balance=other_config.get("balance", 1000000),
                threshold_balance=other_config.get("threshold_balance", 100),
                gas_limit_accumulate=other_config.get("gas_limit_accumulate", 1000000),
                gas_limit_on_transfer=other_config.get("gas_limit_on_transfer", 1000000),
                footprint_storage_bytes=other_config.get("footprint_storage_bytes", 0),
                footprint_storage_items=other_config.get("footprint_storage_items", 0),
                deposit_offset=other_config.get("deposit_offset", 0),
                creation_slot=other_config.get("creation_slot", 0),
                last_accumulation_slot=other_config.get("last_accumulation_slot", 0),
                parent_service=other_config.get("parent_service", 0)
            )

        all_services = {service_id: service}
        all_services.update(other_services)

        storage_items = {}
        for item in test_vector.get("storage_items", []):
            key = (item["service_id"], item["hash"])
            storage_items[key] = bytes.fromhex(item["value"])

        preimages = {}
        for item in test_vector.get("preimages", []):
            key = (item["service_id"], item["hash"])
            preimages[key] = bytes.fromhex(item["value"])

        services = create_mock_services_state(
            service_accounts=all_services,
            storage_items=storage_items,
            preimages=preimages
        )

        hostcall = test_vector["hostcall"]
        logger = None

        if hostcall == "hc_read":
            hc_read(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)

        elif hostcall == "hc_write":
            hc_write(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)

        elif hostcall == "hc_info":
            hc_info(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)

        elif hostcall == "hc_fetch":
            work_package_data = test_vector.get("work_package")
            work_package = None
            if work_package_data:

                work_package = Mock(spec=WorkPackage)
                work_package.auth_code_hash = bytes.fromhex(work_package_data.get("auth_code_hash", "00" * 32))
                work_package.authorizer_config = bytes.fromhex(work_package_data.get("authorizer_config", ""))
                work_package.authorization = bytes.fromhex(work_package_data.get("authorization", ""))
                work_package.context = Mock()
                work_package.context.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(work_package_data.get("context", "00" * 32))))
                work_package.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(work_package_data.get("encoded", "00" * 100))))

                work_package.items = []
                for item_data in work_package_data.get("items", []):
                    item = Mock(spec=WorkItem)
                    item.service = item_data.get("service", 0)
                    item.code_hash = bytes.fromhex(item_data.get("code_hash", "00" * 32))
                    item.refine_gas_limit = item_data.get("refine_gas_limit", 1000000)
                    item.accumulate_gas_limit = item_data.get("accumulate_gas_limit", 1000000)
                    item.export_count = item_data.get("export_count", 0)
                    item.import_segments = item_data.get("import_segments", [])
                    item.extrinsic = item_data.get("extrinsic", [])
                    item.payload = bytes.fromhex(item_data.get("payload", ""))
                    work_package.items.append(item)

            entropy = test_vector.get("entropy")
            if entropy:
                entropy = bytes.fromhex(entropy)

            authorizer_output = test_vector.get("authorizer_output")
            if authorizer_output:
                authorizer_output = bytes.fromhex(authorizer_output)

            work_item_index = test_vector.get("work_item_index")

            work_item_segs = []
            for seg_list in test_vector.get("work_item_segs", []):
                work_item_segs.append([bytes.fromhex(seg) for seg in seg_list])

            extrinsics = []
            for ext_list in test_vector.get("extrinsics", []):
                extrinsics.append([bytes.fromhex(ext) for ext in ext_list])

            accumulation_inputs = []
            for op_data in test_vector.get("accumulation_inputs", []):
                op = Mock(spec=AccumulationInput)
                op.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(op_data.get("encoded", "00" * 20))))
                accumulation_inputs.append(op)

            hc_fetch(
                pvm_regs,
                pvm_memory,
                work_package,
                entropy,
                authorizer_output,
                work_item_index,
                work_item_segs,
                extrinsics,
                accumulation_inputs,
                invocation_output,
                logger)

        elif hostcall == "hc_lookup":
            hc_lookup(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)

        elif hostcall == "hc_gas":
            hc_gas(
                pvm_regs,
                pvm_memory,
                invocation_output,
                logger)

        else:
            raise ValueError(f"Unknown GENERAL hostcall: {hostcall}")

        self.assertEqual(
            test_vector["expected-regs"],
            invocation_output.registers.tolist(),
            f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {invocation_output.registers.tolist()}"
        )

        for expected_mem in test_vector.get("expected-memory", []):
            mem_len = len(expected_mem["contents"])
            hc_mem = list(invocation_output.memory.read_bytes(expected_mem["address"], mem_len))
            self.assertEqual(
                expected_mem["contents"],
                hc_mem,
                f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {[int(x) for x in hc_mem]}"
            )

        expected_exit_reason = test_vector.get("expected-exit-reason", "resume")
        self.assertEqual(
            expected_exit_reason,
            invocation_output.exit_condition.reason.name.lower(),
            f"{name}: Expected exit reason {expected_exit_reason}, but got {invocation_output.exit_condition.reason.name.lower()}"
        )

        # Check expected gas if specified
        if "expected-gas" in test_vector:
            self.assertEqual(
                test_vector["expected-gas"],
                invocation_output.gas_limit,
                f"{name}: Expected gas {test_vector['expected-gas']}, but got {invocation_output.gas_limit}"
            )

        # context related checks for generals hostcalls
        if hostcall == "hc_fetch":
            # hc_fetch provides access to work package data, extrinsics, etc.
            # The data is written directly to memory as specified in expected-memory
            pass

        if hostcall == "hc_info":
            # hc_info provides access to service account information
            # it writes service info to memory which is verified via expected-memory
            pass

        if hostcall == "hc_lookup":
            # hc_lookup reads preimage data from the service preimage store
            pass

        if hostcall == "hc_read":
            # hc_read reads storage items from the service storage
            pass

        if hostcall == "hc_write":
            # hc_write modifies the services storage
            # storage changes are handled through the services mock
            # verify storage was actually modified if expected
            if "expected_storage_items" in test_vector:
                for expected_item in test_vector["expected_storage_items"]:
                    key = (expected_item["service_id"], expected_item["hash"])
                    actual_value = storage_items.get(key)
                    expected_value = bytes.fromhex(expected_item["value"]) if expected_item["value"] else None

                    if expected_value is None:
                        self.assertIsNone(
                            actual_value,
                            f"{name}: Expected storage item {key} to be deleted, but found {actual_value}"
                        )
                    else:
                        self.assertEqual(
                            expected_value,
                            actual_value,
                            f"{name}: Expected storage item {key} to have value {expected_value.hex()}, but got {actual_value.hex() if actual_value else 'None'}"
                        )

            # verify service account footprint updates were called if storage was modified
            if "expected_footprint_calls" in test_vector:
                for call_type, expected_count in test_vector["expected_footprint_calls"].items():
                    if call_type == "add":
                        actual_count = service.update_footprint_add_storage_item.call_count
                        self.assertEqual(
                            expected_count,
                            actual_count,
                            f"{name}: Expected {expected_count} add_storage_item calls, but got {actual_count}"
                        )
                    elif call_type == "remove":
                        actual_count = service.update_footprint_remove_storage_item.call_count
                        self.assertEqual(
                            expected_count,
                            actual_count,
                            f"{name}: Expected {expected_count} remove_storage_item calls, but got {actual_count}"
                        )
                    elif call_type == "update":
                        actual_count = service.update_footprint_update_storage_item.call_count
                        self.assertEqual(
                            expected_count,
                            actual_count,
                            f"{name}: Expected {expected_count} update_storage_item calls, but got {actual_count}"
                        )


if __name__ == '__main__':
    unittest.main()
