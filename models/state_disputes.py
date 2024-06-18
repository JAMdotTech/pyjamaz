from scalecodec.types import Struct, Tuple, Vec, H256

from models.extrinsic import Extrinsic
from models.validator_keys import ValidatorKeys


class StateDisputes(Struct):
    #GP-reference: PSI | SCALETYPE-DEFINITION: "DISPUTES"->"(ALLOW_SET,BAN_SET,PUNISH_SET,VALIDATORS_PRIOR_EPOCH)>" | "ALLOW_SET"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256" | "BAN_SET"->"VEC<WORK_REPORT_HASH>" | "PUNISH_SET"->"VEC<BS_KEY>" | "BS_KEY"->"H256" | "VALIDATORS_PRIOR_EPOCH"-> refer to class WorkReport for details.
    arguments = {
        'state': Tuple(Vec(H256),Vec(H256),Vec(H256),ValidatorKeys())
    }

    #graypaper-equation: 23
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: StateDisputes of current state]
    def state_transition(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of transitioned state]
        pass

