from scalecodec.types import Struct, U8, H512


class ExtrinsicTicket(Struct):
    #GP-equation: 71 | SCALETYPE-DEFINITION: "TICKET"->"(ENTRY_IDX,VALIDITY_PROOF)" | "ENTRY_IDX"->"U8" | "VALIDITY_PROOF"->"H512"
    arguments = {
        'entry_idx': U8,
        'validity_proof': H512
    }

