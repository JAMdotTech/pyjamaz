from scalecodec.types import Struct, Vec, U8, Array, Enum, H256
from models.block.header import Header
from models.block.extrinsic import Extrinsic
from models.other.ticket import Ticket
from models.other.validator_keys import ValidatorKeys
from models.state.state_entropy import StateEntropy
from models.state.state_timeslot import StateTimeslot
from models.state.state_validator_pool import StateValidatorPool
from models.state.state_validator_queue import StateValidatorQueue


class StateSafrole(Struct):
    #GP-equation: PSI,46 | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>"
    #GP-reference: GAMMA_k,50 | SCALETYPE-DEFINITION: "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details.
    #GP-reference: GAMMA_z,47 | SCALETYPE-DEFINITION: "EPOCH_ROOT"->"H1572864"
    #GP-reference: GAMMA_s,48,49 | SCALETYPE-DEFINITION: "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>"
    #GP-reference: GAMMA_a,48,49 | SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>" | "TICKET"-> refer to class Ticket for details
    arguments = {
        'validators': Vec(ValidatorKeys()),
        'epoch_root': Array(U8,196608),
        'slot_sealer_series': Enum(tickets=Vec(Ticket()), bs_keys=Vec(H256)),
        'tickets': Vec(Ticket())
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

