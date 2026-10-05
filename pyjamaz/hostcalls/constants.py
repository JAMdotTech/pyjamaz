from enum import Enum


# GP-0.7.2-section:B.1
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

# GP-0.7.2-section:B.1
class InnerPVMResult(Enum):
    HALT = 0
    PANIC = 1
    FAULT = 2
    HOST = 3
    OOG = 4

class HostCallDebug(Enum):
    log            = 100


# GP-0.7.2-section:B.5
class HostCallGeneral(Enum):
    gas               = 0  #ΩG
    grow_heap         = 1  #ΩR
    fetch             = 2  #ΩY
    lookup            = 3  #ΩL
    read              = 4  #ΩR
    write             = 5  #ΩW
    info              = 6  #ΩI


#GP-0.7.2-section:B.7
class HostCallAccumulate(Enum):
    bless                  = 15  #ΩB
    assign                 = 16  #ΩA
    designate              = 17  #ΩD
    checkpoint             = 18  #ΩC
    new                    = 19  #ΩN
    upgrade                = 20  #ΩU
    transfer               = 21  #ΩT
    eject                  = 22  #ΩJ
    query                  = 23  #ΩQ
    solicit                = 24  #ΩS
    forget                 = 25  #ΩF
    _yield                 = 26  #Ω♉︎
    provide                = 27  #Ω♈︎


#GP-0.7.2-section:B.6
class HostCallRefine(Enum):
    historical_lookup      = 7  #ΩH
    export                 = 8  #ΩE
    machine                = 9  #ΩM
    peek                   = 10  #ΩP
    poke                   = 11  #ΩO
    pages                  = 12  #ΩZ
    invoke                 = 13  #ΩK
    expunge                = 14  #ΩX
