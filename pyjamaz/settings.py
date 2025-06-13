TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.6.5'

DEBUG = False
SOLO_MODE = False

DEBUG_PROGRAM_OVERRIDE = {
    b'fib': {
        'file': '/Users/arjan/Development/duna-polkavm/services/fib/fib.pvm',
        'heap_mem_pages': 2
    },
    b'tribonacci': {
        'file': '/Users/arjan/Development/duna-polkavm/services/tribonacci/tribonacci.pvm',
        'heap_mem_pages': 2
    },
    b'corevm': {
        'file': '/Users/arjan/Development/duna-polkavm/services/corevm/corevm.pvm',
        'heap_mem_pages': 2
    },
    b'\x00\x15jam-bootstrap-service\x060.1.22\nApache-2.0\x01%Parity Technologies <admin@parity.io>': {
        'file': '/Users/arjan/Development/jam-services/jam-bootstrap-service.jam',
        'heap_mem_pages': 2
    }
}

try:
    from pyjamaz.local_settings import *
except ImportError:
    pass
