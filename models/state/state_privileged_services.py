from scalecodec.types import Struct, U32
from models.block.extrinsic import Extrinsic
from models.state.state_assurances import StateAssurances
from models.state.state_authorizer_queue import StateAuthorizerQueue
from models.state.state_services import StateServices
from models.state.state_validator_queue import StateValidatorQueue


class StatePrivilegedServices(Struct):
    #GP-equation: CHI,93 | SCALETYPE-DEFINITION: "PRIVILEGED_SERVICES"->"(MANAGER,MANAGER_AUTHORIZER_QUEUE,MANAGER_VALIDATOR_QUEUE)>"
    #GP-reference: 93,CHI-m,I.4.2 | SCALETYPE-DEFINITION: "MANAGER"->"U32"
    #GP-reference: 93,CHI-a,I.4.2 | SCALETYPE-DEFINITION: "MANAGER_AUTHORIZER_QUEUE"->"U32"
    #GP-reference: 93,CHI-v,I.4.2 | SCALETYPE-DEFINITION: "MANAGER_VALIDATOR_QUEUE"->"U32"
    arguments = {
        'service_empower': U32,
        'service_designate_authorizers': U32,
        'service_assign_validators': U32
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

