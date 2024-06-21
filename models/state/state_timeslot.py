from scalecodec.types import Struct, U32
from models.block.header import Header


class StateTimeslot(Struct):
    #GP-equation: 16,44 | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    arguments = {
        'timeslot': U32
    }

    #GP-equation: 16,44
    #[TODO: input 1: Header]

    #input = headertype en niet Header
    def state_transition(self, header: Header):
        #self += 1
        #[TODO: output 1: self of transitioned state]
        pass

    # GP-equation: 281,(C11)
    def storage_serialize(self):
        #TODO: serialize(self)
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key: blake2b(0x0B | 11), value: serialize(self))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key: blake2b(0x0B | 11))
        pass

