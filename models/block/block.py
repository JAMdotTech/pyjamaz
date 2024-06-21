from scalecodec.base import ScaleType
from scalecodec.types import Struct, H256, U32, Option, Vec, H512
from models.block.extrinsic import Extrinsic
from models.other.epoch import Epoch
from models.other.ticket import Ticket


class HeaderObject(ScaleType):
    def test(self):
        print('ja')


class Header(Struct):
    #GP-equation: 37 | SCALETYPE-DEFINITION: "PARENT_HASH"->"H256"
    #GP-equation: 41 | SCALETYPE-DEFINITION: "PRIOR_STATE_ROOT"->"H256"
    #GP-equation: 39 | SCALETYPE-DEFINITION: "EXTRINSIC_HASH"->"H256"
    #GP-equation: 40 | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-equation: 43,69 | SCALETYPE-DEFINITION: "EPOCH"-> refer to class Epoch for details.
    #GP-equation: 70,49 | SCALETYPE-DEFINITION: "WINNING_TICKETS"-> refer to class WinningTickets for details.
    #GP-equation: 101-108 | SCALETYPE-DEFINITION: "JUDGEMENT_MARKER"->"VEC<WORK_REPORT_HASH>" | "WORK_REPORT_HASH"->"H256"
    #GP-equation: 42 | SCALETYPE-DEFINITION: "AUTHOR_KEY_IDX"->"U32" #Type implicit, but derived from Hk in GP-equation 272
    #GP-equation: 59 | SCALETYPE-DEFINITION: "VRF_SIGNATURE"->"H512"
    #GP-equation: 59 | SCALETYPE-DEFINITION: "BLOCK_SEAL"->"H512"

    scale_type_cls = HeaderObject
    arguments = {
        'parent_hash': H256,
        'prior_state_root': H256,
        'extrinsic_hash': H256,
        'timeslot': U32,
        'epoch': Option(Epoch()), #TODO: only in first block of new epoch
        'winning_tickets': Option(Vec(Ticket())), #TODO: only in first block after submission period for tickets and ticket accumulator is saturated
        'judgements': Vec(H256), #TODO: Complicated, needs research
        'author_key_idx': U32, #TODO: Type implicit, but derived from Hk in GP-equation 272
        'vrf_signature': H512,
        'block_seal': H512
    }

    #GP-equation: 36 | SCALETYPE-DEFINITION: "HEADER"->"(PARENT_HASH,PRIOR_STATE_ROOT,EXTRINSIC_HASH,TIMESLOT,EPOCH,WINNING_TICKETS,JUDGEMENTS_MARKER,AUTHOR_KEY_IDX,VRF_SIGNATURE,BLOCK_SEAL)"
    #DEFINE FUNCTION THAT SERIALIZES HEADER(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES HEADER(DATA)

    #GP-equation: 37
    #DEFINE FUNCTION THAT HASHES HEADER(DATA)

class BlockObject(ScaleType):
    def test(self):
        print('ja')

class Block(Struct):
    #GP-equation: 13
    scale_type_cls = BlockObject
    arguments = {
        'header': Header(),
        'extrinsic': Extrinsic(),
    }

    #GP-equation: 14 | SCALETYPE-DEFINITION: "BLOCK"->"(HEADER,EXTRINSIC)"
    #DEFINE FUNCTION THAT SERIALIZES BLOCK(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES BLOCK(DATA)

