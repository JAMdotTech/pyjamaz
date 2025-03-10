import logging
from typing import List

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, \
    AccumulateInvocationContext, ArgumentData
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutator, InvocationMutationOutput, PVMInvocation
from pyjamaz.pvm.types import PVMMemory
from pyjamaz.pvm_interface.hostcalls.constants import HostCallGeneral, HostCallResult


class AccumulateInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: AccumulateInvocationContext
    ) -> InvocationMutationOutput:
        """
        B.10 | F ∈ Ω⟨(X,X)⟩∶(n,ρ,ω,μ,(x,y))
        TODO stub for host calls
        !!!!!!!!!!!!!!!!!!!!!!!
        """

        if host_call_instr_nr == 0:
            registers[7] = gas_limit - 10

        elif host_call_instr_nr == 2:
            """
            Read from disk to memory
            Puts a Service StorageItem blob into PVM memory
            """
            gas_limit -= 10
            w7 = registers[7]
            service_id = invocation_context.context.service_account_id

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
                service_account = None

            k_o = registers[8]  # offset to read from memory
            k_z = registers[9]  # length to read from memory
            o = registers[10]  # offset where to write to in pvm mem

            # gp: bold_v (storage_item)
            storage_item_mem_error = False
            mem_blob = None
            storage_item = None
            if service_account is not None:
                try:
                    new_service_id_bytes = int(new_service_id).to_bytes(length=4, byteorder="little")
                    storage_key = blake2b_256_hash(new_service_id_bytes + memory.read_bytes(k_o, k_z))
                    storage_item = state.services.retrieve_storage_item(service_account_id=new_service_id, storage_item_hash=storage_key)
                    f = min(registers[11], len(storage_item))
                    l = min(registers[12], len(storage_item) - f)
                    mem_blob = memory.read_bytes(o, l)
                except StateKeyNoResult:
                    storage_item = None
                    mem_blob = bytes(0)
                except PVMMemoryError:
                    storage_item_mem_error = True
                    storage_item = None

            exit_condition = ExitCondition(reason=ExitReason.none)
            if storage_item_mem_error or mem_blob is None:
                exit_condition = ExitCondition(reason=ExitReason.panic)
            elif storage_item is None:
                registers[7] = HostCallResult.none.value
            else:
                registers[7] = len(storage_item)
                memory.write_bytes(o, storage_item[f:f+l])

            return InvocationMutationOutput(
                output=exit_condition,
                gas_limit=gas_limit,
                registers=registers,
                memory=memory,
                context=invocation_context
            )

        elif host_call_instr_nr == 3:
            gas_limit -= 10

            k_o = registers[7]  # offset to read storage_item_key from memory
            k_z = registers[8]  # length to read storage_item_key from memory
            v_o = registers[9]  # offset to write storage_item_value from memory
            v_z = registers[10]  # length to write storage_item_value from memory

            state_context = invocation_context.context.state_context
            service_id = invocation_context.context.service_account_id
            service_id_bytes = int(service_id).to_bytes(length=4, byteorder="little")
            try:
                storage_key = blake2b_256_hash(service_id_bytes + memory.read_bytes(k_o, k_z))
            except PVMMemoryError:
                storage_key = "∇"

            service_account = state_context.services.retrieve_service_account(service_id)

            try:
                if v_z == 0:
                    service_storage_item = None
                else:
                    service_storage_item = memory.read_bytes(v_o, v_z)
            except PVMMemoryError:
                service_storage_item = "∇"

            try:
                si = state_context.services.retrieve_storage_item(service_id, storage_key)
                l = len(si)
            except StateKeyNoResult:
                l = HostCallResult.none.value

            output = ExitCondition(reason=ExitReason.none)
            if storage_key == "∇" or service_storage_item == "∇":
                output = ExitCondition(reason=ExitReason.panic)
            elif service_account.threshold_balance > service_account.balance:
                registers[7] = HostCallResult.full.value
            else:
                registers[7] = l
                invocation_context.context.state_context.services.store_storage_item(
                    service_account_id=service_id,
                    storage_item_hash=storage_key,
                    value=service_storage_item,
                )
                # service_account.storage_items[storage_key] = service_storage_item

            return InvocationMutationOutput(
                output=output,
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
    elif marshalling_output.exit_condition.reason == ExitReason.halt and len(marshalling_output.exit_condition.value) > 0:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.exit_condition.value,
            gas_limit=marshalling_output.gas_limit
        )
    else:
        output = PvmAccumulateOutput(
            state_context=marshalling_output.context.context.state_context,
            deferred_transfers=marshalling_output.context.context.deferred_transfers,
            accumulation_output=marshalling_output.context.context.invocation_output,
            gas_limit=marshalling_output.gas_limit
        )
    if output.accumulation_output is not None:
        # TODO remove
        logging.error(f'accumulation_output=0x{output.accumulation_output.hex()}')
    return output

