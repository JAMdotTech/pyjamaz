from scalecodec.types import Struct, Vec
from models.validator_keys import ValidatorKeys


class StateValidatorQueue(Struct):
    #GP-reference: IOTA | SCALETYPE-DEFINITION: "VALIDATOR_QUEUE"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details.
    arguments = {
        'validator_queue': Vec(ValidatorKeys())
    }

    #graypaper-equation: 28
    #[TODO: input 1: Block.Extrinsic.assurances]
    #[TODO: input 2: State.assurances of transitioned state of graypaper-equation: 27]
    #[TODO: input 3: State.services of intermediate state of graypaper-equation: 24]
    #[TODO: input 4: State.priviliged_services current state]
    #[TODO: input 5: State.enqueued_validators of current state]
    #[TODO: input 6: State.authorizers_queue of current state]
    def state_transition(i1: {}, i2: {}, i3: {}, i4: {}, i5: {}, i6: {}):
        #[TODO: output 1: self of transitioned state]
        pass

