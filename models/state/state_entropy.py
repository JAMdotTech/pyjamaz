from scalecodec.types import Struct, H256, Array
from models.block.header import Header
from models.state.state_timeslot import StateTimeslot


class StateEntropy(Struct):
    #GP-reference: ETA | SCALETYPE-DEFINITION: "ENTROPY"->"VEC<ENTROPY_VALUE>" | "ENTROPY_VALUE"->"H256"
    #GP-equation: 63
    arguments = {
        'state': Array(H256,4)
    }

    #GP-equation: 20,64,65
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: StateEntropy of current state]
    def state_transition(header: Header, state_timeslot: StateTimeslot, self):
        #[TODO: output 1: self of transitioned state]
        pass

