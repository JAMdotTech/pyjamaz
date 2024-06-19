from scalecodec.types import Struct, H256, U8
from models.extrinsic import Extrinsic
from models.state_assurances import StateAssurances
from models.state_authorizer_queue import StateAuthorizerQueue
from models.state_priviliged_services import StatePriviligedServices
from models.state_services import StateServices
from models.state_validator_queue import StateValidatorQueue


class Ticket(Struct):
    #GP-reference: C | SCALETYPE-DEFINITION: "TICKET"->"(TICKET_ID,ENTRY_IDX)" | "TICKET_ID"->"H256" | "ENTRY_IDX"->"U8"
    #GP-equation: 49
    arguments = {
        'ticket_id': H256,
        'entry_idx': U8
    }

    #GP-equation: 28
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizersQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, state_priviliged_services: StatePriviligedServices, state_validator_queue: StateValidatorQueue, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 1: new tickets (transitioned state?)]
        pass
