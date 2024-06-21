from scalecodec.base import ScaleType
from scalecodec.types import Struct
from models.block.block import Block
from models.state.state_authorizer_pool import StateAuthorizerPool
from models.state.state_recent_blocks import StateRecentBlocks
from models.state.state_safrole import StateSafrole
from models.state.state_services import StateServices
from models.state.state_entropy import StateEntropy
from models.state.state_validator_queue import StateValidatorQueue
from models.state.state_validator_pool import StateValidatorPool
from models.state.state_validator_archive import StateValidatorArchive
from models.state.state_assurances import StateAssurances
from models.state.state_timeslot import StateTimeslot
from models.state.state_authorizer_queue import StateAuthorizerQueue
from models.state.state_privileged_services import StatePrivilegedServices
from models.state.state_disputes import StateDisputes


class StateObject(ScaleType):
    #GP-equation: 12
    #[TODO: input 1: Current state]
    #[TODO: input 2: Block]
    def state_transition(self, block: Block):
        #[TODO: state transition dependency | sequence of isolated state transitions]

        #[TODO: output 1: transitioned state]
        pass
    def test(self):
        print('ja')


class State(Struct):
    #TODO: SILOING ALL INTERACTION WITH STATE PER State subclass, e.g. StateTimeslot (state_timeslot.py)
    #GP-reference: SIGMA | SCALETYPE-DEFINITION: "STATE"->"(AUTHORIZER_POOL,RECENT_BLOCKS,SAFROLE,SERVICES,ENTROPY,VALIDATOR_QUEUE,VALIDATOR_POOL,VALIDATOR_ARCHIVE,ASSURANCES,TIMESLOT,AUTHORIZER_QUEUE,PRIVILIGED_SERVICES,DISPUTES)" | "AUTHORIZER_POOL" refer to class StateAuthorizerPool for details. | "RECENT_BLOCKS" refer to class StateRecentBlocks for details. | "SAFROLE" refer to class StateSafrole for details. | "SERVICES" refer to class StateServices for details. | "ENTROPY" refer to class StateEntropy for details. | "VALIDATOR_QUEUE" refer to class StateValidatorQueue for details. | "VALIDATOR_POOL" refer to class StateValidatorPool for details. | "VALIDATOR_ARCHIVE" refer to class StateValidatorArchive for details. | "ASSURANCES" refer to class StateAssurances for details. | "TIMESLOT" refer to class StateTimeslot for details. | "AUTHORIZER_QUEUE" refer to class StateAuthorizerQueue for details. | "PRIVILEGED_SERVICES" refer to class StatePrivilegedServices for details. | "DISPUTES" refer to class StateDisputes for details.
    #GP-equation: 15
    scale_type_cls = StateObject
    arguments = {
        'authorizer_pool': StateAuthorizerPool(),
        'recent_blocks': StateRecentBlocks(),
        'safrole': StateSafrole(),
        'services': StateServices(),
        'entropy': StateEntropy(),
        'validator_queue': StateValidatorQueue(),
        'validator_pool': StateValidatorPool(),
        'validator_archive': StateValidatorArchive(),
        'assurances': StateAssurances(),
        'timeslot': StateTimeslot(),
        'authorizer_queue': StateAuthorizerQueue(),
        'privileged_services': StatePrivilegedServices(),
        'disputes': StateDisputes()
    }

