from enum import Enum


#GP-0.6.2:B.1
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
