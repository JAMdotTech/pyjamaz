TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.6.5'

DEBUG = True
SOLO_MODE = True

DEBUG_PROGRAM_OVERRIDE = {
    b'\x00\x15jam-bootstrap-service\x060.1.22\nApache-2.0\x01%Parity Technologies <admin@parity.io>': {
        'file': '/Users/matthijsblaas/dev/jam-services/jam-bootstrap-service.jam',
        'heap_mem_pages': 2
    },
    b'fib': {
        'file': './data/services/fib/fib.pvm',
        'heap_mem_pages': 2
    },
    b'tribonacci': {
        'file': './data/services/tribonacci/tribonacci.pvm',
        'heap_mem_pages': 2
    }
}
