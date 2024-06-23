from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec

from models.block import Header
from models.state.disputes import Disputes
from models.state.safrole import Safrole
from models.common import ValidatorKeys
from models.state.timeslot import Timeslot


class ValidatorPoolObject(ScaleType):
    # GP-ref:21,56
    def state_transition(self, header: Header, timeslot: Timeslot(), safrole: Safrole(), disputes: Disputes()):
        # TODO: input 1: ValidatorPool of current state
        # TODO: input 2: Block.Header
        # TODO: input 3: Timeslot of current state
        # TODO: input 4: StateSafrole of current state
        # TODO: input 5: StateDisputes of transitioned state
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x08|8) # GP-ref: 281,(C8)
        # TODO: value: [define how to serialize] # GP-ref:281,(C8)
        pass

    def storage_persist(self):
        # TODO: persist
        pass

    def storage_get(self):
        # TODO: key:blake2b(0x08|8)
        pass


class ValidatorPool(Struct):
    # GP-ref: KAPPA,50
    scale_type_cls = ValidatorPoolObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_pool': Vec(ValidatorKeys()) # GP-ref:50
    }
