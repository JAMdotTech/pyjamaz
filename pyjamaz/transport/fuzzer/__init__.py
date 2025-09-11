from pyjamaz import settings


if settings.FUZZER_VERSION == 0:
    from pyjamaz.transport.fuzzer.v0.types import *
    from pyjamaz.transport.fuzzer.v0.target import *
    from pyjamaz.transport.fuzzer.v0.session import *
elif settings.FUZZER_VERSION == 1:
    from pyjamaz.transport.fuzzer.v1.types import *
    from pyjamaz.transport.fuzzer.v1.target import *
    from pyjamaz.transport.fuzzer.v1.session import *