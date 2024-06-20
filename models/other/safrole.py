from scalecodec.types import Struct, Vec, H256, Enum, U8, Array
from models.other.ticket import Ticket
from models.other.validator_keys import ValidatorKeys


class Safrole(Struct):
    #GP-equation: 46 | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>"
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

