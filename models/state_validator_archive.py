from scalecodec.types import Struct, Vec
from models.header import Header
from models.state_timeslot import StateTimeslot
from models.state_validator_pool import StateValidatorPool
from models.validator_keys import ValidatorKeys


class StateValidatorArchive(Struct):
    #GP-reference: LAMBDA | SCALETYPE-DEFINITION: "VALIDATOR_ARCHIVE"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    #GP-equation: 50
    arguments = {
        'state': Vec(ValidatorKeys())
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

