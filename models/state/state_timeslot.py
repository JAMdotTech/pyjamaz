from scalecodec.types import Struct, U32
from models.block.header import Header


class StateTimeslot(Struct):
    #GP-equation: 16,44 | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    arguments = {
        'state': U32
    }

    #GP-equation: 16,44
    #[TODO: input 1: Header]
    def state_transition(header: Header):
        #self += 1
        #[TODO: output 1: self of transitioned state]
        pass

