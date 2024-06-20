from scalecodec.types import Struct, Vec, H256, Enum, U8, Array
from models.other.ticket import Ticket
from models.other.validator_keys import ValidatorKeys


class Safrole(Struct):
    #GP-equation: 46 | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>" | "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details. | "EPOCH_ROOT"->"H1572864"  | "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>" | "TICKETS"->"VEC<TICKET>" | "TICKET"-> refer to class Ticket for details. | BS_KEYS->"VEC<BS_KEY>" | BS_KEY->"H256"
    #GP-equation: gamma_z, 47 | epoch_root
    #GP-equation: gamma_s, 48,49 | slot_sealer_series
    arguments = {
        'validators': Vec(ValidatorKeys()),
        'epoch_root': Array(U8,196608),
        'slot_sealer_series': Enum(tickets=Vec(Ticket()), bs_keys=Vec(H256)),
        'tickets': Vec(Ticket())
    }

