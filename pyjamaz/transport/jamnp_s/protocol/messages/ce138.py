from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U8, U16, Vec


@dataclass
class MsgCE138ShardRequest(Serializable):
    erasure_root: bytes = field(metadata={"codec": H256})
    shard_index: int = field(metadata={"codec": U16})


@dataclass
class MsgCE138BundleShard(Serializable):
    bytes_: bytes = field(metadata={"codec": Vec(U8)})


@dataclass
class MsgCE138Justification(Serializable):
    nodes: List[bytes] = field(metadata={"codec": Vec(Vec(U8))})
