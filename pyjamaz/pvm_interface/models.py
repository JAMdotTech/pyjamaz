from dataclasses import dataclass
from typing import List, Optional

from pyjamaz.models.state import AccumulationStateComponents, DeferredTransfer


@dataclass
class PvmAccumulateOutput:
    state_context: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_output: Optional[bytes]
    gas_used: int
