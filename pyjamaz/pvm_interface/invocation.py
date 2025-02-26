from dataclasses import dataclass
from typing import List, Union

from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents, PvmAccumulateOutput, EntropyState, JamInvocationContext
from pyjamaz.pvm.invocation import InvocationMutator, InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemory


class JamInvocationMutator(InvocationMutator):
    def execute(
            self,
            host_call_instr_nr: int,
            gas_limit: int,
            registers: List[int],
            memory: PVMMemory,
            invocation_context: JamInvocationContext,
            savepoint_context: JamInvocationContext
    ) -> InvocationMutationOutput:
        """
        B.10
        TODO seperate execute and execute_accumulate
        """


def pvm_invoke_accumulate(
        state_context: AccumulationStateComponents,
        timeslot: int,
        service_id: int,
        gas_limit: int,
        operands: List[AccumulationOperand],
        post_entropy: EntropyState
) -> PvmAccumulateOutput:
    """
    GP-0.6.1-eq:B.8 (Ψ_A) | Accumulation invocation function

    TODO stub

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

    invocation_context = state_context.to_invocation_context(
        service_account_id=service_id,
        entropy=post_entropy.entropy[0],
        timeslot=timeslot
    )

    return PvmAccumulateOutput(
        state_context=state_context,
        deferred_transfers=[],
        accumulation_output=None,
        gas_used=gas_limit
    )

