import os

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.1'
APP_VERSION = '0.1.32'

FUZZER_VERSION = 1
FUZZER_FEATURE_FORK = True
FUZZER_FEATURE_ANCESTRY = False

DEBUG = False
PROFILING = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
SKIP_TIMESLOT_WALL_CLOCK_CHECK = False

DEBUG_PROGRAM_OVERRIDE = {}

USE_THREAD_POOL_SAFROLE = True
USE_THREAD_POOL_ACCUMULATE = False
THREAD_POOL_MAX_WORKERS = os.cpu_count()

PVM_DEBUGGER = None         # Class handling all PVM (& hostcall) related logging
PVM_DEBUG = False
PVM_DEBUG_OPCODES = False
PVM_DEBUG_MEMORY = False

PVM_MIN_HEAP_SIZE = 0
PVM_MAX_HEAP_SIZE = 1_000_000*1000    #TODO: find out what it should be...

# Options: GRAYPAPER, CPYTHON, NUMBA_JIT, NUMBA_AOT
PVM_INTERPRETER = os.getenv("PVM_INTERPRETER", "NUMBA_AOT")

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
