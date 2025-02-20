from dataclasses import dataclass
from typing import List, Union

from pyjamaz.models.common import AccumulationOperand
from pyjamaz.models.state import AccumulationStateComponents
from pyjamaz.pvm_interface.models import PvmAccumulateOutput


def pvm_invoke_accumulate(
        state_context: AccumulationStateComponents,
        timeslot: int,
        service_id: int,
        gas_limit: int,
        operands: List[AccumulationOperand]
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

    return PvmAccumulateOutput(
        state_context=state_context,
        deferred_transfers=[],
        accumulation_output=None,
        gas_used=gas_limit
    )

