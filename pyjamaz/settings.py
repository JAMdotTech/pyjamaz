import os

TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.7.2'
APP_VERSION = '0.1.49'


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


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    return max(minimum, parsed)


THREAD_POOL_MAX_WORKERS = os.cpu_count()
try:
    from pyjamaz.graypaper_constants import CORE_COUNT as _CORE_COUNT
except ImportError:
    _CORE_COUNT = os.cpu_count() or 1
REFINE_WORKERS = _env_int(
    "PYJAMAZ_REFINE_WORKERS",
    min(_CORE_COUNT, os.cpu_count() or 1, 4),
)
ACCUMULATE_WORKERS = _env_int(
    "PYJAMAZ_ACCUMULATE_WORKERS",
    os.cpu_count() or 1,
)
INNER_PVM_MEMORY = os.getenv("PYJAMAZ_INNER_PVM_MEMORY", "sparse").lower()
if INNER_PVM_MEMORY not in ("sparse", "mmap"):
    raise RuntimeError("PYJAMAZ_INNER_PVM_MEMORY must be 'sparse' or 'mmap'")

PVM_DEBUGGER = None         # Class handling all PVM (& hostcall) related logging
PVM_DEBUG = False
PVM_DEBUG_OPCODES = False
PVM_DEBUG_MEMORY = False

PVM_MIN_HEAP_SIZE = 0
PVM_MAX_HEAP_SIZE = 1_000_000*1000    #TODO: find out what it should be...

# Options: GRAYPAPER, CPYTHON, NUMBA_JIT, NUMBA_AOT
PVM_INTERPRETER = os.getenv("PVM_INTERPRETER", "NUMBA_JIT")

RPC_SERVER_MAX_SIZE = 30 * 1024 * 1024

GUARANTEE_SIGNATURE_WAIT_PERIOD = 2

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass

_apply_jam_fuzz_spec_override()
