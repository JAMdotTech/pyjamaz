from scalecodec.base import ScaleType
from scalecodec.types import Struct, U32

from models.block import Header


class TimeslotObject(ScaleType):
    #GP-ref:16,44
    def state_transition(self, header: Header):
        # TODO: input 1: self (strictly not needed according to GP-ref:16)
        # TODO: input 2: Header
        # TODO: output 1: transitioned state
        # self += 1
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x11|11) # GP-ref: 281,(C11)
        # TODO: value: [define how to serialize] # GP-ref:281,(C11)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x0B | 11), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x0B | 11))
        pass


class Timeslot(Struct):
    # GP-ref:44
    scale_type_cls = TimeslotObject
    arguments = {
        'timeslot': U32 # GP-ref:44
    }
