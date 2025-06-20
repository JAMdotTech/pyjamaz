from enum import Enum


#GP-0.6.4:B.1
class HostCallResult(Enum):
    NONE = 2 ** 64 - 1
    WHAT = 2 ** 64 - 2
    OOB = 2 ** 64 - 3
    WHO = 2 ** 64 - 4
    FULL = 2 ** 64 - 5
    CORE = 2 ** 64 - 6
    CASH = 2 ** 64 - 7
    LOW = 2 ** 64 - 8
    HUH = 2 ** 64 - 9
    OK  = 0

#GP-0.6.4:B.1
class InnerPVMResult(Enum):
    HALT = 0
    PANIC = 1
    FAULT = 2
    HOST = 3
    OOG = 4

class HostCallDebug(Enum):
    log            = 100


#GP-0.6.4:B.6
class HostCallGeneral(Enum):
    gas               = 0  #ΩG
    lookup            = 1  #ΩL
    read              = 2  #ΩR
    write             = 3  #ΩW
    info              = 4  #ΩI
    fetch             = 18 #ΩY


#GP-0.6.4:B.7
class HostCallAccumulate(Enum):
    bless                  = 5  #ΩB
    assign                 = 6  #ΩA
    designate              = 7  #ΩD
    checkpoint             = 8  #ΩC
    new                    = 9  #ΩN
    upgrade                = 10 #ΩU
    transfer               = 11 #ΩT
    eject                  = 12 #ΩJ
    query                  = 13 #ΩQ
    solicit                = 14 #ΩS
    forget                 = 15 #ΩF
    _yield                 = 16 #Ω♉︎
    provide                = 27 #Ω♈︎


#GP-0.6.4:B.7
class HostCallRefine(Enum):
    historical_lookup      = 17 #ΩH
    fetch                  = 18 #ΩY
    export                 = 19 #ΩE
    machine                = 20 #ΩM
    peek                   = 21 #ΩP
    poke                   = 22 #ΩO
    zero                   = 23 #ΩZ
    void                   = 24 #ΩV
    invoke                 = 25 #ΩK
    expunge                = 26 #ΩX
