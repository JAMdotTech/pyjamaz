from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

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
    registers: npt.NDArray[np.uint64]
    memory: PVMMemory
