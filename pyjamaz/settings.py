TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.8'

DEBUG = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
TIMESLOT_WALL_CLOCK_CHECK = True

DEBUG_PROGRAM_OVERRIDE = {}

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
