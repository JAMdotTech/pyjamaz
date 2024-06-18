from scalecodec.types import Struct, Tuple, Vec, H256, U8
from models.header import Header
from models.extrinsic import Extrinsic
from models.state_entropy import StateEntropy
from models.state_timeslot import StateTimeslot
from models.state_validator_pool import StateValidatorPool
from models.state_validator_queue import StateValidatorQueue
from models.ticket import Ticket
from models.validator_keys import ValidatorKeys


class StateSafrole(Struct):
    #GP-reference: PSI | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>" | "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details. | "EPOCH_ROOT"->"H1572864"  | "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>" | "TICKETS"->"VEC<TICKET>" | "TICKET"-> refer to class Ticket for details.
    #TODO: "EPOCH_ROOT"->"H1572864" (new type large hash)
    #TODO: "SLOT_SEALER_SERIES"->"ENUM" (new type XOR)
    arguments = {
        'state': Tuple(Vec(ValidatorKeys()),H256,Enum(Vec(Ticket()),H256),Vec(Ticket()))
    }

    #graypaper-equation: 19
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

