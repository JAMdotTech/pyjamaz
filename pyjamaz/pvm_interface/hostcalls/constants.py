from enum import Enum

import numpy as np


#GP_B.1
class HostCallResult(Enum): #TODO: refactor naar capital
    none: np.uint32 = 2**64-1
    what: np.uint32 = 2**64-2
    oob: np.uint32  = 2**64-3
    who: np.uint32  = 2**64-4
    full: np.uint32 = 2**64-5
    core: np.uint32 = 2**64-6
    cash: np.uint32 = 2**64-7
    low: np.uint32  = 2**64-8
    high: np.uint32 = 2**64-9
    huh: np.uint32  = 2**64-10
    ok: np.uint32   = 0


#?????????
class HostCallResultInnerPVM(Enum):
    halt: np.uint32     = np.uint32(0)
    panic: np.uint32    = np.uint32(1)
    fault: np.uint32    = np.uint32(2)
    host: np.uint32     = np.uint32(3)
    oog: np.uint32      = np.uint32(4)


#GP_B.6
class HostCallGeneral(Enum):
    gas: np.uint8               = np.uint8(0)  #ΩG
    lookup: np.uint8            = np.uint8(1)  #ΩL
    read: np.uint8              = np.uint8(2)  #ΩR
    write: np.uint8             = np.uint8(3)  #ΩW
    info: np.uint8              = np.uint8(4)  #ΩI


# #GP_TODO: op volgorde GP
# class HostCallAccumulate(Enum):
#     assign_core: np.uint8               = np.uint8(0)  #ΩA
#     empower_service: np.uint8           = np.uint8(0)  #ΩB
#     checkpoint: np.uint8                = np.uint8(0)  #ΩC
#     designate_validators: np.uint8      = np.uint8(0)  #ΩD
#     export_segment: np.uint8            = np.uint8(0)  #ΩE
#     forget_preimage: np.uint8           = np.uint8(0)  #ΩF
#     gas_remaining: np.uint8             = np.uint8(0)  #ΩG
#     historical_lookup: np.uint8         = np.uint8(0)  #ΩH
#     information_on_service: np.uint8    = np.uint8(0)  #ΩI
#     kickoff_pvm: np.uint8               = np.uint8(0)  #ΩK
#     lookup_preimage: np.uint8           = np.uint8(0)  #ΩL
#     make_pvm: np.uint8                  = np.uint8(0)  #ΩM
#     new_service: np.uint8               = np.uint8(0)  #ΩN
#     poke_pvm: np.uint8                  = np.uint8(0)  #ΩO
#     peek_pvm: np.uint8                  = np.uint8(0)  #ΩP
#     quit_service: np.uint8              = np.uint8(0)  #ΩQ
#     solicit_preimage: np.uint8          = np.uint8(0)  #ΩS
#     read_storage: np.uint8              = np.uint8(0)  #ΩR
#     transfer: np.uint8                  = np.uint8(0)  #ΩT
#     upgrade_service: np.uint8           = np.uint8(0)  #ΩU
#     void_inner_pvm_memory: np.uint8     = np.uint8(0)  #ΩV
#     write_storage: np.uint8             = np.uint8(0)  #ΩW
#     expunge_pvm: np.uint8               = np.uint8(0)  #ΩX
#     import_segment: np.uint8            = np.uint8(0)  #ΩY
#     zero_inner_pvm_memory: np.uint8     = np.uint8(0)  #ΩZ
