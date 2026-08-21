import os

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.2'
APP_VERSION = '0.2.1'


def _apply_jam_fuzz_spec_override():
    global TEST_SUITE

    if os.getenv("JAM_FUZZ") is None:
        return

    jam_fuzz_spec = os.getenv("JAM_FUZZ_SPEC")
    if jam_fuzz_spec not in ("tiny", "full"):
        raise RuntimeError("JAM_FUZZ_SPEC must be set to 'tiny' or 'full' when JAM_FUZZ is set")
    TEST_SUITE = jam_fuzz_spec


_apply_jam_fuzz_spec_override()

FUZZER_VERSION = 1
FUZZER_FEATURE_FORK = True
FUZZER_FEATURE_ANCESTRY = False

DEBUG = False
PROFILING = False
SOLO_MODE = False
STORAGE_ENGINE = 'rocksdb' # memory | rocksdb | leveldb

# GP relaxation flags
SKIP_TIMESLOT_WALL_CLOCK_CHECK = False
SKIP_VALIDATE_GUARANTEES = False

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

RPC_SERVER_MAX_SIZE = 30 * 1024 * 1024
# validator overrides for JAMNP-S
# Keys are validator Ed25519 public key hex strings ( with or without 0x)
# Values can be either "host:port" or ("host", port), or None to ignore connections (for debugging purposes)
VALIDATOR_ENDPOINT_OVERRIDES = {}

GUARANTEE_SIGNATURE_WAIT_PERIOD = 2

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass

_apply_jam_fuzz_spec_override()
