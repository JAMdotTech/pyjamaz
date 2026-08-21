from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import Array, H256, H512, U8, U16, U32, Vec


@dataclass
class MsgCE144CoreWRPair(Serializable):
    core_index: int = field(metadata={"codec": U16})
    wr_hash: bytes = field(metadata={"codec": H256})


@dataclass
class MsgCE144Announcement(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    tranche: int = field(metadata={"codec": U8})
    announcement: List[MsgCE144CoreWRPair] = field(metadata={"codec": Vec(MsgCE144CoreWRPair.to_codec_def())})
    signature: bytes = field(metadata={"codec": H512})


@dataclass
class MsgCE144NoShow(Serializable):
    validator_index: int = field(metadata={"codec": U32})
    announcement: bytes = field(metadata={"codec": Vec(U8)})


@dataclass
class MsgCE144TrancheEvidenceFirst(Serializable):
    signature: bytes = field(metadata={"codec": Array(U8, 96)})


@dataclass
class MsgCE144TrancheEvidenceSubsequent(Serializable):
    signature: bytes = field(metadata={"codec": Array(U8, 96)})
    no_shows: List[MsgCE144NoShow] = field(metadata={"codec": Vec(MsgCE144NoShow.to_codec_def())})


@dataclass
class MsgCE144Evidence(Serializable):
    data: bytes = field(metadata={"codec": Vec(U8)})
