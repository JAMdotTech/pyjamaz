from scalecodec.base import ScaleType
from scalecodec.types import Struct, Tuple, Vec, Option, U8, U16, U32, H256, H512
#from models.ticket import Ticket


#TODO: ARJAN UITLEGGEN WAT DIT BETEKENT. SNAP IK NIET.
#class HeaderType(ScaleType):
#    def test(self):
#        print('ja')

class Header(Struct):
    #GP-equation: 37 | SCALETYPE-DEFINITION: "PARENT_HASH"->"H256"
    #GP-equation: 41 | SCALETYPE-DEFINITION: "PRIOR_STATE_ROOT"->"H256"
    #GP-equation: 39 | SCALETYPE-DEFINITION: "EXTRINSIC_HASH"->"H256"
    #GP-equation: 40 | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-equation: 43,69 | SCALETYPE-DEFINITION: "EPOCH"->"OPTION<(ENTROPY,BS_KEYS)>" | "ENTROPY"->"H256" | "BS_KEYS"->"VEC<BS_KEY>" | "BS_KEY"->"H256"
    #GP-equation: 70,49 | SCALETYPE-DEFINITION: "WINNING_TICKETS_MARKER"->"OPTION<WINNING_TICKETS>" | "WINNING_TICKETS"->"VEC<WINNING_TICKET>" | "WINNING_TICKET"->"(TICKET_HASH,ENTRY_IDX)" | "TICKET_HASH"->"H256" | "ENTRY_IDX"->"U8"
    #GP-equation: 101-108 | SCALETYPE-DEFINITION: "JUDGEMENT_MARKER"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    #GP-equation: 42 | SCALETYPE-DEFINITION: "AUTHOR_KEY_IDX"->"U16"
    #GP-equation: 59 | SCALETYPE-DEFINITION: "VRF_SIGNATURE"->"H512"
    #GP-equation: 59? | SCALETYPE-DEFINITION: "BLOCK_SEAL"->"H512"

    #TODO: ARJAN UITLEGGEN WAT DIT BETEKENT. SNAP IK NIET.
    arguments = {
        'parent_hash': H256,
        'prior_state_root': H256,
        'extrinsic_hash': H256,
        'timeslot': U32,
        'epoch': Option(Tuple(H256, H256, Vec(H256))),
        'winning_tickets': Option(Vec(Tuple(H256,U8))),
        #'winning_tickets': Option(Vec(Ticket())), (TODO vereenvouding model)
        'judgements': Vec(H256),
        'author_key_idx': U16,
        'vrf_signature': H512,
        'block_seal': H512
    }

    #GP-equation: 36 | SCALETYPE-DEFINITION: "HEADER"->"(PARENT_HASH,PRIOR_STATE_ROOT,EXTRINSIC_HASH,TIMESLOT,EPOCH,WINNING_TICKETS,JUDGEMENTS_MARKER,AUTHOR_KEY_IDX,VRF_SIGNATURE,BLOCK_SEAL)"
    #DEFINE FUNCTION THAT SERIALIZES HEADER(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES HEADER(DATA)

    #GP-equation: 37
    #DEFINE FUNCTION THAT HASHES HEADER(DATA)

