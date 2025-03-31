import logging
from dataclasses import dataclass
from typing import List, Optional

from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import PVM_INPUT_DATA_SIZE, ExitCondition, ExitReason
from pyjamaz.pvm.duna_logger import PVMDunaLog
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
    exit_condition: ExitCondition   #TODO: rename
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
            invocation_context: InvocationContext,
            _pvm: PVMInterpreter #TODO: TMP!
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
    exit_condition: ExitCondition
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

    def pvm_invoke_host_call(
            self,
            instruction_counter: int,              # ı
            gas_limit: int,                        # ρ
    ) -> PvMHostCallOutput:
        """
        A.33 Ψ_H
        """

        while True:

            # invoke general PVM function (Ψ)
            self.pvm.invoke(
                instruction_counter,
                gas_limit
            )

            exit_condition = self.pvm.get_exit_condition()

            if exit_condition.reason in [
                ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas, ExitReason.page_fault
            ]:
                return PvMHostCallOutput(
                    exit_condition=exit_condition,
                    instruction_counter=int(self.pvm.pc),
                    gas_limit=int(self.pvm.gas),
                    registers=self.pvm.reg,
                    memory=self.pvm.mem,
                    invocation_context=self.invocation_context
                )

            if exit_condition.reason == ExitReason.host_halt:

                #TODO: refactor in seperate files? (general, accumulate, on_transfer & refine)
                host_call_output = self.invocation_mutator.execute(
                    host_call_instr_nr=exit_condition.value,
                    gas_limit=int(self.pvm.gas),
                    registers=self.pvm.reg,
                    memory=self.pvm.mem,
                    invocation_context=self.invocation_context,
                    _pvm=self.pvm   #TODO
                )
                #logging.debug("ECALLI COMPLETE")
                self.pvm.log()

                # Update gas usage TODO
                gas_limit = host_call_output.gas_limit

                if host_call_output.exit_condition.reason == ExitReason.page_fault:
                    return PvMHostCallOutput(
                        exit_condition=host_call_output.exit_condition,
                        instruction_counter=int(self.pvm.pc),
                        gas_limit=int(self.pvm.gas),
                        registers=self.pvm.reg,
                        memory=self.pvm.reg,
                        invocation_context=self.invocation_context
                    )
                elif host_call_output.exit_condition.reason == ExitReason.resume:
                    self.pvm.status = ExitReason.resume.value
                    self.pvm.next_instruction()
                    instruction_counter = self.pvm.pc
                    logging.debug(f'PVM continue @ {instruction_counter}')

                elif host_call_output.exit_condition.reason in [
                    ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas
                ]:
                    return PvMHostCallOutput(
                        exit_condition=host_call_output.exit_condition,
                        instruction_counter=int(self.pvm.pc),
                        gas_limit=host_call_output.gas_limit,
                        registers=host_call_output.registers,
                        memory=host_call_output.memory,
                        invocation_context=host_call_output.context
                    )
                else:
                    raise Exception("OEPSIE!")


    def pvm_invoke_marshalling(
            self,
            serialized_program: bytes,              # p
            start_offset: int,                      # ı
            gas_limit: int,                         # ρ
            argument_data: bytes                   # a
    ) -> PvmMarshallingOutput:
        """
        GP-0.6.2-eq:A.42 (Ψ_M) | Marshalling invocation function
        """

        if len(argument_data) > PVM_INPUT_DATA_SIZE:
            raise ValueError(f'argument_data too long (> {PVM_INPUT_DATA_SIZE} bytes)')

        self.pvm_program = PVMProgram.from_serialized_bytes(
            serialized_program=serialized_program,
            argument_contents=argument_data
        )

        if self.pvm_program is None:
            return PvmMarshallingOutput(
                gas_limit=gas_limit,
                exit_condition=ExitCondition(reason=ExitReason.panic),
                context=self.invocation_context
            )

        #logger = PVMDebugLog(pvm=None)
        logger = PVMDunaLog(pvm=None)
        self.pvm: PVMInterpreter = PVMInterpreter(self.pvm_program, logger)

        output = self.pvm_invoke_host_call(
            instruction_counter=start_offset,
            gas_limit=gas_limit
        )

        # GP-0.6.2-eq:A.43
        if output.exit_condition.reason not in (ExitReason.halt, ExitReason.out_of_gas):
            output.exit_condition = ExitCondition(reason=ExitReason.panic)

        return PvmMarshallingOutput(
            gas_limit=output.gas_limit,
            exit_condition=output.exit_condition,
            context=output.invocation_context
        )
