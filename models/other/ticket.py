from scalecodec.types import Struct, H256, U8


class Ticket(Struct):
    #GP-equation: 49,C | SCALETYPE-DEFINITION: "TICKET"->"(TICKET_ID,ENTRY_IDX)"
    #GP-reference: Y | SCALETYPE-DEFINITION: "TICKET_ID"->"H256"
    #GP-reference: r | SCALETYPE-DEFINITION: "ENTRY_IDX"->"U8"
    arguments = {
        'ticket_id': H256,
        'entry_idx': U8
    }

