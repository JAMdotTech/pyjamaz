from scalecodec.types import Struct, Vec
from models.header import Header
from models.validator_keys import ValidatorKeys


class StateValidatorArchive(Struct):
    #GP-reference: LAMBDA | SCALETYPE-DEFINITION: "VALIDATOR_ARCHIVE"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details.
    arguments = {
        'validator_archive': Vec(ValidatorKeys())
    }

    #graypaper-equation: 22
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.validator_archive of current state]
    #[TODO: input 4: State.validator_pool of current state]
    def state_transition(header: Header, i2: {}, i3: {}, i4: {}):
        #[TODO: output 1: self of transitioned state]
        pass

