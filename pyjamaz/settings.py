TEST_SUITE = 'tiny' # tiny or full
GP_VERSION = '0.6.2'

DEBUG = True

DEBUG_PROGRAM_OVERRIDE = {
    # b'fib': {
    #     'file': './data/services/fib/fib.pvm',
    #     'heap_mem_pages': 2
    # },
    b'tribonacci': {
        'file': "/Users/matthijsblaas/dev/polkavm/services/tribonacci/tribonacci.pvm",
        #'file': '/Users/matthijsblaas/dev/pyjamaz/pyjamaz/data/services/nok_tribonacci.pvm',
        #'file': '/Users/matthijsblaas/dev/pyjamaz/pyjamaz/data/services/ok_tribonacci.pvm',
        'heap_mem_pages': 2
    }
}
