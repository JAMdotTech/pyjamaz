import os

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.21'

FUZZER_VERSION = 1
FUZZER_FEATURE_FORK = True
FUZZER_FEATURE_ANCESTRY = False

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
SKIP_TIMESLOT_WALL_CLOCK_CHECK = False

DEBUG_PROGRAM_OVERRIDE = {}

USE_THREAD_POOL = True
THREAD_POOL_MAX_WORKERS = os.cpu_count()

PVM_DEBUGGER = None

PVM_MIN_HEAP_SIZE = 0
PVM_MAX_HEAP_SIZE = 1_000_000*1000    #TODO: find out what it should be...

# Options: GRAYPAPER, CPYTHON, NUMBA_JIT, NUMBA_AOT
PVM_INTERPRETER = os.getenv("PVM_INTERPRETER", "NUMBA_AOT")

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
