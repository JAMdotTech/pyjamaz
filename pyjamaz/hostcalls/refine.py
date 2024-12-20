from typing import Dict

import numpy as np

from pyjamaz.hashing import blake2b_256_hash

from .constants import HostCallGeneral as op, HostCallResult
from .exceptions import InvalidHostCall
from ..models.state import ServiceAccount
from ..pvm import PVM


# GP_B.3 Refine Invocations ΨR
class RefineInvocationsMixin:

    # GP_B.3 The Export host-call
    def export(self, pvm:PVM, bold_s:ServiceAccount=None, s:int=None, d:Dict[int, ServiceAccount]=None):
        """
        """
