from scalecodec.base import ScaleType
from scalecodec.types import Struct, U32
from models.block import Block, Header
from models.old_state.state_assurances import StateAssurances
from models.old_state.state_authorizer_pool import StateAuthorizerPool
from models.old_state.state_authorizer_queue import StateAuthorizerQueue
from models.old_state.state_disputes import StateDisputes
from models.old_state.state_entropy import StateEntropy
from models.old_state.state_privileged_services import StatePrivilegedServices
from models.old_state.state_recent_blocks import StateRecentBlocks
from models.old_state.state_safrole import StateSafrole
from models.old_state.state_services import StateServices
from models.old_state.state_validator_archive import StateValidatorArchive
from models.old_state.state_validator_pool import StateValidatorPool
from models.old_state.state_validator_queue import StateValidatorQueue


class TimeslotObject(ScaleType):
    #GP-equation: 16,44
    def state_transition(self, header: Header):
        # TODO: input 1: Header
        # TODO: output 1: transitioned state
        # self += 1
        pass

    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-ref 280
        # TODO: serialize(self) | following specific definition GP-ref:281,(C11)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x0B | 11), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x0B | 11))
        pass


class Timeslot(Struct):
    # GP-ref:16,44
    scale_type_cls = TimeslotObject
    arguments = {
        'timeslot': U32 # GP-ref:??
    }


class StateObject(ScaleType):
    #GP-equation: 12
    #[TODO: input 1: Current old_state]
    #[TODO: input 2: Block]
    def state_transition(self, block: Block):
        #TODO: sequence of siloed old_state transitions based on dependencies
        #TODO: output 1: transitioned old_state
        pass


class State(Struct):
    # GP-ref:SIGMA,15
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
        'timeslot': Timeslot(),
        'authorizer_queue': StateAuthorizerQueue(),
        'privileged_services': StatePrivilegedServices(),
        'disputes': StateDisputes()
    }

