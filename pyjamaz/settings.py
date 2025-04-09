TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.6.2'

DEBUG = False

DEBUG_PROGRAM_OVERRIDE = {
    b'fib': {
        'file': './data/services/fib/fib.pvm',
        'heap_mem_pages': 2
    },
    b'tribonacci': {
        'file': './data/services/tribonacci/tribonacci.pvm',
        'heap_mem_pages': 2
    }
}
