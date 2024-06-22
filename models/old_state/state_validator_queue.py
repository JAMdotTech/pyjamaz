from scalecodec.types import Struct, Vec
from models.block import Extrinsic
from models.old_state.state_assurances import StateAssurances
from models.old_state.state_authorizer_queue import StateAuthorizerQueue
from models.old_state.state_privileged_services import StatePriviligedServices
from models.old_state.state_services import StateServices
from models.other.validator_keys import ValidatorKeys


class StateValidatorQueue(Struct):
    #GP-reference: IOTA | SCALETYPE-DEFINITION: "VALIDATOR_QUEUE"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    #GP-equation: 50 | SCALETYPE-DEFINITION: "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    arguments = {
        'validator_queue': Vec(ValidatorKeys()) #TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
    }

    #GP-equation: 28
    #TODO: Check: changed by manager service PrivilegedService?
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: StateAssurances of transitioned old_state of graypaper-equation: 27]
    #[TODO: input 3: StateServices of intermediate old_state of graypaper-equation: 24]
    #[TODO: input 4: StatePriviligedServices current old_state]
    #[TODO: input 5: StateValidatorQueue of current old_state]
    #[TODO: input 6: StateAuthorizersQueue of current old_state]
    def state_transition(extrinsic: Extrinsic, state_assurances: StateAssurances, state_services: StateServices, state_priviliged_services: StatePriviligedServices, self, state_authorizer_queue: StateAuthorizerQueue):
        #[TODO: output 1: self of transitioned old_state]
        pass

    # GP-equation: 281,(C7)
    def storage_serialize(self):
        #TODO: serialize(self)
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x07|7),value:serialize(self))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x07|7))
        pass

