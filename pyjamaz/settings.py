TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.6'

DEBUG = False
SOLO_MODE = False

DEBUG_PROGRAM_OVERRIDE = {}

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
