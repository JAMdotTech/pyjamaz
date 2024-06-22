from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, H256, U32, Option, Vec, H512, U8, Bool, VecType, Compact, Bytes
from models.common import Ticket, WorkReport


class EpochObject(ScaleType):
    def test(self):
        print('ja')


class Epoch(Struct):
    #GP-equation: 43,69 | SCALETYPE-DEFINITION: "EPOCH"->"OPTION<(ENTROPY,BS_KEYS)>"
    #GP-reference: ETA-1 | SCALETYPE-DEFINITION: "ENTROPY"->"H256"
    #GP-reference: k | SCALETYPE-DEFINITION: "BS_KEYS"->"VEC<BS_KEY>" | "BS_KEY"->"H256"
    scale_type_cls = EpochObject
    arguments = {
        'entropy': H256,
        'bs_keys': Vec(H256) #TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(H256,1023)
    }


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
        'epoch': Option(Epoch()), #TODO: only in first old_block of new epoch
        'winning_tickets': Option(Vec(Ticket())), #TODO: only in first old_block after submission period for tickets and ticket accumulator is saturated
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


class ExtrinsicTicketObject(ScaleType):
    def test(self):
        print('ja')


class ExtrinsicTicket(Struct):
    #GP-equation: 71 | SCALETYPE-DEFINITION: "TICKET"->"(ENTRY_IDX,VALIDITY_PROOF)"
    #GP-reference: 71,r | SCALETYPE-DEFINITION: "ENTRY_IDX"->"U8"
    #GP-reference: 71,p | SCALETYPE-DEFINITION: "VALIDITY_PROOF"->"H512"
    scale_type_cls = ExtrinsicTicketObject
    arguments = {
        'entry_idx': U8, #TODO Constant(N): TICKET_ENTRIES=2; entry_idx=0|1 Needs to be more strict
        'validity_proof': H512
    }


class JudgementVoteObject(ScaleType):
    def test(self):
        print('ja')


class JudgementVote(Struct):
    #GP-equation: 96,97 | SCALETYPE-DEFINITION: "VOTE"->"(IS_VALID,VALIDATOR_IDX,SIGNATURE)" |
    #GP-reference: X | SCALETYPE-DEFINITION: "IS_VALID"->"BOOL"
    #GP-reference: Nv | SCALETYPE-DEFINITION: "VALIDATOR_IDX"->"U32" #TODO: Type implicit, but derived from Hk in GP-equation 272
    #GP-reference: - | SCALETYPE-DEFINITION: "SIGNATURE"->"H512"
    scale_type_cls = JudgementVoteObject
    arguments = {
        'is_valid': Bool,
        'validator_idx': U32, #TODO: Type implicit, but derived from Hk in GP-equation 272
        'signature': H512
    }


class JudgementVotes(Vec):
    #In deze class kunnen we data validatie afdwingen van een standaard vec
    #TODO Constant(V): VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683 Needs to be more strict. Possible Array(JudgementVote(),683); Round()|Floor()?
    def __init__(self):
        super().__init__()
        self.scale_type_cls = VecType
        self.type_def = JudgementVote()

    def decode(self, data: ScaleBytes) -> list:
        # deze functie dwingt validatie af

        # Decode length of Vec
        length = Compact().decode(data)
        if length != 683: # vervangen door constant
            raise ValueError('size of list should be 683')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

    # def endecode(self, data: ScaleBytes) -> list: # TODO ENCODE VALIDATION


class ExtrinsicJudgementObject(ScaleType):
    def test(self):
        print('ja')


class ExtrinsicJudgement(Struct):
    #GP-equation: 96,98,Ej,J | SCALETYPE-DEFINITION: "JUDGEMENT"->"(WORK_REPORT_HASH,VOTES)"
    #GP-reference: 96,99,H | SCALETYPE-DEFINITION: "WORK_REPORT_HASH"->"H256"
    #GP-reference: 96,97 | SCALETYPE-DEFINITION: "VOTES"->"VEC<VOTE>" | "VOTE"-> refer to class JudgementVote for details.
    scale_type_cls = ExtrinsicJudgementObject
    arguments = {
        'work_report_hash': H256,
        'votes': JudgementVotes() #TODO Constant(V): VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683 Needs to be more strict. Possible Array(JudgementVote(),683); Round()|Floor()?
    }


class ExtrinsicPreimageObject(ScaleType):
    def test(self):
        print('ja')


class ExtrinsicPreimage(Struct):
    #GP-equation: 148,Ep | SCALETYPE-DEFINITION: "PREIMAGE"->"(SERVICE_IDX,DATA)"
    #GP-reference: 148,Ns | SCALETYPE-DEFINITION: "SERVICE_IDX"->"U32"
    #GP-reference: 148,Y | SCALETYPE-DEFINITION: "DATA"->"BYTES"
    scale_type_cls = ExtrinsicPreimageObject
    arguments = {
        'service_idx': U32,
        'data': Bytes #TODO: verify assumption that BLOB is encoded as Bytes (variable length)
    }


class ExtrinsicAssuranceObject(ScaleType):
    def test(self):
        print('ja')


class ExtrinsicAssurance(Struct):
    #GP-equation: 116-120,Ea | SCALETYPE-DEFINITION: "ASSURANCE"->"(WORK_REPORT_HASH,IS_AVAILABLE,VALIDATOR_IDX,SIGNATURE)"
    #GP-reference: 116-120,a | SCALETYPE-DEFINITION: "WORK_REPORT_HASH"->"H256"
    #GP-reference: 116-120,f | SCALETYPE-DEFINITION: "IS_AVAILABLE"->"BOOL"
    #GP-reference: 116-120,v | SCALETYPE-DEFINITION: "VALIDATOR_IDX"->"U16"
    #GP-reference: 116-120,s | SCALETYPE-DEFINITION: "SIGNATURE"->"H512"
    scale_type_cls = ExtrinsicAssuranceObject
    arguments = {
        'work_report_hash': H256,
        'is_available': Bool,
        'validator_idx': U32, #TODO: Type implicit, but derived from Hk in GP-equation 272
        'signature': H512
    }


class ExtrinsicGuaranteeObject(ScaleType):
    def test(self):
        print('ja')


class ExtrinsicGuarantee(Struct):
    #GP-equation: 130,Eg | SCALETYPE-DEFINITION: "GUARANTEE"->"(CORE_IDX,WORK_REPORT,TIMESLOT,CREDENTIAL)"
    #GP-reference: 130,c | SCALETYPE-DEFINITION: "CORE_IDX"->"U32" #Type implicit, but treated similar to validator_idx as derived from Hk in GP-equation 272
    #GP-reference: 130,110,W | SCALETYPE-DEFINITION: "WORK_REPORT"-> refer to class WorkReport for details.
    #GP-reference: 130,t | SCALETYPE-DEFINITION: "TIMESLOT"->"U32"
    #GP-reference: 130,a | SCALETYPE-DEFINITION: "CREDENTIAL"->"VEC<OPTION<SIGNATURE>> | "SIGNATURE"->"H512"
    scale_type_cls = ExtrinsicGuaranteeObject
    arguments = {
        'core_idx': U32, #TODO: Type implicit, but treated similar to validator_idx as derived from Hk in GP-equation 272
        'work_report': WorkReport(),
        'timeslot': U32,
        'credential': Vec(Option(H512)) #TODO FixedValue (not a constant): 3 (assume core-size; validators/authorizer); Only 3rd value allowed None; Needs to be more strict
    }


class ExtrinsicObject(ScaleType):
    def test(self):
        print('ja')


class Extrinsic(Struct):
    #GP-equation: 71 | SCALETYPE-DEFINITION: "TICKETS"->"VEC<TICKET>" | refer to class ExtrinsicTicket for details.
    #GP-equation: 96 | SCALETYPE-DEFINITION: "JUDGEMENTS"->"VEC<JUDGEMENT>" | refer to class ExtrinsicJudgement for details.
    #GP-equation: 148 | SCALETYPE-DEFINITION: "PREIMAGES"->"VEC<PREIMAGE>" | refer to class ExtrinsicPreimage for details.
    #GP-equation: 116-120 | SCALETYPE-DEFINITION: "ASSURANCES"->"VEC<ASSURANCE>" | refer to class ExtrinsicAssurance for details.
    #GP-equation: 130 | SCALETYPE-DEFINITION: "GUARANTEES"->"VEC<GUARANTEE>" | refer to class ExtrinsicGuarantee for details.
    scale_type_cls = ExtrinsicObject
    arguments = {
        'tickets': Vec(ExtrinsicTicket()), #TODO Constant(K): MAXIMUM_EXTRINSIC_TICKETS=16; Needs to be more strict; How to solve?
        'judgements': Vec(ExtrinsicJudgement()),
        'preimages': Vec(ExtrinsicPreimage()),
        'assurances': Vec(ExtrinsicAssurance()),
        'guarantees': Vec(ExtrinsicGuarantee())
    }

    #GP-equation: 14 | SCALETYPE-DEFINITION: "EXTRINSIC"->"(TICKETS,JUDGEMENTS,PREIMAGES,ASSURANCES,GUARANTEES)"
    #DEFINE FUNCTION THAT SERIALIZES EXTRINSIC(DATA)
    #DEFINE FUNCTION THAT UNSERIALIZES EXTRINSIC(DATA)

    #GP-equation: 39
    #DEFINE FUNCTION THAT HASHES EXTRINSIC(DATA)


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

