from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, U32

from models.block import HeaderObject


class TimeslotObject(ScaleType):
    #GP-ref:16,44
    def state_transition(self, header: HeaderObject):
        """
        GP-ref:16,44 Defines STF for Timeslot

        :param self: input 1: self (strictly not needed according to GP-ref:16
        :param header: Header
        :return: transitioned state for Timeslot
        """
        self.value['timeslot'] = header.value['timeslot']

    def storage_serialize(self) -> bytes:
        """
        GP-ref:280,281,C(11) SCALE-encodes / serializes Timeslot state

        :param self:
        :return: SCALE-encoded / serialized Timeslot state
        """
        timeslot = U32.new()
        scale_bytes = timeslot.encode(self.value['timeslot'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        """
        GP-ref:280,281,C(11) SCALE-decodes / deserializes Timeslot state

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized Timeslot state
        """
        timeslot = U32.new().decode(ScaleBytes(data))
        self.value['timeslot'] = timeslot


class Timeslot(Struct):
    # GP-ref:44
    scale_type_cls = TimeslotObject
    arguments = {
        'timeslot': U32 # GP-ref:44
    }
