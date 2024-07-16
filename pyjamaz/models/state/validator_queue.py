from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, Vec

from pyjamaz.models.state.assurances import AssurancesObject
from pyjamaz.models.state.privileged_services import PrivilegedServicesObject
from pyjamaz.models.state.services import ServicesObject
from pyjamaz.models.common import ValidatorKeys
from pyjamaz.models.state.authorizer_queue import AuthorizerQueueObject


class ValidatorQueueObject(ScaleType):
    """
    Creates a new `ValidatorQueue` object. ValidatorQueue is an isolated subsection of State.
    GP-ref: 28
    """
    def state_transition(self, extrinsic_assurances: Vec, assurances: AssurancesObject, services: ServicesObject, privileged_services: PrivilegedServicesObject, authorizer_queue: AuthorizerQueueObject):
        """
        GP-ref: 28 Defines STF for ValidatorQueue

        :param self: ValidatorQueueObject of current state (self)
        :param extrinsic_assurances: Block.Extrinsic.assurances
        :param assurances: AssurancesObject of transitioned state of GP-ref:27
        :param services: ServicesObject of intermediate state of GP-ref:24
        :param privileged_services: PrivilegedServicesObject current state
        :param authorizer_queue: AuthorizersQueueObject of current state
        :return: ValidatorArchiveObject of transitioned state
        """
        # TODO: actual state transition logic goes here
        # TODO: Check, should be changed by manager service of PrivilegedServices
        # self.value['validator_queue'] = XXX
        pass

    def storage_serialize(self) -> bytes:
        """
        GP-ref:280,281,C(7) SCALE-encodes / serializes ValidatorQueue state

        :param self:
        :return: SCALE-encoded / serialized ValidatorQueue state
        """
        # TODO with Arjan; simple serialization of validator_queue list
        validator_queue = Vec.new()
        scale_bytes = validator_queue.encode(self.value['validator_queue'])
        return scale_bytes.data

    def storage_deserialize(self, data: bytes):
        """
        GP-ref:280,281,C(7) SCALE-decodes / deserializes ValidatorQueue state

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized ValidatorQueue state
        """
        # TODO with Arjan; simple deserialization of validator_queue list
        validator_queue = ValidatorQueue.new().decode(ScaleBytes(data))
        self.value['validator_queue'] = validator_queue


class ValidatorQueue(Struct):
    # GP-ref:IOTA,50
    scale_type_cls = ValidatorQueueObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_queue': Vec(ValidatorKeys()) # GP-ref:50
    }
