from scalecodec.types import Struct, Vec, H256
from models.header import Header


class StateEntropy(Struct):
    #GP-reference: ETA | SCALETYPE-DEFINITION: "ENTROPY"->"VEC<ENTROPY_VALUE>" | "ENTROPY_VALUE"->"H256"
    arguments = {
        'entropy': Vec(H256)
    }

    #graypaper-equation: 20
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: Timeslot of current state]
    #[TODO: input 3: State.entropy of current state]
    def state_transition(header: Header, i2: {}, i3: {}):
        #[TODO: output 1: self of transitioned state]
        pass

