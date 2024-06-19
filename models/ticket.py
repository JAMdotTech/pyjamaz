from scalecodec.types import Struct, H256, U8


class Ticket(Struct):
    #GP-reference: C | SCALETYPE-DEFINITION: "TICKET"->"(TICKET_ID,ENTRY_IDX)" | "TICKET_ID"->"H256" | "ENTRY_IDX"->"U8"
    #GP-equation: 49,70
    arguments = {
        'ticket_id': H256,
        'entry_idx': U8
    }

