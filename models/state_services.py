from scalecodec.types import Struct, Vec
from models.extrinsic import Extrinsic
from models.service_account import ServiceAccount
from models.state_assurances import StateAssurances
from models.state_authorizer_queue import StateAuthorizerQueue
from models.state_priviliged_services import StatePriviligedServices
from models.state_timeslot import StateTimeslot
from models.state_validator_queue import StateValidatorQueue


class StateServices(Struct):
    #GP-reference: DELTA | SCALETYPE-DEFINITION: "SERVICES"->"VEC<SERVICE_ACCOUNT>" | "SERVICE_ACCOUNT refer to class ServiceAccount for details.
    arguments = {
        #TODO: INDEX OF SERVICE ACCOUNT state[1] = ServiceAccount is ServiceAccount of index 1
        'state': Vec(ServiceAccount())
    }

    #graypaper-equation: 24
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.preimages]
    #[TODO: input 2: StateServices of current state]
    #[TODO: input 3: StateTimeslot of transitioned state]
    def state_transition_intermediate1(extrinsic: Extrinsic, self, state_timeslot: StateTimeslot):
        #[TODO: output 1: self of intermediate state]
        pass


    #graypaper-equation: 28
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateAuthorizerQueue of current state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, self, state_priviliged_services: StatePriviligedServices, state_validator_queue: StateValidatorQueue, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 1: self of transitioned state]
        pass


