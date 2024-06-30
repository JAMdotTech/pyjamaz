from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, Vec, Array, U8, Enum, H256, U32

from models.block import HeaderObject
from models.common import Ticket, ValidatorKeys
from models.state.entropy import EntropyObject
from models.state.timeslot import TimeslotObject
from models.state.validator_pool import ValidatorPoolObject
from models.state.validator_queue import ValidatorQueueObject


class SafroleObject(ScaleType):
    """
    Creates a new `Timeslot` object. Timeslot is an isolated subsection of State.
    GP-ref: 16,44
    """

    # GP-ref:19,56
    def state_transition(self, header: HeaderObject, timeslot: TimeslotObject, extrinsic_tickets: Vec, validator_queue: ValidatorQueueObject, validator_entropy: EntropyObject, validator_pool: ValidatorPoolObject):
        """
        GP-ref:19,56 Defines STF for Safrole

        :param self: Safrole of current state (self)
        :param header: Header
        :param timeslot: Timeslot pre-state
        :param extrinsic_tickets: Block.Extrinsic.tickets
        :param validator_queue: ValidatorQueue pre-state
        :param validator_entropy: Entropy post-state
        :param validator_pool: ValidatorPool post-state
        :return: Safrole post-state
        """

        # Todo: actual sequence of logic for state transition function
        # self.value['timeslot'] = header.value['timeslot']

    def storage_serialize(self) -> bytes:
        """
        GP-ref:280,281,C(11) SCALE-encodes / serializes Safrole state

        :param self:
        :return: SCALE-encoded / serialized Safrole state
        """

        # TODO: Strict & explicit encoding for Safrole object
        safrole = U32.new()
        # TODO: How to concatenate inputs?
        scale_bytes = safrole.encode(self.value['validators'],self.value['epoch_root'],self.value['slot_sealer_series'],self.value['tickets'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        """
        GP-ref:280,281,C(4) SCALE-decodes / deserializes Safrole state

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized Safrole state
        """
        # TODO: decode and map to Safrole Object
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot


class Safrole(Struct):
    # GP-ref:PSI,46
    scale_type_cls = SafroleObject
    arguments = {
        # TODO: Consider creating a class ValidatorKeySets [Vec(ValidatorKeys())]; simplifies strictness
        'validators': Vec(ValidatorKeys()), # GP-ref:GAMMA_k,50
        # TODO: Discuss with Arjan: fixed length Bytes-type
        'epoch_root': Array(U8,196608), # GP-ref:GAMMA_z,47
        # TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
        'slot_sealer_series': Enum(tickets=Vec(Ticket()), bs_keys=Vec(H256)), # GP-ref:GAMMA_s,48,49
        # TODO: Consider creating a class Tickets [Vec(Ticket())]; simplifies strictness
        'tickets': Vec(Ticket()) # GP-ref:GAMMA_a,48,49
    }
