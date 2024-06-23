from scalecodec.base import ScaleType
from scalecodec.types import Struct, Vec, H256

from models.state.assurances import Assurances
from models.state.privileged_services import PrivilegedServices
from models.state.services import Services
from models.state.validator_queue import ValidatorQueue


class AuthorizerQueueObject(ScaleType):
    # GP-ref:28,83,84
    # TODO: Check, should be changed by manager service of PrivilegedServices
    def state_transition(self, extrinsic_assurances: Vec, assurances: Assurances, services: Services, privileged_services: PrivilegedServices, validator_queue: ValidatorQueue):
        # TODO: input 1: AuthorizerQueue of current state (self)
        # TODO: input 2: Block.Extrinsic.assurances]
        # TODO: input 3: Assurances of transitioned state # GP-ref:27
        # TODO: input 4: Services of intermediate state # GP-ref:24
        # TODO: input 5: PrivilegedServices current state
        # TODO: input 6: ValidatorQueue of current state
        # TODO: output 1: self of transitioned state]
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x02|2) # GP-ref:281,(C2)
        # TODO: value: [define how to serialize] # GP-ref:281,(C2)
        pass

    def storage_persist(self):
        # TODO: persist
        pass

    def storage_get(self):
        # TODO: key:blake2b(0x02|2)
        pass


class AuthorizerQueue(Struct):
    # GP-ref:PHI,82
    # TODO: create separate classes for authorizer_queue and authorizer (used by both AuthorizerPool and AuthorizerQueue)
    scale_type_cls = AuthorizerQueueObject
    arguments = {
        # TODO Constant(C): CORES=341; size of list is exactly CORES=341 Needs to be more strict.
        # TODO Constant(Q): SIZE_AUTHORIZERS_QUEUE=80; size of list is exactly (probably, but check) SIZE_AUTHORIZERS_QUEUE=80 Needs to be more strict.
        'authorizer_queue': Vec(Vec(H256))
    }
