from scalecodec.types import Struct, Vec, H256
from models.block.extrinsic import Extrinsic
from models.other.validator_keys import ValidatorKeys


class StateDisputes(Struct):
    #GP-equation: PSI,94 | SCALETYPE-DEFINITION: "DISPUTES"->"(ALLOW_SET,BAN_SET,PUNISH_SET,VALIDATORS_PRIOR_EPOCH)>"
    #GP-reference: 94,PSI-a | SCALETYPE-DEFINITION: "ALLOW_SET"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    #GP-reference: 94,PSI-b | SCALETYPE-DEFINITION: "BAN_SET"->"VEC<WORK_REPORT_HASH>"
    #GP-reference: 94,PSI-p | SCALETYPE-DEFINITION: "PUNISH_SET"->"VEC<BS_KEY>" | "BS_KEY"->"H256"
    #GP-reference: 94,PSI-k,50 | SCALETYPE-DEFINITION: "VALIDATORS_PRIOR_EPOCH"->"VEC<VALIDATOR_KEYS>" | "VALIDATOR_KEYS"-> refer to class ValidatorKeys for details.
    arguments = {
        'allow_set': Vec(H256),
        'ban_set': Vec(H256),
        'punish_set': Vec(H256),
        'validators_prior_epoch': Vec(ValidatorKeys())
    }

    #GP-equation: 23
    #[Volgorde input parameters SELF eerst conventie?]
    #[TODO: input 1: Block.Extrinsic.judgements]
    #[TODO: input 2: StateDisputes of current state]
    def state_transition(extrinsic: Extrinsic, self):
        #[TODO: output 1: self of transitioned state]
        pass

    # GP-equation: 281,(C5)
    def storage_serialize(self):
        #TODO: serialize([COMPLICATED; self with first 3 individual parts ordered])
        #TODO ATTENTION: ordering is required per GP-equation: 281
        pass

    #TODO: Generalize by introducing the StateKeyConstructor function (C) | GP-reference 280
    def storage_persist(self):
        #TODO: insert/update_kvdb(key:blake2b(0x05|5),value:serialize([COMPLICATED; self with first 3 individual parts ordered]))
        pass

    def storage_get(self):
        #TODO: set self = select_kvdb(key:blake2b(0x05|5))
        pass

