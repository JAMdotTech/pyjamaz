from scalecodec.types import Struct, Bool, U16, H512


class JudgementVote(Struct):
    #GP-equation: 96,97 | SCALETYPE-DEFINITION: "VOTE"->"(IS_VALID,VALIDATOR_IDX,SIGNATURE)" | "IS_VALID"->"BOOL" | "VALIDATOR_IDX"->"U16" | "SIGNATURE"->"H512"
    arguments = {
        'is_valid': Bool,
        'validator_idx': U16,
        'signature': H512
    }
