from scalecodec.types import Struct, Vec, H256
from models.other.validator_keys import ValidatorKeys


class Disputes(Struct):
    #GP-equation: 94 | SCALETYPE-DEFINITION: "DISPUTES"->"(ALLOW_SET,BAN_SET,PUNISH_SET,VALIDATORS_PRIOR_EPOCH)>" | "ALLOW_SET"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256" | "BAN_SET"->"VEC<WORK_REPORT_HASH>" | "PUNISH_SET"->"VEC<BS_KEY>" | "BS_KEY"->"H256" | "VALIDATORS_PRIOR_EPOCH"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS"-> refer to class ValidatorKeys for details.
    arguments = {
        'allow_set': Vec(H256),
        'ban_set': Vec(H256),
        'punish_set': Vec(H256),
        'validators_prior_epoch': Vec(ValidatorKeys())
    }
