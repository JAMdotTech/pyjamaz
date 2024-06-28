from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, U32

from models.block import Header, HeaderObject


class TimeslotObject(ScaleType):
    #GP-ref:16,44
    def state_transition(self, header: HeaderObject):
        # TODO: input 1: self (strictly not needed according to GP-ref:16)
        # TODO: input 2: Header
        # TODO: output 1: transitioned state
        self.value['timeslot'] = header.value['timeslot']

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self) -> bytes:
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x11|11) # GP-ref: 281,(C11)
        # TODO: value: [define how to serialize] # GP-ref:281,(C11)
        timeslot = U32.new()
        scale_bytes = timeslot.encode(self.value['timeslot'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        timeslot = U32.new().decode(ScaleBytes(data))
        self.value['timeslot'] = timeslot


class Timeslot(Struct):
    # GP-ref:44
    scale_type_cls = TimeslotObject
    arguments = {
        'timeslot': U32 # GP-ref:44
    }
