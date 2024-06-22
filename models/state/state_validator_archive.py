from scalecodec.types import Struct, Vec
from models.block import Header
from models.state.state_timeslot import StateTimeslot
from models.state.state_validator_pool import StateValidatorPool
from models.other.validator_keys import ValidatorKeys


class StateValidatorArchive(Struct):
    #GP-reference: LAMBDA | SCALETYPE-DEFINITION: "VALIDATOR_ARCHIVE"->"VEC<VALIDATOR_KEYS>"
    #GP-equation: 50 | SCALETYPE-DEFINITION: "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    arguments = {
        'validator_archive': Vec(ValidatorKeys()) #TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(ValidatorKeys(),1023)
    }

    #GP-equation: 22,56
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: StateValidatorArchive of current state]
    #[TODO: input 4: StateValidatorPool of current state]
    def state_transition(header: Header, state_timeslot: StateTimeslot(), self, state_validator_pool: StateValidatorPool()):
        #[TODO: output 1: self of transitioned state]
        pass

    # GP-equation: 281,(C9)
    def storage_serialize(self):
        #TODO: serialize(self)
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x09|9),value:serialize(self))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x09|9))
        pass

