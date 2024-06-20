from scalecodec.types import Struct, U32, Bytes


class ExtrinsicPreimage(Struct):
    #GP-equation: 148,Ep | SCALETYPE-DEFINITION: "PREIMAGE"->"(SERVICE_IDX,DATA)"
    #GP-reference: 148,Ns | SCALETYPE-DEFINITION: "SERVICE_IDX"->"U32"
    #GP-reference: 148,Y | SCALETYPE-DEFINITION: "DATA"->"BYTES"
    arguments = {
        'service_idx': U32,
        'data': Bytes
    }

