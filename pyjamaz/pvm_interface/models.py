from dataclasses import dataclass
from typing import List, Optional

from pyjamaz.models.state import AccumulationStateComponents, DeferredTransfer
from pyjamaz.pvm.invocation import InvocationContext


@dataclass
class PvmAccumulateOutput:
    state_context: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_output: Optional[bytes]
    gas_used: int


class JamInvocationContext(InvocationContext):
    """
    GP-0.6.2-eq:B.6 (blackboard_X) | Invocation Result Context

    TODO check service_account_id in state_context.services
    """
    service_account_id: int # s
    state_context: AccumulationStateComponents # u
    new_service_account_id: int #i
    deferred_transfers: List[DeferredTransfer] # t
    invocation_output: Optional[bytes] # y



