from scalecodec.types import Struct, Vec
from models.block import Extrinsic
from models.other.service_account import ServiceAccount
from models.old_state.state_assurances import StateAssurances
from models.old_state.state_authorizer_queue import StateAuthorizerQueue
from models.old_state.state_privileged_services import StatePrivilegedServices
from models.state import Timeslot
from models.old_state.state_validator_queue import StateValidatorQueue


class StateServices(Struct):
    #GP-reference: DELTA | SCALETYPE-DEFINITION: "SERVICES"->"VEC<SERVICE_ACCOUNT>" | "SERVICE_ACCOUNT refer to class ServiceAccount for details.
    #GP-equation: 86
    arguments = {
        #TODO: INDEX OF SERVICE ACCOUNT services[i] = ServiceAccount is ServiceAccount of index 1
        'services': Vec(ServiceAccount())
    }

    #GP-equation: 24
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.preimages]
    #[TODO: input 2: StateServices of current state]
    #[TODO: input 3: Timeslot of transitioned state]
    def state_transition_preimages(extrinsic: Extrinsic, self, timeslot: Timeslot):
        #[TODO: output 1: self of intermediate state]
        pass

    #GP-reference: I.4.2
    #[TODO: check inconsistency GP-I.4.2 mentions function, whereas GP-4.2.1 does not mention function]
    #[TODO: input: Unknown]
    def state_transition_accumulation(self):
        #[TODO: output: unknown]
        pass


    #GP-equation: 28
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned old_state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate old_state of graypaper-equation: 24]
    #[TODO: input 4: StatePrivilegedServices current old_state]
    #[TODO: input 5: StateValidatorQueue of current old_state]
    #[TODO: input 6: StateAuthorizerQueue of current old_state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, self, state_privileged_services: StatePrivilegedServices, state_validator_queue: StateValidatorQueue, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 1: self of transitioned old_state]
        pass


