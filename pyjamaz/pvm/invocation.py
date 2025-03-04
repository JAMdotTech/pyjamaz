from dataclasses import dataclass
from typing import List, Optional

from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import PVM_INPUT_DATA_SIZE, ExitCondition, ExitReason
from pyjamaz.pvm.debug_logger import PVMDebugLog
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


class PVMInvocation:

    def __init__(
        self,
        invocation_mutator: InvocationMutator,  # f
        invocation_context: InvocationContext  # x

    ):
        self.pvm_program: Optional[PVMProgram] = None

        self.invocation_mutator: InvocationMutator = invocation_mutator
        self.invocation_context:InvocationContext = invocation_context

        self.pvm: Optional[PVMInterpreter] = None

    def pvm_general_invoke(
            self,
            instruction_counter: int,  # ı
            gas_limit: int  # ρ
    ) -> PVMOutput:
        """
        A.1 Ψ
        TODO kan weg
        """

        self.pvm.invoke(
            instruction_counter,
            gas_limit
        )

        return PVMOutput(
            exit_condition=self.pvm.get_exit_condition(),
            instruction_counter=self.pvm.pc,
            gas_limit=self.pvm.gas,
            registers=self.pvm.reg,
            memory=self.pvm.mem
        )

    def pvm_invoke_host_call(
            self,
            instruction_counter: int,              # ı
            gas_limit: int,                        # ρ
    ) -> PvMHostCallOutput:
        """
        A.33 Ψ_H
        """

        # invoke general PVM function (Ψ)
        self.pvm.invoke(
            instruction_counter,
            gas_limit
        )

        # TODO kan weg
        output = PVMOutput(
            exit_condition=self.pvm.get_exit_condition(),
            instruction_counter=self.pvm.pc,
            gas_limit=self.pvm.gas,
            registers=self.pvm.reg,
            memory=self.pvm.mem
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
                invocation_context=self.invocation_context
            )

        if output.exit_condition.reason == ExitReason.host_halt:
            host_call_output = self.invocation_mutator.execute(
                host_call_instr_nr=output.exit_condition.value,
                gas_limit=output.gas_limit,
                registers=output.registers,
                memory=output.memory,
                invocation_context=self.invocation_context
            )

            if host_call_output.output.reason == ExitReason.page_fault:
                return PvMHostCallOutput(
                    exit_condition=host_call_output.output,
                    instruction_counter=output.instruction_counter,
                    gas_limit=output.gas_limit,
                    registers=output.registers,
                    memory=output.memory,
                    invocation_context=self.invocation_context
                )
            elif host_call_output.output.reason == ExitReason.none:
                # TODO continue PVM!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                self.pvm.status = ExitReason.none.value
                self.pvm.next_instruction()
                return self.pvm_invoke_host_call(
                    # instruction_counter=output.instruction_counter + 1 + skip(output.instruction_counter), # TODO
                    instruction_counter=self.pvm.pc,
                    gas_limit=host_call_output.gas_limit
                )
                # raise Exception("TODO")

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
            self,
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

        self.pvm_program = PVMProgram.from_serialized_bytes(
            serialized_program=serialized_program,
            arguments=argument_data
        )

        if self.pvm_program is None:
            return PvmMarshallingOutput(
                gas_limit=gas_limit,
                output=ExitCondition(reason=ExitReason.panic, value=None),
                context=invocation_context
            )

        logger = PVMDebugLog(None)
        self.pvm: PVMInterpreter = PVMInterpreter(self.pvm_program, logger)

        output = self.pvm_invoke_host_call(
            instruction_counter=start_offset,
            gas_limit=gas_limit
        )
        # GP-0.6.2-eq:A.43
        if output.exit_condition.reason not in (ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas):
            raise Exception("TODO")

        return PvmMarshallingOutput(
            gas_limit=gas_limit,
            output=output.exit_condition,   #TODO: rename output to exit_condition
            context=invocation_context
        )
