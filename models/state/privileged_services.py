from scalecodec.base import ScaleType
from scalecodec.types import Struct, U32, Vec

from models.state.services import Services
from models.state.assurances import Assurances
from models.state.authorizer_queue import AuthorizerQueue
from models.state.validator_queue import ValidatorQueue


class PrivilegedServicesObject(ScaleType):
    # GP-ref:28,159
    def state_transition(self, extrinsic_assurances: Vec, assurances: Assurances, services: Services, validator_queue: ValidatorQueue, authorizer_queue: AuthorizerQueue):
        # TODO: input 1: Privileged_services current state (self)
        # TODO: input 2: Block.Extrinsic.assurances
        # TODO: input 3: Assurances of transitioned state of # GP-ref:27
        # TODO: input 4: Services of intermediate state of # GP-ref:24
        # TODO: input 5: ValidatorQueue of current state
        # TODO: input 6: AuthorizerQueue of current state
        # TODO: output 1: self transitioned state]
        pass

   # TODO: with Arjan get/serialize/deserialize this subsection of the state
    def storage_serialize(self):
        # TODO: Generalize by introducing the StateKeyConstructor function (C) | # GP-ref:280
        # TODO: key: blake2b(0x0C|12) # GP-ref:281,(C12)
        # TODO: value: [define how to serialize] # GP-ref:281,(C12)
        pass

    def storage_persist(self):
        # TODO: insert/update_kvdb(key: blake2b(0x0C|12), value: serialize(self))
        pass

    def storage_get(self):
        # TODO: set self = select_kvdb(key: blake2b(0x0C|12))
        pass


class PrivilegedServices(Struct):
    # GP-ref:CHI,93
    scale_type_cls = PrivilegedServicesObject
    arguments = {
        'service_empower': U32, # GP-ref:93,CHI-m,I.4.2
        'service_designate_authorizers': U32, # GP-ref:93,CHI-a,I.4.2
        'service_assign_validators': U32 # GP-ref:93,CHI-v,I.4.2
    }
