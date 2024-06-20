from scalecodec.types import Struct, U32, H256, H512, Bool


class ExtrinsicAssurance(Struct):
    #GP-equation: 116-120,Ea | SCALETYPE-DEFINITION: "ASSURANCE"->"(WORK_REPORT_HASH,IS_AVAILABLE,VALIDATOR_IDX,SIGNATURE)"
    #GP-reference: 116-120,a | SCALETYPE-DEFINITION: "WORK_REPORT_HASH"->"H256"
    #GP-reference: 116-120,f | SCALETYPE-DEFINITION: "IS_AVAILABLE"->"BOOL"
    #GP-reference: 116-120,v | SCALETYPE-DEFINITION: "VALIDATOR_IDX"->"U16"
    #GP-reference: 116-120,s | SCALETYPE-DEFINITION: "SIGNATURE"->"H512"
    arguments = {
        'work_report_hash': H256,
        'is_available': Bool,
        'validator_idx': U32, #TODO: Type implicit, but derived from Hk in GP-equation 272
        'signature': H512
    }

