from scalecodec.types import Struct, Vec
from models.header import Header
from models.validator_keys import ValidatorKeys


class StateValidatorPool(Struct):
    #GP-reference: KAPPA | SCALETYPE-DEFINITION: "VALIDATOR_POOL"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details.
    arguments = {
        'validator_pool': Vec(ValidatorKeys())
    }

    #GP-equation: 21
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.validator_pool of current state]
    #[TODO: input 4: State.safrole of current state]
    #[TODO: input 5: State.disputes of transitioned state]
    def state_transition(header: Header, i2: {}, i3: {}, i4: {}, i5: {}):
        #[TODO: output 1: self of transitioned state]
        pass

