from scalecodec.types import Struct, Tuple, Vec, U16, H256, H512, Bool


class ExtrinsicJudgement(Struct):
    #GP-equation: 96 | SCALETYPE-DEFINITION: "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)" | "WORK_REPORT_HASH"->"32BYTEHASH" | "VOTES"->"VEC<VOTE>" | "VOTE"->"(IS_VALID,VALIDATOR_IDX,SIGNATURE)" | "IS_VALID"->"BOOLEAN" | "VALIDATOR_IDX"->"U16" | "SIGNATURE"->"64BYTEHASH"
    arguments = {
        'work_report_hash': H256,
        'votes': Vec(Tuple(Bool,U16,H512))
    }

