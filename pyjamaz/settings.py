import logging

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.0'
APP_VERSION = '0.1.5'

DEBUG = False
SOLO_MODE = False

DEBUG_PROGRAM_OVERRIDE = {}

PVM_DEBUGGER = None

LOG_PACKAGE_OVERRIDES = {
    "quic": logging.WARNING,
    'numba': logging.WARNING,
    'numba.core': logging.WARNING,
}


try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
