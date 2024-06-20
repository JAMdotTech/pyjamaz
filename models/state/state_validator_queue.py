from scalecodec.types import Struct, Vec
from models.block.extrinsic import Extrinsic
from models.state.state_assurances import StateAssurances
from models.state.state_authorizer_queue import StateAuthorizerQueue
from models.state.state_privileged_services import StatePriviligedServices
from models.state.state_services import StateServices
from models.other.validator_keys import ValidatorKeys


class StateValidatorQueue(Struct):
    #GP-reference: IOTA | SCALETYPE-DEFINITION: "VALIDATOR_QUEUE"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    #GP-equation: 50 | SCALETYPE-DEFINITION: "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    arguments = {
        'state': Vec(ValidatorKeys())
    }

    #GP-equation: 28
    #TODO: Check: changed by manager service PrivilegedService?
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizersQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, state_priviliged_services: StatePriviligedServices, self, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 1: self of transitioned state]
        pass

