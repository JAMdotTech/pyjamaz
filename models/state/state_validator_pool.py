from scalecodec.types import Struct, Vec
from models.block.header import Header
from models.state.state_disputes import StateDisputes
from models.state.state_safrole import StateSafrole
from models.state.state_timeslot import StateTimeslot
from models.other.validator_keys import ValidatorKeys


class StateValidatorPool(Struct):
    #GP-reference: KAPPA | SCALETYPE-DEFINITION: "VALIDATOR_POOL"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    #GP-equation: 50 | SCALETYPE-DEFINITION: "VALIDATOR_KEYS" refer to class ValidatorKeys for details.
    arguments = {
        'validator_pool': Vec(ValidatorKeys())
    }

    #GP-equation: 21,56
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: StateValidatorPool of current state]
    #[TODO: input 4: StateSafrole of current state]
    #[TODO: input 5: StateDisputes of transitioned state]
    def state_transition(header: Header, state_timeslot: StateTimeslot(), self, state_safrole: StateSafrole(), state_disputes: StateDisputes()):
        #[TODO: output 1: self of transitioned state]
        pass

