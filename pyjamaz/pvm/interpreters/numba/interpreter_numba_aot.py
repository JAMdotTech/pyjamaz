"""
Ahead of Time compiled version of the JIT interpreter
"""

from numba.typed import Dict, List

from .interpreter_numba_aot_ffi import invoke_native
from .interpreter_numba_jit import PVMInterpreter as PVMInterpreterBase
from . import interpreter_numba_jit as _jit_mod

# TODO: might need a patch: https://numba.discourse.group/t/containerized-application-without-recompilation-at-startup/1637
class PVMInterpreter(PVMInterpreterBase):
    """
    AOT-backed PVM interpreter.
    """

    def __init__(self, program: "PVMProgram", logger=None):
        _jit_mod.invoke_native_jit = invoke_native
        super().__init__(program, logger=logger)
