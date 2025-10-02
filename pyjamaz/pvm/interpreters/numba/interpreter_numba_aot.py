# Minimal AOT wrapper that pre compiled interpreter_numba_jit

import pyjamaz.pvm.interpreters.numba.interpreter_numba_jit as m

from .interpreter_numba_aot_ffi import invoke_native

m.invoke_native = invoke_native

PVMInterpreter = m.PVMInterpreter
