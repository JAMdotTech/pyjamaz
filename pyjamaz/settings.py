TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.7'

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

DEBUG_PROGRAM_OVERRIDE = {}


PVM_DEBUGGER = None
PVM_MIN_HEAP_SIZE = 1_000_000
PVM_MAX_HEAP_SIZE = 1_000_000*10    #TODO: find out what it should be...


try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
