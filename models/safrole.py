from scalecodec.types import Struct, Vec, H256
from models.ticket import Ticket
from models.validator_keys import ValidatorKeys


class Safrole(Struct):
    #GP-equation: 46 | SCALETYPE-DEFINITION: "SAFROLE"->"(VALIDATORS,EPOCH_ROOT,SLOT_SEALER_SERIES,TICKETS)>" | "VALIDATORS"->"VEC<VALIDATOR_KEYS>" | refer to class ValidatorKeys for details. | "EPOCH_ROOT"->"H1572864"  | "SLOT_SEALER_SERIES"->"ENUM<TICKETS,BS_KEYS>" | "TICKETS"->"VEC<TICKET>" | "TICKET"-> refer to class Ticket for details.
    #TODO: "EPOCH_ROOT"->"H1572864" (new type large hash)
    #TODO: "SLOT_SEALER_SERIES"->"ENUM" (new type XOR)
    arguments = {
        'validators': Vec(ValidatorKeys()),
        'epoch_root': H256,
        'slot_sealer_series': Enum(Vec(Ticket()), H256),
        'tickets': Vec(Ticket())
    }

