from scalecodec.types import Struct, U32, H256, I64, Bytes, Bool, Enum


class WorkResult(Struct):
    #GP-equation: 114,115 | "RESULT"->"(SERVICE_IDX,CODE_HASH,PAYLOAD_HASH,GAS_PRIORITIZATION_RATIO,RESULT)" | "SERVICE_IDX"->"U32" | "CODE_HASH"->"H256" | "PAYLOAD_HASH"->"H256" | "GAS_PRIORITIZATION_RATIO"->"I64" | "RESULT"->"ENUM<OUTPUT,OUT-OF-GAS,PANIC,BAD,BIG>" | "OUTPUT"->"BYTES" | "OUT-OF-GAS"->"BOOL" | "PANIC"->"BOOL" | "BAD"->"BOOL" | "BIG"->"BOOL"
    arguments = {
        'service_idx': U32,
        'code_hash': H256,
        'payload_hash': H256,
        'gas_prioritization_ratio': I64,
        'result': Enum(output=Bytes,out_of_gas=Bool,panic=Bool,bad=Bool,big=Bool)
    }

