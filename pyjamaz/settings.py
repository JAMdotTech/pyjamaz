TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.6.5'
APP_VERSION = '0.1.0'

DEBUG = False
SOLO_MODE = False

DEBUG_PROGRAM_OVERRIDE = {}

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
