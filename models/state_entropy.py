from scalecodec.types import Struct, Vec, H256
from models.header import Header
from models.state_timeslot import StateTimeslot


class StateEntropy(Struct):
    #GP-reference: ETA | SCALETYPE-DEFINITION: "ENTROPY"->"VEC<ENTROPY_VALUE>" | "ENTROPY_VALUE"->"H256"
    arguments = {
        'state': Vec(H256)
    }

    #graypaper-equation: 20
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: StateEntropy of current state]
    def state_transition(header: Header, state_timeslot: StateTimeslot, self):
        #[TODO: output 1: self of transitioned state]
        pass

