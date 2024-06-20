from scalecodec.types import Struct, U8, H512


class ExtrinsicTicket(Struct):
    #GP-equation: 71 | SCALETYPE-DEFINITION: "TICKET"->"(ENTRY_IDX,VALIDITY_PROOF)"
    #GP-reference: 71,r | SCALETYPE-DEFINITION: "ENTRY_IDX"->"U8"
    #GP-reference: 71,p | SCALETYPE-DEFINITION: "VALIDITY_PROOF"->"H512"
    arguments = {
        'entry_idx': U8, #TODO Constant(N): TICKET_ENTRIES=2; entry_idx=0|1 Needs to be more strict
        'validity_proof': H512
    }

