from scalecodec.types import Struct, U32, Bytes


class ExtrinsicPreimage(Struct):
    #GP-equation: 148 | SCALETYPE-DEFINITION: "PREIMAGE"->"(SERVICE_IDX,DATA)" | "SERVICE_IDX"->"U32" | "DATA"->"BLOB?"
    arguments = {
        'service_idx': U32,
        'data': Bytes
    }

