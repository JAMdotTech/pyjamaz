from scalecodec.types import Struct, U16, H256, H512, Bool


class ExtrinsicAssurance(Struct):
    #GP-equation: 116-120 | "ASSURANCE"->"(WORK_REPORT_HASH,IS_AVAILABLE,VALIDATOR_IDX,SIGNATURE)" | "WORK_REPORT_HASH"->"H256" | "IS_AVAILABLE"->"BOOL" | "VALIDATOR_IDX"->"U16" | "SIGNATURE"->"H512"
    arguments = {
        'work_report_hash': H256,
        'is_available': Bool,
        'validator_idx': U16,
        'signature': H512
    }

