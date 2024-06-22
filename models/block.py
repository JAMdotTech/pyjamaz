from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, H256, U32, Option, Vec, H512, U8, Bool, VecType, Compact, Bytes
from models.common import Ticket, WorkReport


class EpochObject(ScaleType):
    def test(self):
        pass


class Epoch(Struct):
    # GP-ref:43,69
    scale_type_cls = EpochObject
    arguments = {
        'entropy': H256, # GP-ref:ETA-1
        # TODO Constant(V): VALIDATORS=1023; size of list is exactly VALIDATORS=1023 Needs to be more strict. Possible Array(H256,1023)
        'bs_keys': Vec(H256) # GP-ref:k
    }


class HeaderObject(ScaleType):
    def test(self):
        pass
    # TODO: DEFINE FUNCTION THAT SERIALIZES HEADER(DATA)
    # TODO: DEFINE FUNCTION THAT UNSERIALIZES HEADER(DATA)
    # TODO: GP-ref:37: DEFINE FUNCTION THAT HASHES HEADER(DATA)


class Header(Struct):
    # GP-ref:36
    scale_type_cls = HeaderObject
    arguments = {
        'parent_hash': H256, # GP-ref:37
        'prior_state_root': H256, # GP-ref:41
        'extrinsic_hash': H256, # GP-ref:39
        'timeslot': U32, # GP-ref:40
        # TODO: only in first old_block of new epoch
        'epoch': Option(Epoch()), # GP-ref:43,69
        # TODO: only in first old_block after submission period for tickets and ticket accumulator is saturated
        'winning_tickets': Option(Vec(Ticket())), # GP-ref:70,49
        # TODO: Complicated, needs research
        'judgements': Vec(H256), # GP-ref:101-108
        # TODO: Type author_key_idx implicit, but derived from Hk in GP-ref:272
        'author_key_idx': U32, # GP-ref:42
        'vrf_signature': H512, # GP-ref:59
        'block_seal': H512 # GP-ref:59
    }


class ExtrinsicTicketObject(ScaleType):
    def test(self):
        pass


class ExtrinsicTicket(Struct):
    # GP-ref:71
    scale_type_cls = ExtrinsicTicketObject
    arguments = {
        # TODO Constant(N): TICKET_ENTRIES=2; entry_idx=0|1 Needs to be more strict
        'entry_idx': U8, # GP-ref:71,r
        'validity_proof': H512 # GP-ref:71,p
    }


class JudgementVoteObject(ScaleType):
    def test(self):
        pass


class JudgementVote(Struct):
    # GP-ref:96,97
    scale_type_cls = JudgementVoteObject
    arguments = {
        'is_valid': Bool, # GP-ref:X
        # TODO: Type implicit, but derived from Hk in GP-equation 272
        'validator_idx': U32, # GP-ref:Nv
        'signature': H512 # GP-ref:-
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

    # TODO: ENCODE VALIDATION SIMILAR TO DECODE VALIDATION
    # def endecode(self, data: ScaleBytes) -> list:


class ExtrinsicJudgementObject(ScaleType):
    def test(self):
        pass


class ExtrinsicJudgement(Struct):
    # GP-ref:96,98,Ej,J
    scale_type_cls = ExtrinsicJudgementObject
    arguments = {
        'work_report_hash': H256, # GP-ref:96,99,H
        # TODO: Constant(V): VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683 Needs to be more strict. Possible Array(JudgementVote(),683); Round()|Floor()?
        # TODO: proof-of-concept in class JudgementVotes()
        'votes': JudgementVotes() # GP-ref:96,97
    }


class ExtrinsicPreimageObject(ScaleType):
    def test(self):
        pass


class ExtrinsicPreimage(Struct):
    # GP-ref:148,Ep
    scale_type_cls = ExtrinsicPreimageObject
    arguments = {
        'service_idx': U32, # GP-reference:148,Ns
        # TODO: verify assumption that BLOB is encoded as Bytes (variable length)
        'data': Bytes # GP-ref:148,Y
    }


class ExtrinsicAssuranceObject(ScaleType):
    def test(self):
        pass


class ExtrinsicAssurance(Struct):
    # GP-ref:116-120,Ea
    scale_type_cls = ExtrinsicAssuranceObject
    arguments = {
        'work_report_hash': H256, # GP-ref:116-120,a
        'is_available': Bool, # GP-ref:116-120,f
        # TODO: validator_idx type implicit, but derived from Hk in GP-equation 272
        'validator_idx': U32, # GP-ref:116-120,v
        'signature': H512 # GP-ref:116-120,s
    }


class ExtrinsicGuaranteeObject(ScaleType):
    def test(self):
        pass


class ExtrinsicGuarantee(Struct):
    # GP-ref:130,Eg
    scale_type_cls = ExtrinsicGuaranteeObject
    arguments = {
        # TODO: core_idx type implicit, but treated similar to validator_idx as derived from Hk in GP-ref:272
        'core_idx': U32, # GP-ref:130,c
        'work_report': WorkReport(), # GP-ref:130,110,W
        'timeslot': U32, # GP-ref:130,t
        # TODO: FixedValue (not a constant): 3 (assume core-size; validators/authorizer); Only 3rd value allowed None; Needs to be more strict;
        'credential': Vec(Option(H512)) # GP-ref:130,a
    }


class ExtrinsicObject(ScaleType):
    def test(self):
        pass
    # TODO: DEFINE FUNCTION THAT SERIALIZES EXTRINSIC(DATA)
    # TODO: DEFINE FUNCTION THAT UNSERIALIZES EXTRINSIC(DATA)
    # TODO: GP-ref:39: DEFINE FUNCTION THAT HASHES EXTRINSIC(DATA)

class Extrinsic(Struct):
    # GP-ref:14
    scale_type_cls = ExtrinsicObject
    arguments = {
        # TODO: Constant(K): MAXIMUM_EXTRINSIC_TICKETS=16; Needs to be more strict; How to solve?
        'tickets': Vec(ExtrinsicTicket()), # GP-ref:71
        'judgements': Vec(ExtrinsicJudgement()), # GP-ref:96
        'preimages': Vec(ExtrinsicPreimage()), # GP-ref:148
        'assurances': Vec(ExtrinsicAssurance()), # GP-ref:116-120
        'guarantees': Vec(ExtrinsicGuarantee()) # GP-ref:130
    }


class BlockObject(ScaleType):
    def test(self):
        pass
    # TODO: DEFINE FUNCTION THAT SERIALIZES BLOCK(DATA)
    # TODO: DEFINE FUNCTION THAT UNSERIALIZES BLOCK(DATA)
    # TODO: GP-ref:??: DEFINE FUNCTION THAT HASHES BLOCK(DATA)


class Block(Struct):
    # GP-ref:13
    scale_type_cls = BlockObject
    arguments = {
        'header': Header(),
        'extrinsic': Extrinsic(),
    }

