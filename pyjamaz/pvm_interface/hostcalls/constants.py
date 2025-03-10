from enum import Enum


#GP-0.6.2:B.1
class HostCallResult(Enum): #TODO: refactor naar capital
    none: int = 2**64-1
    what: int = 2**64-2
    oob: int  = 2**64-3
    who: int  = 2**64-4
    full: int = 2**64-5
    core: int = 2**64-6
    cash: int = 2**64-7
    low: int  = 2**64-8
    high: int = 2**64-9
    huh: int  = 2**64-10
    ok: int   = 0


#GP-0.6.2:B.6
class HostCallGeneral(Enum):
    gas: int               = 0  #ΩG
    lookup: int            = 1  #ΩL
    read: int              = 2  #ΩR
    write: int             = 3  #ΩW
    info: int              = 4  #ΩI


#GP-0.6.2:B.7
class HostCallAccumulate(Enum):
    bless: int                  = 5  #ΩB
    assign: int                 = 6  #ΩA
    designate: int              = 7  #ΩD
    checkpoint: int             = 8  #ΩC
    new: int                    = 9  #ΩN
    upgrade: int                = 10 #ΩU
    transfer: int               = 11 #ΩT
    eject: int                  = 12 #ΩJ
    query: int                  = 13 #ΩQ
    solicit: int                = 14 #ΩS
    forget: int                 = 15 #ΩF
    _yield: int                 = 16 #Ω?
