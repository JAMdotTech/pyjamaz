from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U32, Vec

from pyjamaz.models.block import Header


@dataclass
class MsgUP0Leaf(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    timeslot: int = field(metadata={"codec": U32})


@dataclass
class MsgUP0Handshake(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    timeslot: int = field(metadata={"codec": U32})
    leafs: List[MsgUP0Leaf] = field(metadata={"codec": Vec(MsgUP0Leaf.to_codec_def())})


@dataclass
class MsgUP0Announcement(Serializable):
    header: Header = field(metadata={"codec": Header.to_codec_def()})
    header_hash: bytes = field(metadata={"codec": H256})
    timeslot: int = field(metadata={"codec": U32})
