from dataclasses import dataclass
from typing import List

from pyjamaz.models.state import AccumulateInvocationContext
from pyjamaz.pvm.types import PVMMemory


@dataclass
class InvocationInput:
    """
    TODO
    """
    service_id: int
    invocation_context: AccumulateInvocationContext
    gas_before: int
    gas_limit: int
    registers: List[int]
    memory: PVMMemory
