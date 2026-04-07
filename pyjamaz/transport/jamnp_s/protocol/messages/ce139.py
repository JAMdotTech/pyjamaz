from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import Array, H256, U8, U16, Vec

from pyjamaz.transport.jamnp_s.protocol.messages.common import calculate_r


@dataclass
class MsgCE139SegmentRequest(Serializable):
    erasure_root: bytes = field(metadata={"codec": H256})
    shard_index: int = field(metadata={"codec": U16})
    segment_indices: List[int] = field(metadata={"codec": Vec(U16)})


@dataclass
class MsgCE139SegmentShard(Serializable):
    bytes_: bytes = field(metadata={"codec": Array(U8, 4104 // calculate_r())})
