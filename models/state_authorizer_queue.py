from scalecodec.types import Struct, Vec, H256

from models.extrinsic import Extrinsic
from models.state_assurances import StateAssurances
from models.state_privileged_services import StatePriviligedServices
from models.state_services import StateServices
from models.state_validator_queue import StateValidatorQueue


class StateAuthorizerQueue(Struct):
    #GP-reference: PHI | SCALETYPE-DEFINITION: "AUTHORIZER_QUEUE"->"VEC<AUTHORIZER>" | "AUTHORIZER"->"VEC<AUTHORIZATION>" | "AUTHORIZATION"->"H256" |
    arguments = {
        'state': Vec(Vec(H256))
    }

    #GP-equation: 28
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizerQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, state_priviliged_services: StatePriviligedServices, state_validator_queue: StateValidatorQueue, self):
        #[TODO: output 4: self of transitioned state]
        pass

