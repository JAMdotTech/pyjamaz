# from pyjamaz import settings
#
#
# if settings.PVM_INTERPRETER == "CPYTHON":
#     from .cpython.defs import *
#     from .cpython.types import *
#     from .cpython.interpreter_cpython import *
# elif settings.PVM_INTERPRETER == "NUMBA":
#     from .numba.defs import *
#     from .numba.types import *
#     from .numba.types import *
#     from .numba.interpreter_numba import *
# elif settings.PVM_INTERPRETER == "PVM_GP":
#     from .gp import *
# else:
#     raise Exception(f"Unknown PVM interpreter: {settings.PVM_INTERPRETER}")


# from .cpython.defs import *
# from .cpython.types import *
# from .cpython.interpreter_cpython import *
#
# import os
# os.environ.pop("NUMBA_DISABLE_JIT", None)
#
# from numba import config
# config.DISABLE_JIT = False


from .numba.defs import *
from .numba.types import *
# from .numba.interpreter_numba import *
# from .numba.aot import *
from .numba.interpreter_numba_aot import *