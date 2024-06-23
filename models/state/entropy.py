from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256

from models.block import Header
from models.state.timeslot import Timeslot


class EntropyObject(ScaleType):
    # GP-ref:20,64,65
    def state_transition(self, header: Header, timeslot: Timeslot):
        # TODO: input 1: Entropy of current state (self)
        # TODO: input 2: Block.Header
        # TODO: input 3: Timeslot of current state
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x06|6) # GP-ref: 281,(C6)
        # TODO: value: [define how to serialize] # GP-ref:281,(C11)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x06|6), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x06|6))
        pass


class Entropy(Struct):
    # GP-ref: ETA,63
    scale_type_cls = EntropyObject
    arguments = {
        # TODO: Enforce that entropy has 4 items
        'entropy': Vec(H256)
    }
