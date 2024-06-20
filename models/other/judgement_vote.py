from scalecodec.types import Struct, Bool, U32, H512


class JudgementVote(Struct):
    #GP-equation: 96,97 | SCALETYPE-DEFINITION: "VOTE"->"(IS_VALID,VALIDATOR_IDX,SIGNATURE)" |
    #GP-reference: X | SCALETYPE-DEFINITION: "IS_VALID"->"BOOL"
    #GP-reference: Nv | SCALETYPE-DEFINITION: "VALIDATOR_IDX"->"U32" #TODO: Type implicit, but derived from Hk in GP-equation 272
    #GP-reference: - | SCALETYPE-DEFINITION: "SIGNATURE"->"H512"
    arguments = {
        'is_valid': Bool,
        'validator_idx': U32, #TODO: Type implicit, but derived from Hk in GP-equation 272
        'signature': H512
    }
