from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from jamcodec.base import JamCodecTypeDef, JamBytes, JamCodecType
from jamcodec.mixins import Serializable
from jamcodec.types import U32, H256, U8, VarInt64, Vec, Option, Array, Map, H512, VecType

from pyjamaz.models.block import Header, Guarantee, Block
from pyjamaz.models.common import WorkPackage



class ImplicitVec(Vec):

    def encode(self, value: list) -> JamBytes:
        # Encode length of Vec
        data = JamBytes(bytes())

        for idx, item in enumerate(value):
            if type(item) is JamBytes:
                data += item
            else:
                data += self.type_def.encode(item)
                if item and issubclass(item.__class__, JamCodecType):
                    value[idx] = item.serialize()

        return data

    def decode(self, data: JamBytes) -> list:
        value = []

        while True:
            obj = self.type_def.new()
            obj.decode(data)
            value.append(obj)

            if data.get_remaining_length() == 0:
                break

        return value


@dataclass
class MsgUP0Leaf(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})

@dataclass
class MsgUP0Handshake(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})
    leafs: List[MsgUP0Leaf] = field(metadata={'codec': Vec(MsgUP0Leaf.to_codec_def())})

@dataclass
class MsgUP0Announcement(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    header_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})


class MsgCE128BlockRequestDirection(Enum):
    ASC = 0
    DESC = 1

@dataclass
class MsgCE128BlockRequest(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    direction: int = field(metadata={'codec': U8})
    max_blocks: int = field(metadata={'codec': U32})

@dataclass
class MsgCE128BlockRequestResponse(Serializable):
    blocks: List[Block] = field(metadata={'codec': ImplicitVec(Block.to_codec_def())})


@dataclass
class MsgCE129KeyRangeRequest(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    key_start: bytes = field(metadata={'codec': Array(U8, 31)})
    key_end: bytes = field(metadata={'codec': Array(U8, 31)})
    max_size: int = field(metadata={'codec': U32})


@dataclass
class MsgCE131SafroleTicket(Serializable):
    attempt: int = field(metadata={'codec': U8})                # 0|1
    proof: bytes = field(metadata={'codec': Array(U8, 784)})


@dataclass
class MsgCE131SafroleTicketDistribution(Serializable):
    # Note: CE 131 & 132
    epoch_index: int = field(metadata={'codec': U32})
    ticket: MsgCE131SafroleTicket = field(metadata={'codec': MsgCE131SafroleTicket.to_codec_def()})


@dataclass
class MsgCE132SafroleTicket(MsgCE131SafroleTicket):
    pass

@dataclass
class MsgCE132SafroleTicketDistribution(MsgCE131SafroleTicketDistribution):
    pass


@dataclass
class MsgCE133WorkPackageSubmission(Serializable):
    core_index: int = field(metadata={'codec': U32})
    work_package: WorkPackage = field(metadata={'codec': WorkPackage.to_codec_def()})

@dataclass
class MsgCE133WorkPackageSubmission(Serializable):
    core_index: int = field(metadata={'codec': U32})
    work_package: WorkPackage = field(metadata={'codec': WorkPackage.to_codec_def()})

@dataclass
class MsgCE133Extrinsic(Serializable):
    bytes_: bytes = field(metadata={'codec': Vec(U8)})


@dataclass
class MsgCE134WorkPackageSharing(Serializable):
    core_index: int = field(metadata={'codec': U32})
    segment_root_map: Dict[bytes, bytes] = field(metadata={'codec': Map(H256, H256)})


@dataclass
class MsgCE134WorkPackageBundle(Serializable):
    work_package: WorkPackage = field(metadata={'codec': WorkPackage.to_codec_def()})


@dataclass
class MsgCE134RefineResponse(Serializable):
    report_hash: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class MsgCE135GuaranteedWorkReport(Guarantee):
    pass


@dataclass
class MsgCE135GuaranteedWorkReport(Guarantee):
    pass


@dataclass
class MsgCE136HashRequest(Serializable):
    hash: bytes = field(metadata={'codec': H256})


@dataclass
class MsgCE136WorkReport(Serializable):
    report: bytes = field(metadata={'codec': Vec(U8)})


@dataclass
class MsgCE141Assurance(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})   # anchor
    bitfield:    bytes = field(metadata={'codec': Vec(U8)})  # len = ceil(C/8)
    signature:   bytes = field(metadata={'codec': H512})


@dataclass
class MsgCE142PreimageAnnouncement(Serializable):
    service_id:      int   = field(metadata={'codec': U32})
    hash:            bytes = field(metadata={'codec': H256})
    preimage_length: int   = field(metadata={'codec': U32})


@dataclass
class MsgCE143HashRequest(Serializable):
    hash: bytes = field(metadata={'codec': H256})


@dataclass
class MsgCE143Preimage(Serializable):
    bytes_: bytes = field(metadata={'codec': Vec(U8)})
