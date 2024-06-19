from scalecodec.types import Struct
from models.disputes import Disputes
from models.extrinsic import Extrinsic


class StateDisputes(Struct):
    #GP-reference: PSI | SCALETYPE-DEFINITION: "DISPUTES"-> refer to class Disputes for details.
    arguments = {
        'state': Disputes()
    }

    #GP-equation: 23
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: StateDisputes of current state]
    def state_transition(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of transitioned state]
        pass


