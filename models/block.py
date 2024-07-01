from graypaper_constants import VALIDATOR_COUNT,MAXIMUM_EXTRINSIC_TICKETS
from scalecodec.base import ScaleType, ScaleBytes
from scalecodec.types import Struct, H256, U32, Option, Vec, H512, U8, Bool, VecType, Compact, Bytes

from models.common import Ticket, WorkReport


class BsKeys(Vec):
    def __init__(self):
        super().__init__(self)
        self.scale_type_cls = VecType
        self.type_def = H256

    def decode(self, data: ScaleBytes) -> list:
        # Decode length of Vec
        length = Compact().decode(data)
        # TODO: Check with Arjan: VALIDATOR_COUNT=1023; size of list is exactly 1023
        # TODO: Round()|Floor()?
        length_constraint = VALIDATOR_COUNT # GP-ref:43,69,k
        if length != length_constraint:
            # TODO: How to deal with error messages?
            raise ValueError('size of BsKeys list should be: {length_constraint}')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

    # TODO: ENCODE VALIDATION SIMILAR TO DECODE VALIDATION
    # def encode(self, data: ScaleBytes) -> list:

    # TODO: VALIDATE FUNCTION
    # def validate (self, data: ScaleBytes) -> list:


class EpochObject(ScaleType):
    def test(self):
        pass


class Epoch(Struct):
    # GP-ref:43,69
    scale_type_cls = EpochObject
    arguments = {
        'entropy': H256, # GP-ref:ETA-1
        'bs_keys': BsKeys() # GP-ref:k; Additional type-constraints apply
        #'bs_keys': Vec(H256)  # GP-ref:k
    }


class HeaderObject(ScaleType):
    """
    Creates a new `Header` object.
    GP-ref: 36
    """
    def serialize(self) -> bytes:
        """
        GP-ref: 36,271,272 SCALE-encodes / serializes Header

        :param self:
        :return: SCALE-encoded / serialized Header
        """
        # timeslot = U32.new()
        # scale_bytes = timeslot.encode(self.value['timeslot'])
        # return scale_bytes.data
        pass

    def deserialize(self, data: bytes):
        """
        GP-ref: 36,271,272 SCALE-decodes / deserializes Header

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized Header
        """
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot
        pass

    def hash(self, data: bytes):
        """
        GP-ref: 37 Blake2b Hash Header

        :param self:
        :param data:
        :return: Blake2b Hash Header
        """
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot
        pass


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
        'author_key_idx': U32, # GP-ref:42; type derived from Hk in GP-ref:272
        'vrf_signature': H512, # GP-ref:59
        'block_seal': H512 # GP-ref:59
    }


class ExtrinsicTickets(Vec):
    def __init__(self):
        super().__init__(self)
        self.scale_type_cls = VecType
        self.type_def = ExtrinsicTicket()

    def decode(self, data: ScaleBytes) -> list:
        # Decode length of Vec
        length = Compact().decode(data)
        # TODO: Check with Arjan: MAXIMUM_EXTRINSIC_TICKETS=8; size of list is between 0 and 8
        # TODO: Round()|Floor()?
        length_constraint = MAXIMUM_EXTRINSIC_TICKETS # GP-ref:71
        if length > length_constraint:
            # TODO: How to deal with error messages?
            raise ValueError('size of ExtrinsicTickets list should be not greater than: {length_constraint}')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

    # TODO: ENCODE VALIDATION SIMILAR TO DECODE VALIDATION
    # def encode(self, data: ScaleBytes) -> list:

    # TODO: VALIDATE FUNCTION
    # def validate (self, data: ScaleBytes) -> list:


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
        'is_valid': Bool, # GP-ref:96,97
        'validator_idx': U32, # GP-ref:Nv; type derived from Hk in GP-ref:272
        # TODO: all signatures must be valid in terms of one of the two validator key-sets. Key-sets may not be mixed. Solve in JudgementVotes
        'signature': H512 # GP-ref:96
    }


class JudgementVotes(Vec):
    def __init__(self):
        super().__init__(self)
        self.scale_type_cls = VecType
        self.type_def = JudgementVote()

    def decode(self, data: ScaleBytes) -> list:
        # Decode length of Vec
        length = Compact().decode(data)
        # TODO: Check with Arjan: VALIDATORS=1023; size of list is exactly (2*VALIDATORS)/3+1=683
        # TODO: Round()|Floor()?
        length_constraint = ((2*VALIDATOR_COUNT)/3)+1 # GP-ref:96
        if length != length_constraint:
            # TODO: How to deal with error messages?
            raise ValueError('size of JudgementVotes list should be: {length_constraint}')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

    # TODO: ENCODE VALIDATION SIMILAR TO DECODE VALIDATION
    # def encode(self, data: ScaleBytes) -> list:

    # TODO: VALIDATE FUNCTION
    # def validate (self, data: ScaleBytes) -> list:


class ExtrinsicJudgementObject(ScaleType):
    def test(self):
        pass


class ExtrinsicJudgement(Struct):
    # GP-ref:96,98,Ej,J
    scale_type_cls = ExtrinsicJudgementObject
    arguments = {
        'work_report_hash': H256, # GP-ref:96,99,H
        'votes': JudgementVotes() # GP-ref:96,97; Additional type-constraints apply
    }


class ExtrinsicPreimageObject(ScaleType):
    def test(self):
        pass


class ExtrinsicPreimage(Struct):
    # GP-ref:148,Ep
    scale_type_cls = ExtrinsicPreimageObject
    arguments = {
        'service_idx': U32, # GP-reference:148,Ns
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
        'validator_idx': U32, # GP-ref:116-120,v; type derived from Hk in GP-ref:272
        'signature': H512 # GP-ref:116-120,s
    }


class CredentialObject(ScaleType):
    def test(self):
        pass


class Credential(Struct):
    # GP-ref:130,Eg
    scale_type_cls = CredentialObject
    arguments = {
        'signature': H512, # GP-ref:130,a,132,133
        'validator_idx': U32, # GP-ref:130,a,132,133; type derived from Hk in GP-ref:272
    }


class Credentials(Vec):
    def __init__(self):
        super().__init__(self)
        self.scale_type_cls = VecType
        self.type_def = Credential()

    def decode(self, data: ScaleBytes) -> list:
        # Decode length of Vec
        length = Compact().decode(data)
        # TODO: Check with Arjan: fixed value=3; size of list is >= 2 (2 or 3) (NO CONSTANT FOR THIS!!)
        length_constraint = 2 # GP-ref:130,131,132,133
        if length >= length_constraint:
            # TODO: How to deal with error messages?
            raise ValueError('size of Credentials list should be greater or equal to: {length_constraint}')
        value = []

        for _ in range(0, length):
            obj = self.type_def.new()
            obj.decode(data)

            value.append(obj)

        return value

    # TODO: ENCODE VALIDATION SIMILAR TO DECODE VALIDATION
    # def encode(self, data: ScaleBytes) -> list:

    # TODO: VALIDATE FUNCTION
    # def validate (self, data: ScaleBytes) -> list:


class ExtrinsicGuaranteeObject(ScaleType):
    def test(self):
        pass


class ExtrinsicGuarantee(Struct):
    # GP-ref:130,Eg
    scale_type_cls = ExtrinsicGuaranteeObject
    arguments = {
        'core_idx': U32, # GP-ref:130,c; type similar to validator_idx, thus derived from Hk in GP-ref:272
        'work_report': WorkReport(), # GP-ref:130,110,W
        'timeslot': U32, # GP-ref:130,t
        'credential': Credentials()  # GP-ref:130,a,132,133; Additional type-constraints apply
        # 'credential': Vec(Credential())  # GP-ref:130,a,132,133
        # 'credential': Vec(Tuple(H512,U32))  # GP-ref:130,a,132,133
    }


class ExtrinsicObject(ScaleType):
    """
    Creates a new `Extrinsic` object.
    GP-ref: 14
    """
    def serialize(self) -> bytes:
        """
        GP-ref: 14,270 SCALE-encodes / serializes Extrinsic

        :param self:
        :return: SCALE-encoded / serialized Extrinsic
        """
        # timeslot = U32.new()
        # scale_bytes = timeslot.encode(self.value['timeslot'])
        # return scale_bytes.data
        pass

    def deserialize(self, data: bytes):
        """
        GP-ref: 14,270 SCALE-decodes / deserializes Extrinsic

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized Extrinsic
        """
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot
        pass

    def hash(self, data: bytes):
        """
        GP-ref: 39 Blake2b Hash Extrinsic

        :param self:
        :param data:
        :return: Blake2b Hash Extrinsic
        """
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot
        pass


class Extrinsic(Struct):
    # GP-ref:14
    scale_type_cls = ExtrinsicObject
    arguments = {
        'tickets': ExtrinsicTickets(), # GP-ref:71; Additional type-constraints apply
        # 'tickets': Vec(ExtrinsicTicket()), # GP-ref:71
        'judgements': Vec(ExtrinsicJudgement()), # GP-ref:96
        'preimages': Vec(ExtrinsicPreimage()), # GP-ref:148
        'assurances': Vec(ExtrinsicAssurance()), # GP-ref:116-120
        'guarantees': Vec(ExtrinsicGuarantee()) # GP-ref:130
    }


class BlockObject(ScaleType):
    """
    Creates a new `Block` object.
    GP-ref: 13
    """
    def serialize(self) -> bytes:
        """
        GP-ref: 13,270 SCALE-encodes / serializes Block

        :param self:
        :return: SCALE-encoded / serialized Block
        """
        # timeslot = U32.new()
        # scale_bytes = timeslot.encode(self.value['timeslot'])
        # return scale_bytes.data
        pass

    def deserialize(self, data: bytes):
        """
        GP-ref: 13,270 SCALE-decodes / deserializes Block

        :param self:
        :param data:
        :return: SCALE-decoded / deserialized Block
        """
        # timeslot = U32.new().decode(ScaleBytes(data))
        # self.value['timeslot'] = timeslot
        pass


class Block(Struct):
    # GP-ref:13
    scale_type_cls = BlockObject
    arguments = {
        'header': Header(),
        'extrinsic': Extrinsic(),
    }

