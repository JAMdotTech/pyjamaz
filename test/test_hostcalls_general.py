import json
import os
import unittest
from unittest.mock import Mock, MagicMock
from copy import deepcopy
from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm_interface.hostcalls.general import (
    # hc_gas,
    hc_read,
    hc_write,
    hc_info,
    hc_lookup,
    hc_fetch,
)

from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory, MemorySection, PVMMemoryMode
from pyjamaz.pvm.constants import ExitCondition, ExitReason, PVM_PAGE_SIZE
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.models.state import ServiceAccount, ServicesState, DeferredTransfer
from pyjamaz.models.common import WorkPackage, WorkItem, AccumulationOperand
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


def create_mock_service_account(
        code_hash=None,
        balance=1000000,
        threshold_balance=100,
        gas_limit_accumulate=1000000,
        gas_limit_on_transfer=1000000,
        footprint_storage_bytes=0,
        footprint_storage_items=0,
        storage_items=None,
        preimages=None
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

    service_account.update_footprint_add_storage_item = Mock()
    service_account.update_footprint_remove_storage_item = Mock()
    service_account.update_footprint_update_storage_item = Mock()

    return service_account


def create_mock_services_state(service_accounts=None, storage_items=None, preimages=None):
    services = Mock(spec=ServicesState)
    services.services = service_accounts or {}

    def retrieve_service_account(service_id):
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

    def store_storage_item(service_account_id, storage_item_hash, value):
        key = (service_account_id, storage_item_hash.hex() if isinstance(storage_item_hash, bytes) else storage_item_hash)
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

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general'))
    def test_instruction(self, name, test_vector):
        skip_tests = [
        ]
        if any(skip_test in name for skip_test in skip_tests):
            self.skipTest(f"Skipping {name} - overlapping memory regions not supported")

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')
        pvm_code = PVMCode.from_jam_bytes(
            #JamBytes(bytes(test_vector["pvm-program"]))
            #Grrrrrrr just a dummy program (for now)
            JamBytes(bytes([0,0,3,210,135,9,1]))
        )
        pvm_regs = test_vector["initial-registers"]

        mem_rom = None
        mem_heap = None
        mem_pages = []
        heap_pages = []
        
        for page_map in test_vector["initial-page-map"]:
            page = MemorySection(
                address=page_map["address"],
                length=page_map["length"],
                acl=PVMMemoryMode.writable if page_map["is-writable"] else PVMMemoryMode.readable,
                contents=[0] * page_map["length"]
            )
            if page_map["address"] < 2*65536:
                mem_rom = page
            else:
                heap_pages.append(page)
            mem_pages.append(page)
        
        # For tests with multiple heap pages, we need to combine them into one
        if len(heap_pages) == 1:
            mem_heap = heap_pages[0]
        elif len(heap_pages) > 1:
            # Find the lowest address and total size
            min_addr = min(p.address for p in heap_pages)
            max_addr = max(p.address + p.size for p in heap_pages)
            total_size = max_addr - min_addr
            
            # Create a combined heap section
            combined_contents = [0] * total_size
            mem_heap = MemorySection(
                address=min_addr,
                length=total_size,
                acl=PVMMemoryMode.writable,  # Default to writable for combined heap
                contents=combined_contents
            )

        pvm_memory = PVMMemory(mem_rom, mem_heap, None, None)
        
        # For tests with specific memory access requirements, update ACL after creation
        if len(heap_pages) > 1:
            for page in heap_pages:
                # Copy the original page's ACL settings
                start_page = page.address // PVM_PAGE_SIZE
                end_page = (page.address + page.size - 1) // PVM_PAGE_SIZE
                for pg in range(start_page, end_page + 1):
                    pvm_memory._acl[pg] = page.acl.value

        for mem_block in test_vector["initial-memory"]:
            page = pvm_memory.find_section(mem_block["address"])
            mem = page.contents

            if len(mem_block["contents"]) > len(mem):
                raise ValueError(f"TOO BIG TO FIT IN HERE :D")
            offset = mem_block["address"] - page.address
            for idx, byt in enumerate(mem_block["contents"]):
                mem[offset + idx] = np.uint8(byt)

        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program)

        invocation_output = InvocationMutationOutput(
            exit_condition=ExitCondition(reason=ExitReason.resume),
            gas_limit=1000000,  # Start with plenty of gas
            registers=np.array(pvm_regs, dtype=np.uint64),
            memory=deepcopy(pvm_memory),
            context=None
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
            footprint_storage_items=service_config.get("footprint_storage_items", 0)
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
                footprint_storage_items=other_config.get("footprint_storage_items", 0)
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
        logger = PVMDebugLog(pvm)

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
                work_package.authorizer = Mock()
                work_package.authorizer.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(work_package_data.get("authorizer", "00" * 32))))
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

            accumulation_operands = []
            for op_data in test_vector.get("accumulation_operands", []):
                op = Mock(spec=AccumulationOperand)
                op.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(op_data.get("encoded", "00" * 20))))
                accumulation_operands.append(op)

            deferred_transfers = []
            for dt_data in test_vector.get("deferred_transfers", []):
                dt = Mock(spec=DeferredTransfer)
                dt.to_jam_bytes = Mock(return_value=JamBytes(bytes.fromhex(dt_data.get("encoded", "00" * 40))))
                deferred_transfers.append(dt)

            hc_fetch(
                pvm_regs,
                pvm_memory,
                work_package,
                entropy,
                authorizer_output,
                work_item_index,
                work_item_segs,
                extrinsics,
                accumulation_operands,
                deferred_transfers,
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

        else:
            raise ValueError(f"Unknown GENERAL hostcall: {hostcall}")

        self.assertEqual(
            test_vector["expected-regs"],
            invocation_output.registers.tolist(),
            f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {invocation_output.registers.tolist()}"
        )

        for expected_mem in test_vector.get("expected-memory", []):
            page = invocation_output.memory.find_section(expected_mem["address"])
            mem_offset = expected_mem["address"] - page.address
            mem_len = len(expected_mem["contents"])
            hc_mem = page.contents.tolist()[mem_offset:mem_offset + mem_len]
            self.assertEqual(
                expected_mem["contents"],
                hc_mem,
                f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {hc_mem}"
            )

        expected_exit_reason = test_vector.get("expected-exit-reason", "resume")
        self.assertEqual(
            expected_exit_reason,
            invocation_output.exit_condition.reason.name.lower(),
            f"{name}: Expected exit reason {expected_exit_reason}, but got {invocation_output.exit_condition.reason.name.lower()}"
        )


if __name__ == '__main__':
    unittest.main()
