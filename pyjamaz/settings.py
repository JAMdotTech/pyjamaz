TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.8'

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

DEBUG_PROGRAM_OVERRIDE = {}

USE_THREAD_POOL = False
THREAD_POOL_MAX_WORKERS = None # None=use default of min(32, (os.process_cpu_count() or 1) + 4)

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
