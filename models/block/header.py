from scalecodec.types import Struct, Vec, Option, U16, U32, H256, H512
from models.other.ticket import Ticket
from models.other.epoch import Epoch


#TODO: ARJAN EXPLAIN, REMOVE?
#class HeaderType(ScaleType):
#    def test(self):
#        print('ja')

class Header(Struct):
    #GP-equation: 37 | SCALETYPE-DEFINITION: "PARENT_HASH"->"H256"
    #GP-equation: 41 | SCALETYPE-DEFINITION: "PRIOR_STATE_ROOT"->"H256"
    #GP-equation: 39 | SCALETYPE-DEFINITION: "EXTRINSIC_HASH"->"H256"
    #GP-equation: 40 | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-equation: 43,69 | SCALETYPE-DEFINITION: "EPOCH"-> refer to class Epoch for details.
    #GP-equation: 70,49 | SCALETYPE-DEFINITION: "WINNING_TICKETS"-> refer to class WinningTickets for details.
    #GP-equation: 101-108 | SCALETYPE-DEFINITION: "JUDGEMENT_MARKER"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    #GP-equation: 42 | SCALETYPE-DEFINITION: "AUTHOR_KEY_IDX"->"U16"
    #GP-equation: 59 | SCALETYPE-DEFINITION: "VRF_SIGNATURE"->"H512"
    #GP-equation: 59? | SCALETYPE-DEFINITION: "BLOCK_SEAL"->"H512"

    arguments = {
        'parent_hash': H256,
        'prior_state_root': H256,
        'extrinsic_hash': H256,
        'timeslot': U32,
        'epoch': Option(Epoch()),
        'winning_tickets': Option(Vec(Ticket())),
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

