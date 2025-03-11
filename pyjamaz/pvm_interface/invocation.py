import logging
from typing import List

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import PREIMAGE_EXPUNGE_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, \
    AccumulateInvocationContext, ArgumentData, ServiceAccount
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.duna_logger import PVMDunaLog
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

        if host_call_instr_nr == HostCallGeneral.gas.value:
            registers[7] = gas_limit - 10
            _pvm.log.host_call("GAS", f"charged gas: {10} gas_before: {_pvm.gas} gas_after: {registers[7]}")

            return InvocationMutationOutput(
                output=ExitCondition(reason=ExitReason.none),
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == HostCallGeneral.lookup.value:
            """
            Puts a Service Preimage blob into PVM memory
            """
            gas_limit -= 10
            service_id = invocation_context.context.service_account_id
            state = invocation_context.context.state_context
            _pvm.log.host_call("LOOKUP", f"charged gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            # GP: bold_a
            w7 = registers[7]
            if w7 in (service_id, 2 ** 64 - 1):
                service_account = state.services.retrieve_service_account(service_id)
            else:
                try:
                    service_account = state.services.retrieve_service_account(w7)
                except:
                    service_account = None # bold_a = ∅

            h = registers[8]  # offset to read image hash from pvm mem
            o = registers[9]  # offset to write image data to in pvm mem

            preimage_bytes = bytes() # GP: bold_v
            preimage_unreadable = False
            if not memory.is_accessible(h, 32, PVMMemoryMode.readable):
                preimage_unreadable = True  #bold_v = ∇
            if service_account is not None and not preimage_unreadable:
                preimage_bytes = service_account.preimages.get(memory.read_bytes(h, 32), None)
                f = min(registers[10], len(preimage_bytes))
                l = min(registers[11], len(preimage_bytes) - f)
                preimage_unreadable = not memory.is_accessible(o, l, PVMMemoryMode.readable)  #bold_v = ∇

            exit_condition = ExitCondition(reason=ExitReason.none)
            if preimage_unreadable:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("LOOKUP", f"PANIC")
            elif service_account is None:
                registers[7] = HostCallResult.none.value
                _pvm.log.host_call("LOOKUP", f"NONE r7=HostCallResult.none")
            else:
                registers[7] = len(preimage_bytes)
                memory.write_bytes(f, preimage_bytes[f:f + l])
                _pvm.log.host_call("LOOKUP", f"NONE write_bytes({f},{f + l}) r7={len(preimage_bytes)}")

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == HostCallGeneral.read.value:
            """
            Puts a Service StorageItem blob into PVM memory
            """
            gas_limit -= 10
            w7 = registers[7]
            service_id = invocation_context.context.service_account_id
            _pvm.log.host_call("READ", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            #gp: s*
            if w7 == 2 ** 64 - 1:
                new_service_id = service_id
            else:
                new_service_id = w7

            #gp: bold_a
            state = invocation_context.context.state_context
            try:
                if new_service_id == service_id:
                    service_account = state.services.retrieve_service_account(service_id)
                else:
                    service_account = state.services.retrieve_service_account(new_service_id)
            except StateKeyNoResult as e:
                service_account = None  #GP: bold_a = ∅

            k_o = registers[8]  # offset to read from memory
            k_z = registers[9]  # length to read from memory
            o = registers[10]  # offset where to write to in pvm mem

            # GP: bold_v (storage_item)
            storage_item_mem_error = False
            storage_item = None # bold_v
            if service_account is not None:
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

            exit_condition = ExitCondition(reason=ExitReason.none)
            if storage_item_mem_error or not mem_writable:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("READ", f"PANIC")
            elif storage_item is None:
                registers[7] = HostCallResult.none.value
                _pvm.log.host_call("READ", f"NONE r7=HostCallResult.none")
            else:
                registers[7] = len(storage_item)
                memory.write_bytes(o, storage_item[f:f+l])
                _pvm.log.host_call("READ", f"NONE write_bytes({len(storage_item[f:f+l])})")

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

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
                storage_key = blake2b_256_hash(service_id_bytes + memory.read_bytes(k_o, k_z))  # GP: k
                service_account = state_context.services.retrieve_service_account(service_id)
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
                    l = HostCallResult.none.value

            except PVMMemoryError:
                storage_key_mem_error = True    #GP: k= ∇

            output = ExitCondition(reason=ExitReason.none)

            if storage_key_mem_error or service_storage_item_mem_error:
                output = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("WRITE", f"PANIC")
            elif service_account.threshold_balance > service_account.balance:
                registers[7] = HostCallResult.full.value
                _pvm.log.host_call("WRITE", f"NONE r7=HostCallResult.full")
            else:
                registers[7] = l
                if service_storage_item is None:
                    invocation_context.context.state_context.services.delete_storage_item(
                        service_account_id=service_id,
                        storage_item_hash=storage_key
                    )
                    _pvm.log.host_call("WRITE", f"NONE delete_storage_item({service_id}, {storage_key})")
                else:
                    invocation_context.context.state_context.services.store_storage_item(
                        service_account_id=service_id,
                        storage_item_hash=storage_key,
                        value=service_storage_item,
                    )
                    _pvm.log.host_call("WRITE", f"NONE store_storage_item({service_id}, {storage_key})")

            return InvocationMutationOutput(
                output=output,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == HostCallGeneral.info.value:
            """
            Writes ServiceAccount into PVM memory
            """
            gas_limit -= 10
            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            w7 = registers[7]
            _pvm.log.host_call("INFO", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            #gp: bold_t
            try:
                if w7 == 2 ** 64 - 1:
                    # TODO: nieuwe functie: retrieve_service_account_bytes -> nalopen waar allemaal toepassen
                    service_account = state.services.retrieve_service_account(service_id)
                else:
                    service_account = state.services.retrieve_service_account(w7)
            except StateKeyNoResult:
                service_account = None # t = ∅

            o = registers[8]

            service_account_bytes = None
            mem_write_error = False
            if service_account:
                service_account_bytes = service_account.to_serialized_bytes2()  #GP: bold_m
                try:
                    memory.write_bytes(o, service_account_bytes)
                except PVMMemoryError:
                    mem_write_error = True

            exit_condition = ExitCondition(reason=ExitReason.none)
            if mem_write_error:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("INFO", f"PANIC")
            elif service_account_bytes is None:
                registers[7] = HostCallResult.none.value
                _pvm.log.host_call("INFO", f"NONE r7=HostCallResult.none")
            else:
                registers[7] = HostCallResult.ok.value
                _pvm.log.host_call("INFO", f"NONE r7=HostCallResult.ok")

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == HostCallAccumulate.forget.value:
            """
            Deletes PreimageAvailability (status queue)
            """
            gas_limit -= 10
            _pvm.log.host_call("FORGET", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")

            state = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            service_account = state.services.retrieve_service_account(service_id)
            o = registers[7]
            preimage_length = registers[8]  #GP: z

            #GP: h
            if memory.is_accessible(o, 32, PVMMemoryMode.readable):
                preimage_hash = memory.read_bytes(o, 32)
            else:
                preimage_hash = None #GP: h = ∇

            timeslot = 0 #GP: t  #TODO: invocation_context.context.state_context.timeslot
            # Note: x & y & w refer to the cardinality of the preimage_availability dictionary, see 9.2.2 EQ9.7
            preimage_updated = True #GP: bold_a = ∇
            preimage_availability = service_account.preimage_availability.get((preimage_hash,preimage_length), None)
            if preimage_availability:
                preimage_cardinality = len(preimage_availability)
                if preimage_cardinality in (0, 2) and preimage_availability[1] < (timeslot - PREIMAGE_EXPUNGE_TIMESLOTS):
                    state.services.delete_preimage_availability(service_id, preimage_hash, preimage_length)
                    state.services.delete_preimage(service_id, preimage_hash)
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
            else:
                preimage_updated = False


            exit_condition = ExitCondition(reason=ExitReason.none)
            if preimage_hash is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
                _pvm.log.host_call("FORGET", f"PANIC")
            elif preimage_updated is False:
                registers[7] = HostCallResult.huh.value
                _pvm.log.host_call("FORGET", f"NONE r7=HostCallResult.huh")
            else:
                registers[7] = HostCallResult.ok.value
                _pvm.log.host_call("FORGET", f"NONE r7=HostCallResult.ok")

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == HostCallAccumulate._yield.value:
            """
            Reads a ??? hash and returns that back into Xy????
            """
            gas_limit -= 10
            _pvm.log.host_call("YIELD", f"charged_gas: {10} gas_before: {_pvm.gas} gas_after: {gas_limit}")
            # state = invocation_context.context.state_context
            # service_id = invocation_context.context.service_account_id
            # service_account = state.services.retrieve_service_account(service_id)
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
                exit_condition = ExitCondition(reason=ExitReason.none)
                registers[7] = HostCallResult.ok.value
                invocation_context.invocation_output = preimage_hash
                _pvm.log.host_call("YIELD", f"NONE r7:HostCallResult.ok invocation_output={preimage_hash}")

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        else:
            raise Exception(f"TODO!!!!!!!! {host_call_instr_nr}")


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

    logging.debug(f'PVM invoke accumulate: service ID {service_id}')

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

    argument_data = ArgumentData(
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

