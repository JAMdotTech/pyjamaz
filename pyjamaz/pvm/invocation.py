from dataclasses import dataclass
from typing import List

from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import PVM_INPUT_DATA_SIZE, ExitCondition, ExitReason
from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm.types import PVMProgram, PVMMemory, PVMCode


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
        pvm_code: PVMCode,  # c
        instruction_counter: int,  # ı
        gas_limit: int,  # ρ
        registers: List[int],  # ω
        memory: PVMMemory,  # μ
) -> PVMOutput:
    """
    A.1 Ψ

    """
    logger = PVMDebugLog(None)
    pvm_program = PVMProgram(pvm_code, registers, memory)
    pvm = PVMInterpreter(pvm_program, logger)
    pvm.invoke(
        instruction_counter,
        gas_limit
    )

    return PVMOutput(
        exit_condition=pvm.get_exit_condition(),
        instruction_counter=pvm.pc,
        gas_limit=gas_limit,
        registers=pvm.reg,
        memory=pvm.mem
    )


@dataclass
class PvmMarshallingOutput:
    gas_limit: int
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
        pvm_code: PVMCode,                     # c
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
        pvm_code,
        instruction_counter,
        gas_limit,
        registers,
        memory
    )

    if output.exit_condition.reason in [
        ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas, ExitReason.page_fault
    ]:
        return PvMHostCallOutput(
            exit_condition=output.exit_condition,
            instruction_counter=output.instruction_counter,
            gas_limit=output.gas_limit,
            registers=output.registers,
            memory=output.memory,
            invocation_context=invocation_context
        )

    if output.exit_condition.reason == ExitReason.host_halt:
        host_call_output = invocation_mutator.execute(
            host_call_instr_nr=output.exit_condition.value,
            gas_limit=output.gas_limit,
            registers=output.registers,
            memory=output.memory,
            invocation_context=invocation_context
        )

        if host_call_output.output.reason == ExitReason.page_fault:
            return PvMHostCallOutput(
                exit_condition=host_call_output.output,
                instruction_counter=output.instruction_counter,
                gas_limit=output.gas_limit,
                registers=output.registers,
                memory=output.memory,
                invocation_context=invocation_context
            )
        elif host_call_output.output.reason == ExitReason.none:
            # TODO continue PVM!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # return pvm_invoke_host_call(
            #     pvm_code=pvm_code,
            #     instruction_counter=output.instruction_counter + 1 + skip(output.instruction_counter), # TODO
            #     gas_limit=host_call_output.gas_limit,
            #     registers=host_call_output.registers,
            #     memory=host_call_output.memory,
            #     invocation_mutator=invocation_mutator,
            #     invocation_context=invocation_context
            # )
            raise Exception("TODO")

        elif host_call_output.output.reason in [
            ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas
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
            gas_limit=gas_limit,
            output=ExitCondition(reason=ExitReason.panic, value=None),
            context=invocation_context
        )
    else:
        output = pvm_invoke_host_call(
            pvm_code=pvm_program.code,
            instruction_counter=start_offset,
            gas_limit=gas_limit,
            registers=pvm_program.registers,
            memory=pvm_program.memory,
            invocation_mutator=invocation_mutator,
            invocation_context=invocation_context
        )
        # GP-0.6.2-eq:A.43
        if output.exit_condition.reason not in (ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas):
            raise Exception("TODO")

        return PvmMarshallingOutput(
            gas_limit=gas_limit,
            output=output.exit_condition,   #TODO: rename output to exit_condition
            context=invocation_context
        )
