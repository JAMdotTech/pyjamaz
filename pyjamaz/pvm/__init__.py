from pyjamaz import settings

if settings.PVM_INTERPRETER == "GRAYPAPER":
    from .interpreters.graypaper.defs import *
    from .interpreters.graypaper.memory_section import *
    from .interpreters.graypaper.interpreter_gp import *
elif settings.PVM_INTERPRETER == "CPYTHON":
    from .interpreters.cpython.defs import *
    from .interpreters.cpython.memory_section import *
    from .interpreters.cpython.interpreter_cpython import *
elif settings.PVM_INTERPRETER == "NUMBA_JIT":
    from .interpreters.numba.defs import *
    from .interpreters.numba.memory_section import *
    from .interpreters.numba.interpreter_numba_jit import PVMInterpreter
elif settings.PVM_INTERPRETER == "NUMBA_AOT":
    from .interpreters.numba.defs import *
    from .interpreters.numba.memory_section import *
    from .interpreters.numba.interpreter_numba_aot import PVMInterpreter
