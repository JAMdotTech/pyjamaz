import json
import os
import unittest
from unittest.mock import Mock, MagicMock
from copy import deepcopy
from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm_interface.hostcalls.accumulate import (
    hc_bless,
    hc_assign,
    hc_designate,
    hc_new
)

from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory, MemorySection, PVMMemoryMode
from pyjamaz.pvm.constants import ExitCondition, ExitReason, PVM_PAGE_SIZE
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.models.state import ServiceAccount, ServicesState, DeferredTransfer, PrivilegedServicesState, AccumulationStateComponents, AuthorizerQueuesState, ValidatorQueueState
from pyjamaz.models.common import WorkPackage, WorkItem, AccumulationOperand
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.pvm_interface.models import AccumulateInvocationContext, AccumulateContextItem
from pyjamaz.pvm_interface.hostcalls.constants import HostCallResult


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
    service_account.update_footprint_add_preimage = Mock()
    
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
    services.store_preimage_availability = Mock()
    
    return services


class TestHCAccumulate(unittest.TestCase):

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/accumulate'))
    def test_instruction(self, name, test_vector):
        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')
        pvm_code = PVMCode.from_jam_bytes(
            # JamBytes(bytes(test_vector["pvm-program"]))
            # Grrrrrrr just a dummy program (for now)
            JamBytes(bytes([0, 0, 3, 210, 135, 9, 1]))
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
            if page_map["address"] < 2 * 65536:
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

        hostcall = test_vector["hostcall"]
        logger = PVMDebugLog(pvm)

        services_data = test_vector.get("context", {}).get("services", {})
        service_accounts = {}
        for service_id, service_config in services_data.items():
            service_accounts[int(service_id)] = create_mock_service_account(
                code_hash=bytes.fromhex(service_config.get("code_hash", "00" * 32)),
                balance=service_config.get("balance", 1000000),
                threshold_balance=service_config.get("threshold_balance", 100),
                gas_limit_accumulate=service_config.get("gas_limit_accumulate", 1000000),
                gas_limit_on_transfer=service_config.get("gas_limit_on_transfer", 1000000),
                footprint_storage_bytes=service_config.get("footprint_storage_bytes", 0),
                footprint_storage_items=service_config.get("footprint_storage_items", 0)
            )
        
        services = create_mock_services_state(service_accounts=service_accounts)
        
        # Create privileged services
        privileged_services = Mock(spec=PrivilegedServicesState)
        privileged_services.empower_service = None
        privileged_services.assign_service = None
        privileged_services.designate_service = None
        privileged_services.auto_accumulate_services = {}
        
        # Create authorizer queues
        authorizer_queues = Mock(spec=AuthorizerQueuesState)
        authorizer_queues.authorizer_queues = {}
        
        # Create validator queue
        validator_queue = Mock(spec=ValidatorQueueState)
        validator_queue.validators = []
        
        # Create accumulation state components
        state_components = Mock(spec=AccumulationStateComponents)
        state_components.services = services
        state_components.privileged_services = privileged_services
        state_components.authorizer_queues = authorizer_queues
        state_components.validator_queue = validator_queue
        state_components.check_service_id = Mock(side_effect=lambda x: x)
        
        # Create accumulate context item
        context_item = Mock(spec=AccumulateContextItem)
        context_item.state_context = state_components
        context_item.service_account_id = test_vector.get("context", {}).get("service_account_id", 1)
        context_item.new_service_account_id = test_vector.get("context", {}).get("new_service_account_id", 256)
        context_item.deferred_transfers = []
        
        # Create accumulate invocation context
        accumulate_context = Mock(spec=AccumulateInvocationContext)
        accumulate_context.context = context_item

        if hostcall == "hc_bless":
            hc_bless(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_assign":
            hc_assign(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_designate":
            hc_designate(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_new":
            hc_new(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        else:
            raise ValueError(f"Unknown ACCUMULATE hostcall: {hostcall}")

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
        
        # Check expected privileged services if provided
        if "expected-privileged-services" in test_vector:
            expected_ps = test_vector["expected-privileged-services"]
            if expected_ps.get("empower_service") is not None:
                self.assertEqual(
                    expected_ps["empower_service"],
                    privileged_services.empower_service,
                    f"{name}: Expected empower_service {expected_ps['empower_service']}, but got {privileged_services.empower_service}"
                )
            if expected_ps.get("assign_service") is not None:
                self.assertEqual(
                    expected_ps["assign_service"],
                    privileged_services.assign_service,
                    f"{name}: Expected assign_service {expected_ps['assign_service']}, but got {privileged_services.assign_service}"
                )
            if expected_ps.get("designate_service") is not None:
                self.assertEqual(
                    expected_ps["designate_service"],
                    privileged_services.designate_service,
                    f"{name}: Expected designate_service {expected_ps['designate_service']}, but got {privileged_services.designate_service}"
                )
            if "auto_accumulate_services" in expected_ps:
                # Convert string keys to int keys for comparison
                expected_auto_acc = {int(k): v for k, v in expected_ps["auto_accumulate_services"].items()}
                self.assertEqual(
                    expected_auto_acc,
                    privileged_services.auto_accumulate_services,
                    f"{name}: Expected auto_accumulate_services {expected_auto_acc}, but got {privileged_services.auto_accumulate_services}"
                )


if __name__ == '__main__':
    unittest.main()
