from dataclasses import dataclass
from typing import Union, List

from pyjamaz.pvm.constants import ExitCondition, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.types import PVMProgram, PVMMemory

class InvocationContext:
    """
    GP-0.6.2-eq:B.6 (X) | Invocation Result Context (abstract)
    """


@dataclass
class InvocationMutationOutput:
    """
    A.34
    """
    output: ExitCondition
    gas_limit: int
    registers: List[int]
    memory: PVMMemory
    context: InvocationContext


class InvocationMutator:
    """
    GP-x.x.x-eq:A.34 (Ω⟨X⟩) Abstract class for mutator functions
    """
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: InvocationContext
    ) -> InvocationMutationOutput:
        pass

@dataclass
class PVMOutput:
    exit_condition: ExitCondition   # ε′
    instruction_counter: int        # ı′
    gas_limit: int                  # ρ′
    registers: List[int]            # ω′
    memory: PVMMemory               # μ′

def pvm_general_invoke(
        serialized_pvm_code: bytes,  # c TODO should be PMVCode?
        instruction_counter: int,  # ı
        gas_limit: int,  # ρ
        registers: List[int],  # ω
        memory: PVMMemory,  # μ
) -> PVMOutput:
    """
    A.1 Ψ

    TODO Stub
    """

    return PVMOutput(
        exit_condition=ExitCondition.panic.value,
        instruction_counter=instruction_counter,
        gas_limit=gas_limit,
        registers=registers,
        memory=memory
    )


@dataclass
class PvmMarshallingOutput:
    gas_used: int
    output: ExitCondition
    context: InvocationContext

@dataclass
class PvMHostCallOutput:
    exit_condition: ExitCondition          # ε′
    instruction_counter: int               # ı′
    gas_limit: int                         # ρ′
    registers: List[int]                   # ω′
    memory: PVMMemory                      # μ′
    invocation_context: InvocationContext  # x

def pvm_invoke_host_call(
        serialized_pvm_code: bytes,            # c TODO should be PMVCode?
        instruction_counter: int,              # ı
        gas_limit: int,                        # ρ
        registers: List[int],                  # ω
        memory: PVMMemory,                     # μ
        invocation_mutator: InvocationMutator, # f
        invocation_context: InvocationContext  # x
) -> PvMHostCallOutput:
    """
    A.33 Ψ_H
    """

    # invoke general PVM function (Ψ)
    output = pvm_general_invoke(
        serialized_pvm_code,
        instruction_counter,
        gas_limit,
        registers,
        memory
    )

    if output.exit_condition in [
        ExitCondition.halt, ExitCondition.panic, ExitCondition.out_of_gas, ExitCondition.page_fault
    ]:
        return PvMHostCallOutput(
            exit_condition=output.exit_condition,
            instruction_counter=output.instruction_counter,
            gas_limit=output.gas_limit,
            registers=output.registers,
            memory=output.memory,
            invocation_context=invocation_context
        )
    if output.exit_condition == ExitCondition.host_halt:
        host_call_output = invocation_mutator.execute(
            host_call_instr_nr=output.exit_condition.host_halt_instruction,
            gas_limit=output.gas_limit,
            registers=output.registers,
            memory=output.memory,
            invocation_context=invocation_context
        )
        if host_call_output.output == ExitCondition.page_fault:
            return PvMHostCallOutput(
                exit_condition=host_call_output.output,
                instruction_counter=output.instruction_counter,
                gas_limit=output.gas_limit,
                registers=output.registers,
                memory=output.memory,
                invocation_context=invocation_context
            )
        elif host_call_output.output == ExitCondition.none:
            # TODO continue PVM
            return pvm_invoke_host_call(
                serialized_pvm_code=serialized_pvm_code,
                instruction_counter=output.instruction_counter + 1 + skip(output.instruction_counter), # TODO
                gas_limit=host_call_output.gas_limit,
                registers=host_call_output.registers,
                memory=host_call_output.memory,
                invocation_mutator=invocation_mutator,
                invocation_context=invocation_context
            )

        elif host_call_output.output in [
            ExitCondition.halt, ExitCondition.panic, ExitCondition.out_of_gas
        ]:
            return PvMHostCallOutput(
                exit_condition=host_call_output.output,
                instruction_counter=output.instruction_counter,
                gas_limit=host_call_output.gas_limit,
                registers=host_call_output.registers,
                memory=host_call_output.memory,
                invocation_context=host_call_output.context
            )

    raise NotImplementedError

def pvm_invoke_marshalling(
        serialized_program: bytes,              # p
        start_offset: int,                      # ı
        gas_limit: int,                         # ρ
        argument_data: bytes,                   # a
        invocation_mutator: InvocationMutator,  # f
        invocation_context: InvocationContext   # x
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
            context=invocation_context
        )
    else:
        output = pvm_invoke_host_call(
            serialized_pvm_code=pvm_program.code,
            instruction_counter=start_offset,
            gas_limit=gas_limit,
            registers=pvm_program.registers,
            memory=pvm_program.memory,
            invocation_mutator=invocation_mutator,
            invocation_context=invocation_context
        )
        # GP-0.6.2-eq:A.43
        if output.exit_condition == ExitCondition.out_of_gas:
            output = ExitCondition.out_of_gas
        elif output.exit_condition == ExitCondition.halt:
            output = ExitCondition.halt
            output.halt_output = bytes(32) # TODO implement
        else:
            output = ExitCondition.panic

        return PvmMarshallingOutput(
            gas_used=gas_limit,
            output=output,
            context=invocation_context
        )
