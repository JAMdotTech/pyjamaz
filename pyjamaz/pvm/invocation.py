from dataclasses import dataclass
from typing import Union, List

from pyjamaz.pvm.constants import ExitCondition, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.types import PVMProgram, PVMMemory


class InvocationContext:
    """
    GP-0.6.2-eq:B.6 (X) | Invocation Result Context (abstract)
    """
    pass

@dataclass
class PvmMarshallingOutput:
    gas_used: int
    output: Union[bytes, ExitCondition]
    context: InvocationContext

@dataclass
class PvMHostCallOutput:
    exit_condition: ExitCondition          # ε′
    instruction_counter: int               # ı′
    gas_used: int                          # ρ′
    registers: List[int]                   # ω′
    memory: bytes                          # μ′
    invocation_context: InvocationContext  # x

def pvm_invoke_host_call(
        serialized_pvm_code: bytes, # c
        instruction_counter: int,   # ı
        gas_limit: int,             # ρ
        registers: List[int],       # ω
        memory: PVMMemory,          # μ
        host_call_def: callable,    # f
        invocation_context: InvocationContext # x
) -> PvMHostCallOutput:

    # invoke PVM single step

    return PvMHostCallOutput(

    )

def pvm_invoke_marshalling(
        serialized_program: bytes,              # p
        start_offset: int,                      # ı
        gas_limit: int, # TODO or gas_used?     # ρ
        argument_data: bytes,                   # a
        context: InvocationContext,             # f
        savepoint_context: InvocationContext    # x
) -> PvmMarshallingOutput:
    """
    GP-0.6.2-eq:A.42 (Ψ_M) | Marshalling invocation function
    """

    if len(argument_data) > PVM_INPUT_DATA_SIZE:
        raise ValueError(f'argument_data too long (> {PVM_INPUT_DATA_SIZE} bytes)')

    pvm_program = PVMProgram.from_serialized_bytes(
        serialized_program=serialized_program,
        arguments=argument_data
    )

    if pvm_program is None:
        return PvmMarshallingOutput(
            gas_used=gas_limit,
            output=ExitCondition.panic,
            context=context
        )
    else:
        output = pvm_invoke_host_call(
            serialized_pvm_code=pvm_program.code,
            instruction_counter=start_offset,
            gas_limit=gas_limit,
            registers=pvm_program.registers,
            memory=pvm_program.memory,
            host_call_def=lambda x: x,
            invocation_context=context
        )
        # GP-0.6.2-eq:A.43
        if output.exit_condition == ExitCondition.out_of_gas:
            output = ExitCondition.out_of_gas
        elif output.exit_condition == ExitCondition.halt:
            output = bytes(32) # TODO implement
        else:
            output = ExitCondition.panic

        return PvmMarshallingOutput(
            gas_used=gas_limit,
            output=output,
            context=context
        )
