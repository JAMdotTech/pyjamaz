from enum import Enum


#GP-0.6.4:B.1
class HostCallResult(Enum):
    NONE: int = 2 ** 64 - 1
    WHAT: int = 2 ** 64 - 2
    OOB: int  = 2 ** 64 - 3
    WHO: int  = 2 ** 64 - 4
    FULL: int = 2 ** 64 - 5
    CORE: int = 2 ** 64 - 6
    CASH: int = 2 ** 64 - 7
    LOW: int  = 2 ** 64 - 8
    HUH: int  = 2 ** 64 - 9
    OK: int   = 0

#GP-0.6.4:B.1
class InnerPVMResult(Enum):
    HALT = 0
    PANIC = 1
    FAULT = 2
    HOST = 3
    OOG = 4

class HostCallDebug(Enum):
    log:int              = 100


#GP-0.6.4:B.6
class HostCallGeneral(Enum):
    gas: int               = 0  #ΩG
    lookup: int            = 1  #ΩL
    read: int              = 2  #ΩR
    write: int             = 3  #ΩW
    info: int              = 4  #ΩI


#GP-0.6.4:B.7
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


#GP-0.6.4:B.7
class HostCallRefine(Enum):
    historical_lookup: int      = 17 #ΩH
    fetch: int                  = 18 #ΩY
    export: int                 = 19 #ΩE
    machine: int                = 20 #ΩM
    peek: int                   = 21 #ΩP
    poke: int                   = 22 #ΩO
    zero: int                   = 23 #ΩZ
    void: int                   = 24 #ΩV
    invoke: int                 = 25 #ΩK
    expunge: int                = 26 #ΩX
