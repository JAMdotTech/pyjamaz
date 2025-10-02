import json
import os
import unittest
from unittest.mock import Mock, MagicMock
from copy import deepcopy
from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.hostcalls.accumulate import (
    hc_bless,
    hc_assign,
    hc_designate,
    hc_checkpoint,
    hc_new,
    hc_upgrade,
    hc_transfer,
    hc_eject,
    hc_query,
    hc_solicit,
    hc_forget,
    hc_provide
)

from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory, MemorySection
from pyjamaz.pvm.constants import ExitCondition, ExitReason, PVM_PAGE_SIZE, MEM_R, MEM_W
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.models.state import ServiceAccount, ServicesState, PrivilegedServicesState, AccumulationStateComponents, AuthorizerQueuesState, ValidatorQueueState
from pyjamaz.models.common import WorkPackage, WorkItem, AccumulationOperand, DeferredTransfer
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hostcalls.models import AccumulateInvocationContext, AccumulateContextItem
from pyjamaz.hostcalls.constants import HostCallResult


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
    services.delete_preimage = Mock()
    services.delete_preimage_availability = Mock()
    services.delete_service_account = Mock()

    # Add preimage availability support
    preimage_availability_dict = {}
    def retrieve_preimage_availability(service_id, preimage_hash, length):
        key = f"{service_id}:{preimage_hash.hex() if isinstance(preimage_hash, bytes) else preimage_hash}:{length}"
        if key in preimage_availability_dict:
            return preimage_availability_dict[key]
        raise StateKeyNoResult(f"Preimage availability not found")

    services.retrieve_preimage_availability = Mock(side_effect=retrieve_preimage_availability)

    def store_preimage_availability(service_id, preimage_hash, length, value):
        key = f"{service_id}:{preimage_hash.hex() if isinstance(preimage_hash, bytes) else preimage_hash}:{length}"
        preimage_availability_dict[key] = value

    services.store_preimage_availability = Mock(side_effect=store_preimage_availability)

    def delete_preimage_availability(service_id, preimage_hash, length):
        key = f"{service_id}:{preimage_hash.hex() if isinstance(preimage_hash, bytes) else preimage_hash}:{length}"
        if key in preimage_availability_dict:
            del preimage_availability_dict[key]

    services.delete_preimage_availability = Mock(side_effect=delete_preimage_availability)

    return services, preimage_availability_dict


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
                size=page_map["length"],
                acl=MEM_W if page_map["is-writable"] else MEM_R,
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
                size=total_size,
                acl=MEM_W,  # Default to writable for combined heap
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
            memory=deepcopy(pvm_memory)
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

        # load preimage availability from test vector (if set)
        preimage_availability_data = test_vector.get("context", {}).get("preimage_availability", {})

        services, preimage_availability_dict = create_mock_services_state(service_accounts=service_accounts)

        # make preimage data available
        for key, value in preimage_availability_data.items():
            preimage_availability_dict[key] = value

        # Setup privileged services from test vector if provided
        privileged_services_data = test_vector.get("context", {}).get("privileged_services", {})
        privileged_services = Mock(spec=PrivilegedServicesState)
        privileged_services.manager = privileged_services_data.get("manager", None)

        # Handle assigners - it can be a partial array or sparse dict in test vector
        privileged_services.assigners = [None] * 341  # Initialize array of 341 cores (CORE_COUNT)

        # Check for sparse format first (dict with core indices as keys)
        if "assigners_sparse" in privileged_services_data:
            assigners_sparse = privileged_services_data["assigners_sparse"]
            for core_idx, assigner in assigners_sparse.items():
                idx = int(core_idx)
                if idx < 341:
                    privileged_services.assigners[idx] = assigner
        # Otherwise use dense array format
        elif "assigners" in privileged_services_data:
            assigners_from_test = privileged_services_data["assigners"]
            # Override specific cores from test vector
            for i, assigner in enumerate(assigners_from_test):
                if i < 341:
                    privileged_services.assigners[i] = assigner

        privileged_services.delegator = privileged_services_data.get("delegator", None)
        privileged_services.always_accumulators = privileged_services_data.get("always_accumulators", {})

        authorizer_queues = Mock(spec=AuthorizerQueuesState)
        authorizer_queues.authorizer_queues = {}

        validator_queue = Mock(spec=ValidatorQueueState)
        validator_queue.validators = []

        state_components = Mock(spec=AccumulationStateComponents)
        state_components.services = services
        state_components.privileged_services = privileged_services
        state_components.authorizer_queues = authorizer_queues
        state_components.validator_queue = validator_queue
        state_components.check_service_id = Mock(side_effect=lambda x: x)

        context_item = Mock(spec=AccumulateContextItem)
        context_item.state_context = state_components
        context_item.service_account_id = test_vector.get("context", {}).get("service_account_id", 1)
        context_item.new_service_account_id = test_vector.get("context", {}).get("new_service_account_id", 256)
        context_item.deferred_transfers = []

        preimages_data = test_vector.get("context", {}).get("preimages", [])
        preimages_hex = test_vector.get("context", {}).get("preimages_hex", False)
        context_item.preimages = []
        for preimage in preimages_data:
            if preimages_hex:
                context_item.preimages.append((preimage[0], bytes.fromhex(preimage[1])))
            else:
                context_item.preimages.append(tuple(preimage))

        accumulate_context = Mock(spec=AccumulateInvocationContext)
        accumulate_context.context = context_item
        accumulate_context.timeslot = test_vector.get("context", {}).get("timeslot", 0)

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
        elif hostcall == "hc_upgrade":
            hc_upgrade(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_transfer":
            hc_transfer(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_eject":
            hc_eject(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_query":
            hc_query(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_solicit":
            hc_solicit(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_forget":
            hc_forget(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                invocation_output,
                logger
            )
        elif hostcall == "hc_provide":
            hc_provide(
                pvm_regs,
                pvm_memory,
                accumulate_context,
                services,
                context_item.service_account_id,
                invocation_output,
                logger
            )
        elif hostcall == "hc_checkpoint":
            hc_checkpoint(
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

        # additionally, heck expected privileged services if provided
        if "expected-privileged-services" in test_vector:
            expected_ps = test_vector["expected-privileged-services"]
            if expected_ps.get("manager") is not None:
                self.assertEqual(
                    expected_ps["manager"],
                    privileged_services.manager,
                    f"{name}: Expected manager {expected_ps['manager']}, but got {privileged_services.manager}"
                )
            if expected_ps.get("assigners") is not None:
                # Compare only the first few assigners as specified in test
                expected_assigners = expected_ps["assigners"]
                actual_assigners = privileged_services.assigners[:len(expected_assigners)]
                self.assertEqual(
                    expected_assigners,
                    actual_assigners,
                    f"{name}: Expected assigners {expected_assigners}, but got {actual_assigners}"
                )
            if expected_ps.get("delegator") is not None:
                self.assertEqual(
                    expected_ps["delegator"],
                    privileged_services.delegator,
                    f"{name}: Expected delegator {expected_ps['delegator']}, but got {privileged_services.delegator}"
                )
            if "always_accumulators" in expected_ps:
                expected_auto_acc = {int(k): v for k, v in expected_ps["always_accumulators"].items()}
                self.assertEqual(
                    expected_auto_acc,
                    privileged_services.always_accumulators,
                    f"{name}: Expected always_accumulators {expected_auto_acc}, but got {privileged_services.always_accumulators}"
                )

        # verify context modifications for accumulate hostcalls
        if hostcall == "hc_bless":
            # hc_bless modifies privileged services in the context
            # Changes are verified above in expected-privileged-services
            pass

        elif hostcall == "hc_assign":
            # hc_assign modifies authorizer queues in the context
            if "expected-authorizer-queues" in test_vector:
                for core_index, expected_queue in test_vector["expected-authorizer-queues"].items():
                    actual_queue = authorizer_queues.authorizer_queues.get(int(core_index), [])
                    self.assertEqual(
                        expected_queue,
                        actual_queue,
                        f"{name}: Expected authorizer queue for core {core_index} to be {expected_queue}, but got {actual_queue}"
                    )

        elif hostcall == "hc_designate":
            # hc_designate modifies validator queue in the context
            if "expected-validator-queue" in test_vector:
                self.assertEqual(
                    test_vector["expected-validator-queue"],
                    validator_queue.validators,
                    f"{name}: Expected validator queue {test_vector['expected-validator-queue']}, but got {validator_queue.validators}"
                )

        elif hostcall == "hc_checkpoint":
            # hc_checkpoint saves a snapshot of the context
            # the savepoint_context should be updated to be a deep copy of context
            self.assertIsNotNone(
                accumulate_context.savepoint_context,
                f"{name}: Expected savepoint_context to be set after hc_checkpoint"
            )
            # verify that savepoint_context is a copy of context (has same values)
            self.assertEqual(
                accumulate_context.context.service_account_id,
                accumulate_context.savepoint_context.service_account_id,
                f"{name}: savepoint_context should have same service_account_id as context"
            )
            self.assertEqual(
                accumulate_context.context.new_service_account_id,
                accumulate_context.savepoint_context.new_service_account_id,
                f"{name}: savepoint_context should have same new_service_account_id as context"
            )

        elif hostcall == "hc_new":
            # hc_new creates a new service account and modifies:
            # - new_service_account_id in context
            # - service accounts in state_context
            # - balance of the calling service
            if "expected-new-service-id" in test_vector:
                self.assertEqual(
                    test_vector["expected-new-service-id"],
                    context_item.new_service_account_id,
                    f"{name}: Expected new_service_account_id {test_vector['expected-new-service-id']}, but got {context_item.new_service_account_id}"
                )

            #check if new service was stored
            if "expected-new-service" in test_vector:
                new_service_data = test_vector["expected-new-service"]
                # Verify store_service_account was called for the new service
                store_calls = services.store_service_account.call_args_list
                new_service_stored = any(
                    call[0][0] == new_service_data.get("id")
                    for call in store_calls
                )
                self.assertTrue(
                    new_service_stored,
                    f"{name}: Expected new service {new_service_data.get('id')} to be stored"
                )

        elif hostcall == "hc_upgrade":
            # hc_upgrade modifies the service accounts code hash and gas limits
            # vhanges are stored in the services state
            if "expected-service-updates" in test_vector:
                # Verify store_service_account was called with updated service
                self.assertGreater(
                    services.store_service_account.call_count,
                    0,
                    f"{name}: Expected store_service_account to be called for upgrade"
                )

        elif hostcall == "hc_transfer":
            # hc_transfer adds to deferred_transfers in context
            if "expected-deferred-transfers-count" in test_vector:
                self.assertEqual(
                    test_vector["expected-deferred-transfers-count"],
                    len(context_item.deferred_transfers),
                    f"{name}: Expected {test_vector['expected-deferred-transfers-count']} deferred transfers, but got {len(context_item.deferred_transfers)}"
                )

            # verify transfer details if specified
            if "expected-deferred-transfers" in test_vector:
                for i, expected_transfer in enumerate(test_vector["expected-deferred-transfers"]):
                    if i < len(context_item.deferred_transfers):
                        actual_transfer = context_item.deferred_transfers[i]
                        if "sender" in expected_transfer:
                            self.assertEqual(
                                expected_transfer["sender"],
                                actual_transfer.sender,
                                f"{name}: Transfer {i} sender mismatch"
                            )
                        if "receiver" in expected_transfer:
                            self.assertEqual(
                                expected_transfer["receiver"],
                                actual_transfer.receiver,
                                f"{name}: Transfer {i} receiver mismatch"
                            )
                        if "amount" in expected_transfer:
                            self.assertEqual(
                                expected_transfer["amount"],
                                actual_transfer.amount,
                                f"{name}: Transfer {i} amount mismatch"
                            )

        elif hostcall == "hc_eject":
            # hc_eject removes a zombie service and transfers its balance
            # modifies service balances and removes preimage availability
            if "expected-service-balance" in test_vector:
                # Verify that the calling service's balance was updated
                for service_id, expected_balance in test_vector["expected-service-balance"].items():
                    # Check if store_service_account was called with updated balance
                    store_calls = services.store_service_account.call_args_list
                    balance_updated = False
                    for call in store_calls:
                        if call[0][0] == int(service_id):
                            stored_service = call[0][1]
                            if hasattr(stored_service, 'balance'):
                                self.assertEqual(
                                    expected_balance,
                                    stored_service.balance,
                                    f"{name}: Expected service {service_id} balance {expected_balance}, but got {stored_service.balance}"
                                )
                                balance_updated = True
                                break
                    if not balance_updated and int(service_id) == context_item.service_account_id:
                        # Check the service object directly
                        service = services.services.get(int(service_id))
                        if service:
                            self.assertEqual(
                                expected_balance,
                                service.balance,
                                f"{name}: Expected service {service_id} balance {expected_balance}, but got {service.balance}"
                            )

            if "expected-ejected-service" in test_vector:
                # Verify the zombie service was removed
                ejected_id = test_vector["expected-ejected-service"]
                # Check if delete_service_account or similar was called
                # Since we're using mocks, we can check if the service still exists
                self.assertNotIn(
                    ejected_id,
                    services.services,
                    f"{name}: Expected service {ejected_id} to be ejected (removed)"
                )

        elif hostcall == "hc_query":
            # hc_query retrieves service account information
            # it doesnt modify context, just reads and returns data
            pass

        elif hostcall == "hc_quit":
            # hc_quit adds storage item for preimage lookup
            # verified through services state modifications
            pass

        elif hostcall == "hc_solicit":
            # hc_solicit may add preimage availability
            # check if store_preimage_availability was called
            pass

        elif hostcall == "hc_forget":
            # hc_forget removes preimage availability
            # check if delete_preimage_availability was called
            pass

        elif hostcall == "hc_yield":
            # hc_yield sets invocation_output in context
            if "expected-invocation-output" in test_vector:
                self.assertIsNotNone(
                    context_item.invocation_output,
                    f"{name}: Expected invocation_output to be set after hc_yield"
                )
                if context_item.invocation_output:
                    expected_output = bytes.fromhex(test_vector["expected-invocation-output"])
                    self.assertEqual(
                        expected_output,
                        context_item.invocation_output,
                        f"{name}: Expected invocation_output {expected_output.hex()}, but got {context_item.invocation_output.hex()}"
                    )

        elif hostcall == "hc_provide":
            # hc_provide adds preimages to the context
            if "expected-preimages-count" in test_vector:
                self.assertEqual(
                    test_vector["expected-preimages-count"],
                    len(context_item.preimages),
                    f"{name}: Expected {test_vector['expected-preimages-count']} preimages, but got {len(context_item.preimages)}"
                )


if __name__ == '__main__':
    unittest.main()
