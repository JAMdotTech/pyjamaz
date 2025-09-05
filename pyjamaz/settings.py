import logging

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.5'

DEBUG = False
SOLO_MODE = False

DEBUG_PROGRAM_OVERRIDE = {}

PVM_DEBUGGER = None
#TODO: opesie loca_serttings???
PVM_MIN_HEAP_SIZE = 2_000_000
PVM_MAX_HEAP_SIZE = 1_000_000*10    #TODO: find out what it should be...
from pyjamaz.pvm.debug_logger import PVMDebugLog
PVM_DEBUGGER = None
#PVM_DEBUGGER = PVMDebugLog


LOG_PACKAGE_OVERRIDES = {
    "quic": logging.WARNING,
    'numba': logging.WARNING,
    'numba.core': logging.WARNING,
}


try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
