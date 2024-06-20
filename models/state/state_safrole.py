from scalecodec.types import Struct
from models.block.header import Header
from models.block.extrinsic import Extrinsic
from models.other.safrole import Safrole
from models.state.state_entropy import StateEntropy
from models.state.state_timeslot import StateTimeslot
from models.state.state_validator_pool import StateValidatorPool
from models.state.state_validator_queue import StateValidatorQueue


class StateSafrole(Struct):
    #GP-reference: PSI | SCALETYPE-DEFINITION: "SAFROLE"-> refer to class Safrole for details.
    #GP-equation: 46
    arguments = {
        'state': Safrole()
    }

    #GP-equation: 19,56
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Header]
    #[TODO: input 2: StateTimeslot of current state]
    #[TODO: input 3: Block.Extrinsic.tickets]
    #[TODO: input 4: StateSafrole of current state]
    #[TODO: input 5: StateValidatorQueue of current state]
    #[TODO: input 6: StateEntropy of transitioned state]
    #[TODO: input 7: StateValidatorPool of transitioned state]
    def state_transition(header: Header, state_timeslot: StateTimeslot, extrinsic: Extrinsic, self, state_validator_queue: StateValidatorQueue, state_validator_entropy: StateEntropy, state_validator_pool: StateValidatorPool):
        #[TODO: output 1: self of transitioned state]
        pass

