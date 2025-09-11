import os

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.9'
FUZZER_VERSION = 1

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
SKIP_TIMESLOT_WALL_CLOCK_CHECK = False

DEBUG_PROGRAM_OVERRIDE = {}

USE_THREAD_POOL = True
THREAD_POOL_MAX_WORKERS = os.cpu_count()

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
