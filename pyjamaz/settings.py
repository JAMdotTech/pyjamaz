TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.8'

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
SKIP_TIMESLOT_WALL_CLOCK_CHECK = False

DEBUG_PROGRAM_OVERRIDE = {}


PVM_DEBUGGER = None
#PVM_INTERPRETER = "PVM_GP"
PVM_INTERPRETER = "PVM_CPYTHON"
PVM_MIN_HEAP_SIZE = 0
PVM_MAX_HEAP_SIZE = 1_000_000*1000    #TODO: find out what it should be...


try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
