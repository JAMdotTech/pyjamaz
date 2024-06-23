from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec

from models.block import Header
from models.common import ValidatorKeys
from models.state.timeslot import Timeslot
from models.state.validator_pool import ValidatorPool


class ValidatorArchiveObject(ScaleType):
    # GP-ref:22,56
    def state_transition(self, header: Header, timeslot: Timeslot(), validator_pool: ValidatorPool()):
        # TODO: input 1: ValidatorArchive of current state (self)
        # TODO: input 2: Block.Header
        # TODO: input 3: Timeslot of current state
        # TODO: input 4: ValidatorPool of current state
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x09|9) # GP-ref: 281,(C9)
        # TODO: value: [define how to serialize] # GP-ref:281,(C9)
        pass

    def storage_persist(self):
        # TODO: persist
        pass

    def storage_get(self):
        # TODO: key:blake2b(0x09|9)
        pass


class ValidatorArchive(Struct):
    # GP-ref: LAMBDA,50
    scale_type_cls = ValidatorArchiveObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_archive': Vec(ValidatorKeys()) # GP-ref:50
    }
