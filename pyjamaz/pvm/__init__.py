# from pyjamaz import settings
#
# if settings.PVM_INTERPRETER == "PVM_GP":
#     from .interpreter_gp import PVMInterpreter
# else:
#     from .interpreter_cpython import PVMInterpreter

#from .interpreter_rpython import PVMInterpreter
from .interpreter_numba import PVMInterpreter