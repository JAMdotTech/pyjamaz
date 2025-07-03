from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from jamcodec.mixins import Serializable
from jamcodec.types import U32, H256, U8, VarInt64, Vec, Option, Array, Map, H512

from pyjamaz.models.block import Header, Guarantee
from pyjamaz.models.common import WorkPackage


@dataclass
class MsgUP0Leaf(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})


@dataclass
class MsgUP0Handshake(Serializable):
    header_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})
    leafs: Optional[List[MsgUP0Leaf]] = field(metadata={'codec': Option(Vec(MsgUP0Leaf.to_codec_def()))})


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


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#
# # ───────────────────────── CE-136 / 143 ────────────────────────
# @dataclass
# class HashRequest(Serializable):          # CE-136 (work-report) & CE-143 (preimage)
#     hash: bytes = field(metadata={'codec': H256})
#
# @dataclass
# class WorkReportEnvelope(Serializable):
#     work_report: 'WorkReport' = field(metadata={'codec': WorkReport.to_codec_def()})
#
# @dataclass
# class Preimage(Serializable):
#     bytes_: bytes = field(metadata={'codec': Vec(U8)})
#
# # ───────────────────────── CE-137 / 138 / 139 / 140 ───────────
# @dataclass
# class ShardRequestHead(Serializable):     # CE-137 & CE-138 share first message
#     erasure_root: bytes = field(metadata={'codec': H256})
#     shard_index:  int   = field(metadata={'codec': U32})      # spec uses u32
#
# @dataclass
# class SegmentShardRequestHead(Serializable):  # CE-139 / 140
#     erasure_root: bytes = field(metadata={'codec': H256})
#     shard_index:  int   = field(metadata={'codec': U32})
#     segment_indices: List[int] = field(
#         metadata={'codec': Vec(U16)}                          # u16 each
#     )
#
# @dataclass
# class JustificationNode(Serializable):        # 0,1,2 tagged union – bytestream
#     raw: bytes = field(metadata={'codec': Vec(U8)})
#
# # reply payloads for 137-140 are raw blobs; dataclasses optional
#
# # ───────────────────────── CE-141 ──────────────────────────────
# @dataclass
# class Assurance(Serializable):
#     header_hash: bytes = field(metadata={'codec': H256})   # anchor
#     bitfield:    bytes = field(metadata={'codec': Vec(U8)})  # len = ceil(C/8)
#     signature:   bytes = field(metadata={'codec': Array(U8, 64)})
#
# # ───────────────────────── CE-142 ──────────────────────────────
# @dataclass
# class PreimageAnnouncement(Serializable):
#     service_id:      int   = field(metadata={'codec': U32})
#     hash:            bytes = field(metadata={'codec': H256})
#     preimage_length: int   = field(metadata={'codec': U32})
#
# # ───────────────────────── CE-144 ──────────────────────────────
# @dataclass
# class CoreWRPair(Serializable):
#     core_index: int   = field(metadata={'codec': U32})
#     wr_hash:   bytes = field(metadata={'codec': H256})
#
# @dataclass
# class NoShow(Serializable):
#     validator_index: int      = field(metadata={'codec': U32})
#     announcement:    bytes    = field(metadata={'codec': Vec(U8)})  # raw bytes
#
# @dataclass
# class TrancheEvidenceFirst(Serializable):
#     signature: bytes = field(metadata={'codec': Array(U8, 96)})  # Bandersnatch
#
# @dataclass
# class TrancheEvidenceSubsequent(Serializable):
#     signature: bytes            = field(metadata={'codec': Array(U8, 96)})
#     no_shows:  List[NoShow]     = field(metadata={'codec': Vec(NoShow.to_codec_def())})
#
# @dataclass
# class AuditAnnouncement(Serializable):
#     header_hash: bytes                 = field(metadata={'codec': H256})
#     tranche:     int                   = field(metadata={'codec': U8})
#     announcement: List[CoreWRPair]     = field(metadata={'codec': Vec(CoreWRPair.to_codec_def())})
#     evidence: bytes = field(           # discriminated union; raw bytes easiest
#         metadata={'codec': Vec(U8)}
#     )
#
# # ───────────────────────── CE-145 ──────────────────────────────
# class JudgmentValidity(Enum):
#     INVALID = 0
#     VALID   = 1
#
# @dataclass
# class JudgmentPublication(Serializable):
#     epoch_index:     int   = field(metadata={'codec': U32})
#     validator_index: int   = field(metadata={'codec': U32})
#     validity:        int   = field(metadata={'codec': U8})     # enum above
#     wr_hash:         bytes = field(metadata={'codec': H256})
#     signature:       bytes = field(metadata={'codec': Array(U8, 64)})
#
# # -----------------------------------------------------------------
# # Helper type used above (validator sig in CE-135)
# @dataclass
# class ValidatorSig(Serializable):
#     validator_index: int   = field(metadata={'codec': U32})
#     signature:       bytes = field(metadata={'codec': Array(U8, 64)})