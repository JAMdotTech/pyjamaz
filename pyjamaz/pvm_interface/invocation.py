import logging
from copy import deepcopy
from typing import List, Dict

from jamcodec.base import JamBytes
from jamcodec.types import U32, U64

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import PREIMAGE_EXPUNGE_TIMESLOTS, SIZE_TRANSFER_MEMO, \
    MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, CORE_COUNT, VALIDATOR_COUNT
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import AccumulationOperand, ValidatorData
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, \
    AccumulateInvocationContext, AccumulatePvmArguments, ServiceAccount, DeferredTransfer, OnTransferPvmArguments, \
    OnTransferInvocationContext
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutator, InvocationMutationOutput, PVMInvocation
from pyjamaz.pvm.types import PVMMemory, PVMMemoryMode
from pyjamaz.pvm_interface.hostcalls.constants import HostCallGeneral, HostCallResult, HostCallAccumulate


class AccumulateInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: AccumulateInvocationContext,
            _pvm: PVMInterpreter  # TODO: TMP!
    ) -> InvocationMutationOutput:
        """
        B.10 | F ∈ Ω⟨(X,X)⟩∶(n,ρ,ω,μ,(x,y))
        TODO stub for host calls
        !!!!!!!!!!!!!!!!!!!!!!!
        """
        logging.debug(f'PVM host-call #{host_call_instr_nr}')

        #TODO: overal dees gebruiken!!!#@$@!$%@
        service_id = invocation_context.context.service_account_id
        state = invocation_context.context.state_context
        exit_condition = ExitCondition(reason=ExitReason.panic)

        if host_call_instr_nr == HostCallGeneral.gas.value:
            registers[7] = gas_limit - 10
            exit_condition = ExitCondition(reason=ExitReason.resume)
            _pvm.log.host_call("GAS", f"charged gas: {10} gas_before: {_pvm.gas} gas_after: {registers[7]}")

        elif host_call_instr_nr == HostCallGeneral.lookup.value:
            """
            Puts a Service Preimage blob into PVM memory
            """
            gas_limit -= 10
            _pvm.log.host_call("LOOKUP", f"charged gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            # GP: bold_a
            core_index = registers[7]
            if core_index in (service_id, 2 ** 64 - 1):
                eject_service_account = state.services.retrieve_service_account(service_id)
            else:
                try:
                    eject_service_account = state.services.retrieve_service_account(core_index)
                except StateKeyNoResult:
                    eject_service_account = None # bold_a = ∅

            preimage_hash = registers[8]  # offset to read image hash from pvm mem
            o = registers[9]  # offset to write image data to in pvm mem

            preimage_writable = True
            preimage_bytes = bytes() # GP: bold_v
            preimage_hash_unreadable = False
            if not memory.is_accessible(preimage_hash, 32, PVMMemoryMode.readable):
                preimage_hash_unreadable = True  #bold_v = ∇
            elif eject_service_account is None:
                preimage_bytes = None
            elif eject_service_account is not None:
                try:
                    preimage_bytes = state.services.retrieve_preimage(service_id, memory.read_bytes(preimage_hash, 32))

                    f = min(registers[10], len(preimage_bytes))
                    l = min(registers[11], len(preimage_bytes) - f)
                    preimage_writable = not memory.is_accessible(o, l, PVMMemoryMode.writable)  # bold_v = ∇
                except StateKeyNoResult:
                    preimage_bytes = None


            if preimage_hash_unreadable or preimage_writable is False:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("LOOKUP", f"PANIC")
            elif preimage_bytes is None:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.NONE.value
                _pvm.log.host_call("LOOKUP", f"NONE r7=HostCallResult.none")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = len(preimage_bytes)
                memory.write_bytes(f, preimage_bytes[f:f + l])
                _pvm.log.host_call("LOOKUP", f"NONE write_bytes({f},{f + l}) r7={len(preimage_bytes)}")

        elif host_call_instr_nr == HostCallGeneral.read.value:
            """
            Puts a Service StorageItem blob into PVM memory
            """
            gas_limit -= 10
            core_index = registers[7]
            service_id = invocation_context.context.service_account_id
            _pvm.log.host_call("READ", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            #gp: s*
            if core_index == 2 ** 64 - 1:
                new_service_id = service_id
            else:
                new_service_id = core_index

            #gp: bold_a
            state = invocation_context.context.state_context
            try:
                if new_service_id == service_id:
                    eject_service_account = state.services.retrieve_service_account(service_id)
                else:
                    eject_service_account = state.services.retrieve_service_account(new_service_id)
            except StateKeyNoResult as e:
                eject_service_account = None  #GP: bold_a = ∅

            k_o = registers[8]  # offset to read from memory
            k_z = registers[9]  # length to read from memory
            o = registers[10]  # offset where to write to in pvm mem

            # GP: bold_v (storage_item)
            storage_item_mem_error = False
            storage_item = None # bold_v
            if eject_service_account is not None:
                try:
                    new_service_id_bytes = int(new_service_id).to_bytes(length=4, byteorder="little")
                    storage_key = blake2b_256_hash(new_service_id_bytes + memory.read_bytes(k_o, k_z))
                    storage_item = state.services.retrieve_storage_item(service_account_id=new_service_id, storage_item_hash=storage_key)
                except StateKeyNoResult:
                    storage_item = None # bold_v = ∅
                except PVMMemoryError:
                    storage_item_mem_error = True
                    storage_item = None # bold_v = ∇

            f = min(registers[11], len(storage_item or bytes()))
            l = min(registers[12], len(storage_item or bytes()) - f)
            mem_writable = memory.is_accessible(o, l, PVMMemoryMode.writable)

            exit_condition = ExitCondition(reason=ExitReason.resume)
            if storage_item_mem_error or not mem_writable:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("READ", f"PANIC")
            elif storage_item is None:
                registers[7] = HostCallResult.NONE.value
                _pvm.log.host_call("READ", f"NONE r7=HostCallResult.none")
            else:
                registers[7] = len(storage_item)
                memory.write_bytes(o, storage_item[f:f+l])
                _pvm.log.host_call("READ", f"NONE write_bytes({len(storage_item[f:f+l])})")

        elif host_call_instr_nr == HostCallGeneral.write.value:
            """
            Writes/deletes a Service StorageItem blob
            """
            gas_limit -= 10
            _pvm.log.host_call("WRITE", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            k_o = registers[7]  # offset to read storage_item_key from memory
            k_z = registers[8]  # length to read storage_item_key from memory
            v_o = registers[9]  # offset to write storage_item_value from memory
            v_z = registers[10]  # length to write storage_item_value from memory

            state_context = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            service_id_bytes = int(service_id).to_bytes(length=4, byteorder="little")
            storage_key_mem_error = False
            service_storage_item_mem_error = False

            try:
                mu_k = memory.read_bytes(k_o, k_z) # Note: service local storage key
                storage_key = blake2b_256_hash(service_id_bytes + mu_k)  # GP: k
                eject_service_account = state_context.services.retrieve_service_account(service_id)
                try:
                    if v_z == 0:
                        service_storage_item = None # GP: bold_a (delete)
                    else:
                        service_storage_item = memory.read_bytes(v_o, v_z)  # GP: bold_a
                except PVMMemoryError:
                    service_storage_item_mem_error = True   #GP: a = ∇

                try:
                    si = state_context.services.retrieve_storage_item(service_id, storage_key)
                    l = len(si)
                except StateKeyNoResult:
                    si = None
                    l = HostCallResult.NONE.value

            except PVMMemoryError:
                storage_key_mem_error = True    #GP: k= ∇

            if storage_key_mem_error or service_storage_item_mem_error:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("WRITE", f"PANIC")
            elif eject_service_account.threshold_balance > eject_service_account.balance:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.FULL.value
                _pvm.log.host_call("WRITE", f"NONE r7=HostCallResult.full")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = l
                if service_storage_item is None:
                    invocation_context.context.state_context.services.delete_storage_item(
                        service_account_id=service_id,
                        storage_item_hash=storage_key
                    )
                    _pvm.log.host_call("WRITE", f"NONE delete_storage_item({service_id}, {storage_key}) mu_k={mu_k.hex()}")

                    # Update storage footprint
                    eject_service_account.update_footprint_remove_storage_item(len(si))

                else:
                    invocation_context.context.state_context.services.store_storage_item(
                        service_account_id=service_id,
                        storage_item_hash=storage_key,
                        value=service_storage_item,
                    )

                    # Update storage footprint
                    if si is None:
                        eject_service_account.update_footprint_add_storage_item(len(service_storage_item))
                        _pvm.log.host_call("WRITE", f"NONE store_storage_item s={service_id} mu_k={mu_k.hex()} k={storage_key.hex()} v={service_storage_item.hex()}")
                    else:
                        eject_service_account.update_footprint_update_storage_item(len(si), len(service_storage_item))
                        _pvm.log.host_call("WRITE", f"{len(si)} store_storage_item s={service_id} mu_k={mu_k.hex()} k={storage_key.hex()} v={service_storage_item.hex()}")

                # Update service_account TODO inefficient; move to end, only once per service
                # state.services.store_service_account(service_id, service_account)

        elif host_call_instr_nr == HostCallGeneral.info.value:
            """
            Writes ServiceAccount into PVM memory
            """
            gas_limit -= 10
            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            core_index = registers[7]
            _pvm.log.host_call("INFO", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            #gp: bold_t
            try:
                if core_index == 2 ** 64 - 1:
                    # TODO: nieuwe functie: retrieve_service_account_bytes -> nalopen waar allemaal toepassen
                    eject_service_account = state.services.retrieve_service_account(service_id)
                else:
                    eject_service_account = state.services.retrieve_service_account(core_index)
            except StateKeyNoResult:
                eject_service_account = None # t = ∅

            o = registers[8]

            service_account_bytes = None
            mem_write_error = False
            if eject_service_account:
                service_account_bytes = eject_service_account.to_serialized_bytes()  #GP: bold_m
                try:
                    memory.write_bytes(o, service_account_bytes)
                except PVMMemoryError:
                    mem_write_error = True

            exit_condition = ExitCondition(reason=ExitReason.resume)
            if mem_write_error:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("INFO", f"PANIC")
            elif service_account_bytes is None:
                registers[7] = HostCallResult.NONE.value
                _pvm.log.host_call("INFO", f"NONE r7=HostCallResult.none")
            else:
                registers[7] = HostCallResult.OK.value
                _pvm.log.host_call("INFO", f"NONE r7=HostCallResult.ok")

        elif host_call_instr_nr == HostCallAccumulate.bless.value:
            """
            State transition function for privileged services.
            Updates gas limits for privileged services
            """
            gas_limit -= 10
            _pvm.log.host_call("BLESS", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            # Privileged services:
            m = registers[7] # m: index of manager service (manager of chi(X))
            a = registers[8] # a: index of assign service (authorization queue)
            v = registers[9] # v: index of designate service (validator queue)

            o = registers[10] # offset to read service indices and accompanying gas limits from
            n = registers[11] # number of entries in the auto_accumulate_services dictionary to read

            auto_accumulate_services = None #GP: bold_g
            if memory.is_accessible(o, o + 12 * n, PVMMemoryMode.readable):
                try:
                    auto_accumulate_services = {}
                    for idx in range(n):
                        offset = o + idx * 12
                        service_idx = U32.decode(memory.read_bytes(offset, 4))
                        gas = U64.decode(memory.read_bytes(offset + 4, 4+8))
                        auto_accumulate_services[service_idx] = gas
                except PVMMemoryError:
                    auto_accumulate_services = None   # bold_g = ∇

            try:
                service_exists = any(state.services.retrieve_service_account(idx) for idx in [m, a, v])
            except StateKeyNoResult:
                service_exists = False

            if auto_accumulate_services is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("BLESS", f"PANIC")
            #TODO: volgens GP hoeven we alleen ints te checken?
            #elif any(idx >= 2**32 for idx in [m, a, v]):
            elif service_exists:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.WHO.value
                _pvm.log.host_call("BLESS", f"WHO")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value

                ps = invocation_context.context.state_context.privileged_services   #
                ps.empower_service = m
                ps.assign_service = a
                ps.designate_service = v
                ps.auto_accumulate_services = auto_accumulate_services

                _pvm.log.host_call("BLESS", f"OK")


        elif host_call_instr_nr == HostCallAccumulate.assign.value:
            """
            Update authorization queue (state transition function of Phi)
            """
            gas_limit -= 10
            _pvm.log.host_call("ASSIGN", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            # Privileged services:
            core_index = registers[7] # Core index to update (0..341)
            o = registers[8] # memory offset

            if memory.is_accessible(o, 32 * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS, PVMMemoryMode.readable):
                validator_queue = [] #GP: bold_c
                try:
                    for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                        offset = o + idx * 32
                        validator_queue.append(memory.read_bytes(offset, 32))
                except PVMMemoryError:
                    validator_queue = None
            else:
                validator_queue = None # bold_c = ∇

            if validator_queue is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("ASSIGN", f"PANIC")
            elif core_index >= CORE_COUNT:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.CORE.value
                _pvm.log.host_call("ASSIGN", f"CORE")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value
                invocation_context.context.state_context.authorizer_queues.authorizer_queues[core_index] = validator_queue
                _pvm.log.host_call("ASSIGN", f"OK")

        elif host_call_instr_nr == HostCallAccumulate.designate.value:
            """
            Update the validator Queue (State transition function for the validator queue)
            """
            gas_limit -= 10
            _pvm.log.host_call("DESIGNATE", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            o = registers[7] # memory offset

            if memory.is_accessible(o, 336 * VALIDATOR_COUNT, PVMMemoryMode.readable):
                validator_queue = [] #GP: bold_v
                try:
                    for idx in range(MAXIMUM_AUTHORIZATION_QUEUE_ITEMS):
                        offset = o + idx * 336
                        validator_data = ValidatorData.from_jam_bytes(JamBytes(memory.read_bytes(offset, 336)))
                        validator_queue.append(validator_data)
                except PVMMemoryError:
                    validator_queue = None # GP: bold_v = ∇
            else:
                validator_queue = None # GP: bold_v = ∇

            if validator_queue is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("DESIGNATE", f"PANIC")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value
                invocation_context.context.state_context.validator_queue.validators = validator_queue
                _pvm.log.host_call("DESIGNATE", f"OK")

        elif host_call_instr_nr == HostCallAccumulate.checkpoint.value:
            """
            Copy the invocation result context x to y
            """
            gas_limit -= 10
            _pvm.log.host_call("CHECKPOINT", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")
            registers[7] = gas_limit
            exit_condition = ExitCondition(reason=ExitReason.resume)
            invocation_context.savepoint_context = deepcopy(invocation_context.context) #TODO: optimize deepcopy?

        elif host_call_instr_nr == HostCallAccumulate.new.value:
            # Maak nieuwe service aan en registreer deze in de services dictionary

            gas_limit -= 10
            _pvm.log.host_call("NEW", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            o = int(registers[7])  # offset to read service data from
            l = int(registers[8])  # size (byte length) of the code blob
            g = int(registers[9])  # gas_limit_accumulate
            m = int(registers[10])  # gas_limit_on_transfer

            try:
                code_hash = memory.read_bytes(o, 32)  # GP: c
            except PVMMemoryError:
                code_hash = None

            eject_service_account = None
            new_service_id = None
            deducted_balance = None
            new_service_account = None  # GP: bold_s
            if not code_hash is None:
                new_service_account = ServiceAccount(
                    code_hash=code_hash,
                    balance=0,
                    gas_limit_accumulate=g,
                    gas_limit_on_transfer=m,
                    footprint_storage_items=0,
                    footprint_storage_bytes=0,
                    storage_items={},  # bold_s
                    preimages={},  # bold_p
                    preimage_availability={}  # {(code_hash, l): []} #bold_l
                )
                new_service_id = invocation_context.context.new_service_account_id

                # TODO move to store_preimage_availability() ?
                new_service_account.update_footprint_add_preimage(l)

                new_service_account.balance = new_service_account.threshold_balance

                eject_service_account = state.services.retrieve_service_account(service_id)
                deducted_balance = eject_service_account.balance - new_service_account.threshold_balance

            if code_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("NEW", f"PANIC")
            elif deducted_balance < eject_service_account.threshold_balance:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.CASH.value
                _pvm.log.host_call("NEW", f"CASH")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = new_service_id
                updated_new_service_id = 2 ** 8 + (new_service_id - 2 ** 8 + 42) % (2 ** 32 - 2 ** 9)
                invocation_context.context.new_service_account_id = invocation_context.context.state_context.check_service_id(
                    updated_new_service_id)
                eject_service_account.balance = deducted_balance

                # TODO inefficient; move to end, only once per service
                state.services.store_service_account(service_id, eject_service_account)

                # TODO inefficient; move to end, only once per service
                state.services.store_service_account(new_service_id, new_service_account)

                state.services.store_preimage_availability(new_service_id, code_hash, l, [])

                _pvm.log.host_call("NEW", f"OK")

        elif host_call_instr_nr == HostCallAccumulate.upgrade.value:
            """
            Updates codehash and gas limits for a service account
            """
            gas_limit -= 10
            _pvm.log.host_call("UPGRADE", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            o = registers[7]  # offset for service codehash
            g = registers[8]  # gas_limit_accumulate
            m = registers[9]  # gas_limit_on_transfer

            service_id = invocation_context.context.service_account_id
            service_account = state.services.retrieve_service_account(service_id)

            try:
                code_hash = memory.read_bytes(o, 32)
            except PVMMemoryError:
                code_hash = None # GP: c = ∇

            if code_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("UPGRADE", f"PANIC")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value
                service_account.code_hash = code_hash
                service_account.gas_limit_accumulate = g
                service_account.gas_limit_on_transfer = m
                # TODO inefficient; move to end, only once per service
                state.services.store_service_account(service_id, service_account)

                _pvm.log.host_call("UPGRADE", f"OK")

        elif host_call_instr_nr == HostCallAccumulate.transfer.value:
            # Create a new transfer and add to the defered transfers
            #TODO:!!!!!!!!!!!!!!!!!!!!!!!!gas_cost = 10 + int(registers[9])
            gas_cost = int(registers[9])
            gas_limit -= gas_cost
            _pvm.log.host_call("TRANSFER", f"charged_gas: {gas_cost} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            d = int(registers[7])      # destination
            a = int(registers[8])      # amount
            g = int(registers[9])      # gas_limit
            o = int(registers[10])     # offset for memo

            eject_service_account = state.services.retrieve_service_account(service_id)
            try:
                dest_service_account = state.services.retrieve_service_account(d)   #GP: bold_d
            except StateKeyNoResult:
                dest_service_account = None

            try:
                m = memory.read_bytes(o, SIZE_TRANSFER_MEMO)   # Transaction Memo (blob)
                # GP: bold_t
                transfer = DeferredTransfer(
                    sender=service_id,
                    receiver=d,
                    amount=a,
                    memo=m,
                    gas_limit=g,
                )
                b = eject_service_account.balance - a
            except PVMMemoryError:
                transfer = None
                b = None

            if transfer is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
            elif dest_service_account is None:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.WHO.value
                _pvm.log.host_call("TRANSFER WHO", f"")
            elif g < dest_service_account.gas_limit_on_transfer:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.LOW.value
                _pvm.log.host_call("TRANSFER LOW", f"")
            elif b < eject_service_account.threshold_balance:   # insufficient funds
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.CASH.value
                _pvm.log.host_call("TRANSFER CASH", f"")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value
                eject_service_account.balance = b
                invocation_context.context.deferred_transfers.append(transfer)

                # TODO inefficient; move to end, only once per service
                state.services.store_service_account(service_id, eject_service_account)

                _pvm.log.host_call("TRANSFER OK", f"sender={transfer.sender} receiver={transfer.receiver} amount={transfer.amount} gaslimit={transfer.gas_limit}")

        elif host_call_instr_nr == HostCallAccumulate.eject.value:
            """
            Reads a ??? hash and returns that back into Xy????
            """
            gas_limit -= 10
            _pvm.log.host_call("EJECT", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            d = registers[7]
            o = registers[8]

            # gp: h
            try:
                preimage_hash = memory.read_bytes(o, 32)
            except PVMMemoryError:
                preimage_hash = None

            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            service_account = state.services.retrieve_service_account(service_id)

            l = None
            updated_balance = None
            preimage_availability = None
            eject_service_account = None  # GP: bold_d
            if d != service_id:
                try:
                    eject_service_account = state.services.retrieve_service_account(d)
                    l = max(81, eject_service_account.footprint_storage_bytes) - 81
                    updated_balance = service_account.balance + eject_service_account.balance
                    try:
                        preimage_availability = state.services.retrieve_preimage_availability(d, preimage_hash, l)
                    except StateKeyNoResult:
                        preimage_availability = None
                except StateKeyNoResult as e:
                    eject_service_account = None  #GP: bold_d = ∇

            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("EJECT", f"PANIC")
            elif eject_service_account is None or eject_service_account.code_hash != int(service_id).to_bytes(length=32, byteorder="little"):
                # Note: eject service grants eject by setting code_hash to current service_id
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.WHO.value
                _pvm.log.host_call("EJECT", f"WHO")
            elif eject_service_account.footprint_storage_items != 2 or preimage_availability is None:
                # Note: if this storage_account emptied and the preimage exists
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.HUH.value
                _pvm.log.host_call("EJECT", f"HUH")
            elif len(preimage_availability) == 2 and preimage_availability[1] < invocation_context.timeslot - PREIMAGE_EXPUNGE_TIMESLOTS:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value

                # TODO: nodig?
                state.services.delete_preimage(d, preimage_hash)
                state.services.delete_preimage_availability(d, preimage_hash, l)
                state.services.delete_service_account(d)
                service_account.balance = updated_balance
                state.services.store_service_account(service_id, service_account) # TODO: meenemen in de finalize vd transactie
                _pvm.log.host_call("EJECT", f"OK")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.HUH.value
                _pvm.log.host_call("EJECT", f"HUH")

        elif host_call_instr_nr == HostCallAccumulate.query.value:
            """
            Determines the availability of a preimage 
            """
            gas_limit -= 10
            _pvm.log.host_call("QUERY", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            o = registers[7]    # memory offset
            preimage_length = registers[8]    # preimage length

            # GP: h
            try:
                preimage_hash = memory.read_bytes(o, 32)
            except PVMMemoryError:
                preimage_hash = None

            # GP: bold_a
            try:
                preimage_availability = state.services.retrieve_preimage_availability(service_id, preimage_hash, preimage_length) # GP: (xs)l[h,z] == bold_a
            except StateKeyNoResult as e:
                preimage_availability = None

            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("QUERY", f"PANIC")
            elif preimage_availability is None:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.NONE.value
                registers[8] = 0
                _pvm.log.host_call("QUERY", f"NONE, 0")
            elif len(preimage_availability) == 0:
                # Note: Marked as requested
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = 0
                registers[8] = 0
                _pvm.log.host_call("QUERY", f"0, 0")
            elif len(preimage_availability) == 1:
                # Note: Marked as available
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = 1+2**32*preimage_availability[0]
                registers[8] = 0
                _pvm.log.host_call(f"QUERY", f"1+2**32*{preimage_availability[0]}, 0")
            elif len(preimage_availability) == 2:
                # Note: Marked as unavailable
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = 2+2**32*preimage_availability[0]
                registers[8] = preimage_availability[1]
                _pvm.log.host_call(f"QUERY", f"1+2**32*{preimage_availability[0]}, {preimage_availability[1]}")
            elif len(preimage_availability) == 3:
                # Note: Marked as re-available
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = 3+2**32*preimage_availability[0]
                registers[8] = preimage_availability[1] + 2**32*preimage_availability[2]
                _pvm.log.host_call(f"QUERY", f"1+2**32*{preimage_availability[0]}, {preimage_availability[1] + 2**32*preimage_availability[2]}")
            else:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("QUERY", f"preimage cardinality error: {len(preimage_availability)}")

        elif host_call_instr_nr == HostCallAccumulate.solicit.value:
            """
            Modifies the preimage availability lookup (requests a preimage to be made available)
            """
            gas_limit -= 10
            _pvm.log.host_call("SOLICIT", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            service_account = state.services.retrieve_service_account(service_id) # GP: bold_a

            o = registers[7]
            preimage_length = registers[8]    # GP: z

            #GP: h
            try:
                preimage_hash = memory.read_bytes(o, 32)
            except PVMMemoryError:
                preimage_hash = None #GP: h = ∇

            try:
                preimage_availability = state.services.retrieve_preimage_availability(service_id, preimage_hash, preimage_length)
            except StateKeyNoResult:
                preimage_availability = None

            old_footprint_items = service_account.footprint_storage_items
            old_footprint_bytes = service_account.footprint_storage_bytes

            if not preimage_hash is None:
                service_account.update_footprint_add_preimage(preimage_length)

            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                service_account.footprint_storage_items = old_footprint_items
                service_account.footprint_storage_bytes = old_footprint_bytes
                _pvm.log.host_call("SOLICIT", f"PANIC")
            elif preimage_availability is not None and len(preimage_availability) != 2:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.HUH.value
                service_account.footprint_storage_items = old_footprint_items
                service_account.footprint_storage_bytes = old_footprint_bytes
                _pvm.log.host_call("SOLICIT", f"HUH")
            elif service_account.balance < service_account.threshold_balance:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.FULL.value
                service_account.footprint_storage_items = old_footprint_items
                service_account.footprint_storage_bytes = old_footprint_bytes
                _pvm.log.host_call("SOLICIT", f"FULL")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value

                if preimage_availability is None:
                    state.services.store_preimage_availability(
                        service_id,
                        preimage_hash,
                        preimage_length,
                        []
                    )

                elif len(preimage_availability) == 2:
                    state.services.store_preimage_availability(
                        service_id,
                        preimage_hash,
                        preimage_length,
                        preimage_availability + [invocation_context.timeslot]
                    )

                _pvm.log.host_call("SOLICIT", f"OK")

        elif host_call_instr_nr == HostCallAccumulate.forget.value:
            """
            Deletes PreimageAvailability (status queue)
            """
            gas_limit -= 10
            _pvm.log.host_call("FORGET", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            eject_service_account = state.services.retrieve_service_account(service_id)
            o = registers[7]
            preimage_length = registers[8]  #GP: z

            #GP: h
            try:
                preimage_hash = memory.read_bytes(o, 32)
            except PVMMemoryError:
                preimage_hash = None #GP: h = ∇

            timeslot = invocation_context.timeslot #GP: t
            # Note: x & y & w refer to the cardinality of the preimage_availability dictionary, see 9.2.2 EQ9.7
            preimage_updated = True #GP: bold_a = ∇

            try:
                preimage_availability = state.services.retrieve_preimage_availability(service_id, preimage_hash, preimage_length)

                preimage_cardinality = len(preimage_availability)
                if preimage_cardinality in (0, 2) and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):
                    state.services.delete_preimage_availability(service_id, preimage_hash, preimage_length)
                    state.services.delete_preimage(service_id, preimage_hash)
                    # Update footprint
                    eject_service_account.update_footprint_remove_preimage(preimage_length)
                elif preimage_cardinality == 1:
                    state.services.store_preimage_availability(
                        service_id,
                        preimage_hash,
                        preimage_length,
                        preimage_availability + [timeslot]
                    )
                elif preimage_cardinality == 3 and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):
                    # Note: reset unreferenced preimage expunge time with current timeslot
                    state.services.store_preimage_availability(
                        service_id,
                        preimage_hash,
                        preimage_length,
                        [preimage_availability[2], timeslot]
                    )
                else:
                    preimage_updated = False
            except StateKeyNoResult:
                preimage_updated = False

            exit_condition = ExitCondition(reason=ExitReason.resume)
            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("FORGET", f"PANIC")
            elif preimage_updated is False:
                registers[7] = HostCallResult.HUH.value
                _pvm.log.host_call("FORGET", f"NONE r7=HostCallResult.huh")
            else:
                registers[7] = HostCallResult.OK.value
                _pvm.log.host_call("FORGET", f"NONE r7=HostCallResult.ok")

        elif host_call_instr_nr == HostCallAccumulate._yield.value:
            """
            Reads a ??? hash and returns that back into Xy????
            """
            gas_limit -= 10
            _pvm.log.host_call("YIELD", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")
            o = registers[7]

            # gp: h
            if memory.is_accessible(o, 32, PVMMemoryMode.readable):
                preimage_hash = memory.read_bytes(o, 32)
            else:
                preimage_hash = None

            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("YIELD", f"PANIC")
            else:
                exit_condition = ExitCondition(reason=ExitReason.resume)
                registers[7] = HostCallResult.OK.value
                invocation_context.invocation_output = preimage_hash
                _pvm.log.host_call("YIELD", f"NONE r7:HostCallResult.ok invocation_output={preimage_hash.hex()}")


        else:
            raise Exception(f"TODO!!!!!!!! {host_call_instr_nr}")

        return InvocationMutationOutput(
            output=exit_condition,
            gas_limit=gas_limit,
            registers=registers,
            memory=memory,
            context=invocation_context
        )

class OnTransferInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: OnTransferInvocationContext,
            _pvm: PVMInterpreter  # TODO: TMP!
    ) -> InvocationMutationOutput:

        return InvocationMutationOutput(
            output=ExitCondition(reason=ExitReason.none),
            gas_limit=gas_limit,
            registers=registers,
            memory=memory,
            context=invocation_context
        )

def pvm_invoke_accumulate(
        state_context: AccumulationStateComponents,
        timeslot: int,
        service_id: int,
        gas_limit: int,
        operands: List[AccumulationOperand],
        post_entropy: EntropyState
) -> PvmAccumulateOutput:
    """
    GP-0.6.2-eq:B.8 (Ψ_A) | Accumulation invocation function

    Parameters
    ----------
    state_context: AccumulationStateComponents
    timeslot: int
    service_id: int
    gas_limit: int
    operands: List[AccumulationOperand]

    Returns
    -------
    PvmAccumulateOutput
    """

    logging.debug(f'PVM invoke accumulate: s={service_id} operands={[o.to_json() for o in operands]}')

    invocation_context = state_context.to_invocation_context(
        service_account_id=service_id,
        entropy=post_entropy.entropy[0],
        timeslot=timeslot
    )
    try:
        code_hash = state_context.services.services[service_id].code_hash
        serialized_program = state_context.services.services[service_id].preimages[code_hash]
    except KeyError:
        # program not found
        return PvmAccumulateOutput(
            state_context=state_context,
            deferred_transfers=[],
            accumulation_output=None,
            gas_limit=0
        )

    argument_data = AccumulatePvmArguments(
        timeslot=timeslot,
        service_id=service_id,
        operands=operands,
    ).to_jam_bytes().to_bytes()

    pvm_invocation = PVMInvocation(
        invocation_context=invocation_context,
        invocation_mutator=AccumulateInvocationMutator()
    )

    marshalling_output = pvm_invocation.pvm_invoke_marshalling(
        serialized_program=serialized_program,
        start_offset=5,
        gas_limit=gas_limit,
        argument_data=argument_data
    )

    # GP-0.6.2-eq:B.12 (C)
    if marshalling_output.exit_condition.reason in [ExitReason.out_of_gas, ExitReason.panic]:

        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.savepoint_context.state_context,
            deferred_transfers=marshalling_output.context.savepoint_context.deferred_transfers,
            accumulation_output=marshalling_output.context.savepoint_context.invocation_output,
            gas_limit=marshalling_output.gas_limit
        )
        logging.debug(f'PVM accumulate failed: {marshalling_output.exit_condition.reason}')
    elif marshalling_output.exit_condition.reason == ExitReason.halt and len(marshalling_output.exit_condition.value) > 0:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.exit_condition.value,
            gas_limit=marshalling_output.gas_limit
        )
        logging.debug(f'PVM accumulate succesful, output=0x{output.accumulation_output.hex()}')
    else:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.context.context.invocation_output,
            gas_limit=marshalling_output.gas_limit
        )
        logging.error(f'PVM accumulate failed')

    return output


def pvm_invoke_on_transfer(
        services: Dict[int, ServiceAccount],
        timeslot: int,
        service_id: int,
        deferred_transfers: List[DeferredTransfer]
) -> ServiceAccount:
    """
    GP-0.6.2-eq:B.14 (Ψ_T) | the on-transfer service-account invocation function

    Parameters
    ----------
    services: Dict[int, ServiceAccount]
    timeslot: int
    service_id: int
    deferred_transfers: List[DeferredTransfer]

    Returns
    -------
    ServiceAccount
    """

    service_account = services.get(service_id)

    if len(deferred_transfers) > 0:
        logging.debug(f'PVM invoke on_transfer: s={service_id} t={[t.to_json() for t in deferred_transfers]}')

        # Update balance
        service_account.balance += sum([t.amount for t in deferred_transfers])

        serialized_program = service_account.preimages.get(service_account.code_hash)

        if serialized_program:

            argument_data = OnTransferPvmArguments(
                timeslot=timeslot,
                service_id=service_id,
                deferred_transfers=deferred_transfers,
            ).to_jam_bytes().to_bytes()

            pvm_invocation = PVMInvocation(
                invocation_context=OnTransferInvocationContext(service_account=service_account),
                invocation_mutator=OnTransferInvocationMutator()
            )

            gas_limit = sum([t.gas_limit for t in deferred_transfers])

            marshalling_output = pvm_invocation.pvm_invoke_marshalling(
                serialized_program=serialized_program,
                start_offset=10,
                gas_limit=gas_limit,
                argument_data=argument_data
            )

            service_account = marshalling_output.context

    return service_account
