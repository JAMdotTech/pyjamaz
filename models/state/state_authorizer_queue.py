from scalecodec.types import Struct, Vec, H256
from models.block.extrinsic import Extrinsic
from models.state.state_assurances import StateAssurances
from models.state.state_privileged_services import StatePrivilegedServices
from models.state.state_services import StateServices
from models.state.state_validator_queue import StateValidatorQueue


class StateAuthorizerQueue(Struct):
    #GP-reference: PHI | SCALETYPE-DEFINITION: "AUTHORIZER_QUEUE"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256"
    #TODO: create separate classes for authorizer_pool and authorizer (used by both StateAuthorizerPool and StateAuthorizerQueue)
    #GP-equation: 82
    arguments = {
        'authorizer_queue': Vec(Vec(H256))
    }

    #GP-equation: 28,83,84
    #TODO: Check: changed by manager service PrivilegedService?
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizerQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, state_privileged_services: StatePrivilegedServices, state_validator_queue: StateValidatorQueue, self):
        #[TODO: output 4: self of transitioned state]
        pass

    # GP-equation: 281,(C2)
    def storage_serialize(self):
        #TODO: serialize(self)
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x02|2),value:serialize(self))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x02|2))
        pass

