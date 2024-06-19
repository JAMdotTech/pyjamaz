from scalecodec.types import Struct
from models.extrinsic import Extrinsic
from models.privileged_services import PrivilegedServices
from models.state_assurances import StateAssurances
from models.state_authorizer_queue import StateAuthorizerQueue
from models.state_services import StateServices
from models.state_validator_queue import StateValidatorQueue


class StatePrivilegedServices(Struct):
    #GP-reference: CHI | SCALETYPE-DEFINITION: "PRIVILEGED_SERVICES"-> refer to class PrivilegedServices for details.
    #GP-equation: 93
    arguments = {
        'state': PrivilegedServices()
    }

    #GP-equation: 28, 159
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviliged_services current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizerQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, self, state_validator_queue: StateValidatorQueue, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 2: self transitioned state]
        pass

