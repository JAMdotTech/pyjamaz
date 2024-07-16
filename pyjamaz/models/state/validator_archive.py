from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, Vec

from pyjamaz.models.block import HeaderObject
from pyjamaz.models.common import ValidatorKeys
from pyjamaz.models.state.timeslot import TimeslotObject
from pyjamaz.models.state.validator_pool import ValidatorPoolObject


class ValidatorArchiveObject(ScaleType):
    """
    Creates a new `ValidatorArchive` object. ValidatorArchive is an isolated subsection of State.
    GP-ref: 22,56
    """
    def state_transition(self, header: HeaderObject, timeslot: TimeslotObject, validator_pool: ValidatorPoolObject):
        """
        GP-ref: 22,56 Defines STF for ValidatorArchive

        :param self: ValidatorArchive of current state (self)
        :param header: HeaderObject
        :param timeslot: TimeslotObject of current state
        :param validator_pool: ValidatorPool of current state
        :return: ValidatorArchiveObject of transitioned state
        """
        # TODO: actual state transition logic goes here
        # self.value['validator_archive'] = XXX
        pass

    def storage_serialize(self) -> bytes:
        """
        GP-ref:280,281,C(9) SCALE-encodes / serializes ValidatorArchive state

        :param self:
        :return: SCALE-encoded / serialized ValidatorArchive state
        """
        # TODO with Arjan; simple serialization of validator_archive list
        validator_archive = Vec.new()
        scale_bytes = validator_archive.encode(self.value['validator_archive'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        """
        GP-ref:280,281,C(9) SCALE-decodes / deserializes ValidatorArchive state

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized ValidatorArchive state
        """
        # TODO with Arjan; simple deserialization of validator_archive list
        validator_archive = ValidatorArchive.new().decode(ScaleBytes(data))
        self.value['validator_archive'] = validator_archive


class ValidatorArchive(Struct):
    # GP-ref: LAMBDA,50
    scale_type_cls = ValidatorArchiveObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_archive': Vec(ValidatorKeys()) # GP-ref:50
    }
