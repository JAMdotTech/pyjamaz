from scalecodec.types import Struct, U32, H256, I64, Bytes, Bool


class WorkResult(Struct):
    #GP-equation: 114,115 | "RESULT"->"(SERVICE_IDX,CODE_HASH,PAYLOAD_HASH,GAS_PRIORIZATION_RATIO,RESULT)" | "SERVICE_IDX"->"U32" | "CODE_HASH"->"H256" | "PAYLOAD_HASH"->"H256" | "GAS_PRIORIZATION_RATIO"->"I64" | "RESULT"->"ENUM<OUTPUT,ENUM<OUT-OF-GAS,UNEXPECTED-TERMINATION,BAD,BIG>>" | "OUTPUT"->"BYTES"
    #TODO Implement ENUM 'RESULT': Enum(OUTPUT,ERROR) | 'OUTPUT': BYTES | 'ERROR': Enum(ERROR1,ERROR2,ERROR3,ERROR4)
    arguments = {
        'service_idx': U32,
        'code_hash': H256,
        'payload_hash': H256,
        'gas_priorization_ratio': I64,
        #'result': Enum(Bytes,Enum(1,2,3,4))
        'result': Enum(Bytes, Bool)
    }

