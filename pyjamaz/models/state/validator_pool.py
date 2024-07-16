from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, Vec

from pyjamaz.models.block import HeaderObject
from pyjamaz.models.state.disputes import DisputesObject
from pyjamaz.models.state.safrole import SafroleObject
from pyjamaz.models.common import ValidatorKeys
from pyjamaz.models.state.timeslot import TimeslotObject


class ValidatorPoolObject(ScaleType):
    """
    Creates a new `ValidatorPool` object. ValidatorPool is an isolated subsection of State.
    GP-ref: 21,56
    """
    def state_transition(self, header: HeaderObject, timeslot: TimeslotObject, safrole: SafroleObject, disputes: DisputesObject):
        """
        GP-ref: 21,56 Defines STF for ValidatorPool

        :param self: ValidatorPoolObject of current state
        :param header: HeaderObject
        :param timeslot: TimeslotObject of current state
        :param safrole: SafroleObject of current state
        :param disputes: Disputes of transitioned state
        :return: ValidatorPoolObject of transitioned state
        """
        # TODO: actual state transition logic goes here
        # self.value['validator_pool'] = XXX
        pass

    def storage_serialize(self) -> bytes:
        """
        GP-ref:280,281,C(8) SCALE-encodes / serializes ValidatorPool state

        :param self:
        :return: SCALE-encoded / serialized ValidatorPool state
        """
        # TODO with Arjan; simple serialization of validator_pool list
        validator_pool = Vec.new()
        scale_bytes = validator_pool.encode(self.value['validator_pool'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        """
        GP-ref:280,281,C(8) SCALE-decodes / deserializes ValidatorPool state

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized ValidatorPool state
        """
        # TODO with Arjan; simple deserialization of validator_pool list
        validator_pool = ValidatorPool.new().decode(ScaleBytes(data))
        self.value['validator_pool'] = validator_pool


class ValidatorPool(Struct):
    # GP-ref: KAPPA,50
    scale_type_cls = ValidatorPoolObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_pool': Vec(ValidatorKeys()) # GP-ref:50
    }
