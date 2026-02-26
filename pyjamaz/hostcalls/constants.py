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
    fetch             = 1  #ΩY
    lookup            = 2  #ΩL
    read              = 3  #ΩR
    write             = 4  #ΩW
    info              = 5  #ΩI


#GP-0.7.2-section:B.7
class HostCallAccumulate(Enum):
    bless                  = 14  #ΩB
    assign                 = 15  #ΩA
    designate              = 16  #ΩD
    checkpoint             = 17  #ΩC
    new                    = 18  #ΩN
    upgrade                = 19  #ΩU
    transfer               = 20  #ΩT
    eject                  = 21  #ΩJ
    query                  = 22  #ΩQ
    solicit                = 23  #ΩS
    forget                 = 24  #ΩF
    _yield                 = 25  #Ω♉︎
    provide                = 26  #Ω♈︎


#GP-0.7.2-section:B.6
class HostCallRefine(Enum):
    historical_lookup      = 6  #ΩH
    export                 = 7  #ΩE
    machine                = 8  #ΩM
    peek                   = 9  #ΩP
    poke                   = 10  #ΩO
    pages                  = 11  #ΩZ
    invoke                 = 12  #ΩK
    expunge                = 13  #ΩX
