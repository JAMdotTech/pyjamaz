import logging
import os
import time
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import numpy.typing as npt

from pyjamaz import settings
from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.types import PVMProgram
from pyjamaz.pvm.constants import PVM_INPUT_DATA_SIZE, ExitCondition, ExitReason
from pyjamaz.refine_profile import ENABLED as REFINE_PROFILE_ENABLED
from pyjamaz.refine_profile import hostcall as refine_profile_hostcall, timer as refine_profile_timer
from pyjamaz.settings import DEBUG


class PVMLogger(ABC):

    @abstractmethod
    def hc_regs(self, msg, phase):
        pass

    @abstractmethod
    def hc_log(self, msg, data):
        pass

    @abstractmethod
    def pvm_regs(self, msg) -> None:
        pass

    @abstractmethod
    def sbrk(self, cur_size, new_size, growth, alloc_mem):
        pass

    @abstractmethod
    def acl(self, cur_size, new_size, growth):
        pass

    @abstractmethod
    def exc(self, exc_str):
        pass

    @abstractmethod
    def hc_debug(self, log_lvl: int, log_lvl_name: str, core_idx: int, service_id: int, target_msg: str, message: str) -> None:
        pass

    @abstractmethod
    def pvm_hash(self):
        pass

    @abstractmethod
    def pvm_counters(self):
        pass

    @abstractmethod
    def pvm_header(self):
        pass


class InvocationContext:
    """
    GP-0.7.2-eq:A.35 (X)
    """
    pass


@dataclass
class InvocationMutationOutput:
    """
    GP-0.7.2-eq:A.35
    """
    exit_condition: ExitCondition
    gas_limit: int
    registers: npt.NDArray[np.uint64]
    memory: PVMMemory


class InvocationMutator:
    """
    GP-0.7.2-eq:A.36 (Ω⟨X⟩) Abstract class for mutator functions
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
    gas_used: int
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
        invocation_context: Optional[InvocationContext]  # x

    ):
        self.pvm_program: Optional[PVMProgram] = None
        self.pvm: Optional[PVMInterpreter] = None
        self.invocation_mutator = invocation_mutator
        self.invocation_context = invocation_context

    @staticmethod
    def _should_create_logger() -> bool:
        if settings.PVM_DEBUGGER is None:
            return False
        if os.getenv("PYJAMAZ_ENABLE_PVM_LOGGER", "").lower() in ("1", "true", "yes", "on"):
            return True
        return bool(settings.DEBUG or settings.PVM_DEBUG or settings.PVM_DEBUG_OPCODES or settings.PVM_DEBUG_MEMORY)

    def pvm_invoke_host_call(
            self,
            instruction_counter: int,              # ı
            gas_limit: int,                        # ρ
    ) -> PvMHostCallOutput:
        """
        GP-0.7.2-eq:A.35 (Ψ_H) | Hostcall definition
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
                    registers=self.pvm.get_registers(),
                    memory=self.pvm.mem,
                    invocation_context=self.invocation_context
                )

            if exit_condition.reason == ExitReason.host_halt:
                host_call_started_at = time.perf_counter() if REFINE_PROFILE_ENABLED else 0.0
                host_call_output = self.invocation_mutator.execute(
                    host_call_instr_nr=exit_condition.value,
                    gas_limit=int(self.pvm.gas),
                    registers=self.pvm.reg,
                    memory=self.pvm.mem,
                    invocation_context=self.invocation_context,
                    _pvm=self.pvm
                )
                if REFINE_PROFILE_ENABLED:
                    refine_profile_hostcall(exit_condition.value, time.perf_counter() - host_call_started_at)

                # Update gas usage
                gas_limit = host_call_output.gas_limit

                if host_call_output.exit_condition.reason == ExitReason.page_fault:
                    return PvMHostCallOutput(
                        exit_condition=host_call_output.exit_condition,
                        instruction_counter=int(self.pvm.pc),
                        gas_limit=int(self.pvm.gas),
                        registers=self.pvm.get_registers(),
                        memory=self.pvm.mem,
                        invocation_context=self.invocation_context
                    )
                elif host_call_output.exit_condition.reason == ExitReason.resume:
                    self.pvm.status = ExitReason.resume.value
                    self.pvm.next_instruction()
                    instruction_counter = self.pvm.pc
                    DEBUG and logging.debug(f'PVM continue @ {instruction_counter}')

                elif host_call_output.exit_condition.reason in [
                    ExitReason.halt, ExitReason.panic, ExitReason.out_of_gas
                ]:
                    return PvMHostCallOutput(
                        exit_condition=host_call_output.exit_condition,
                        instruction_counter=int(self.pvm.pc),
                        gas_limit=host_call_output.gas_limit,
                        registers=host_call_output.registers,
                        memory=host_call_output.memory,
                        invocation_context=self.invocation_context
                    )
                else:
                    raise Exception("OEPSIE!")


    def pvm_invoke_marshalling(
            self,
            serialized_program: bytes,              # p
            start_offset: int,                      # ı
            gas_limit: int,                         # ρ
            argument_data: bytes,                   # a
            program_name: Optional[str],
    ) -> PvmMarshallingOutput:
        """
        GP-0.7.2-eq:A.44 (Ψ_M) | Marshalling invocation function
        """

        with refine_profile_timer("pvm_setup"):
            self.pvm_program = PVMProgram.from_serialized_bytes(
                serialized_program=serialized_program,
                argument_contents=argument_data,
                name=program_name
            )

            if self.pvm_program is None:
                return PvmMarshallingOutput(
                    gas_used=0,
                    exit_condition=ExitCondition(reason=ExitReason.panic),
                    context=self.invocation_context
                )

            logger_cls = settings.PVM_DEBUGGER if self._should_create_logger() else None
            self.pvm: PVMInterpreter = PVMInterpreter(self.pvm_program, logger=logger_cls)

        with refine_profile_timer("pvm_execution"):
            output = self.pvm_invoke_host_call(
                instruction_counter=start_offset,
                gas_limit=gas_limit
            )

        # GP-0.7.2-eq:A.44
        if output.exit_condition.reason not in (ExitReason.halt, ExitReason.out_of_gas):
            output.exit_condition = ExitCondition(reason=ExitReason.panic)

        return PvmMarshallingOutput(
            gas_used=gas_limit - max(output.gas_limit, 0),
            exit_condition=output.exit_condition,
            context=output.invocation_context
        )
