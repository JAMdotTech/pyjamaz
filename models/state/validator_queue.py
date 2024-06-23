from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec

from models.state.assurances import Assurances
from models.state.privileged_services import PrivilegedServices
from models.state.services import Services
from models.common import ValidatorKeys
from models.state.authorizer_queue import AuthorizerQueue


class ValidatorQueueObject(ScaleType):
    # GP-ref:28
    # TODO: Check, should be changed by manager service of PrivilegedServices

    def state_transition(self, extrinsic_assurances: Vec, assurances: Assurances, services: Services, privileged_services: PrivilegedServices, authorizer_queue: AuthorizerQueue):
        # TODO: input 1: ValidatorQueue of current state (self)
        # TODO: input 2: Block.Extrinsic.assurances
        # TODO: input 3: Assurances of transitioned state of # GP-ref:27
        # TODO: input 4: Services of intermediate state of # GP-ref:24
        # TODO: input 5: PrivilegedServices current state
        # TODO: input 6: AuthorizersQueue of current state
        # TODO: output 1: self of transitioned state
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x07|7) # GP-ref:281,(C7)
        # TODO: value: [define how to serialize] # GP-ref:281,(C7)
        pass

    def storage_persist(self):
        # TODO: persist
        pass

    def storage_get(self):
        # TODO: key:blake2b(0x07|7)
        pass


class ValidatorQueue(Struct):
    # GP-ref:IOTA,50
    scale_type_cls = ValidatorQueueObject
    arguments = {
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
        'validator_queue': Vec(ValidatorKeys()) # GP-ref:50
    }
