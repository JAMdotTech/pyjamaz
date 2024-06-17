from scalecodec.types import Struct, Vec, U8, U32


class ExtrinsicPreimage(Struct):
    #GP-equation: 148 | SCALETYPE-DEFINITION: "PREIMAGE"->"(SERVICE_IDX,DATA)" | "SERVICE_IDX"->"U32" | "DATA"->"BLOB?"
    arguments = {
        'service_idx': U32,
        'data': Vec(U8)
    }

