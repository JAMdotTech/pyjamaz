from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U8, Vec


@dataclass
class MsgCE143HashRequest(Serializable):
    hash: bytes = field(metadata={"codec": H256})


@dataclass
class MsgCE143Preimage(Serializable):
    bytes_: bytes = field(metadata={"codec": Vec(U8)})
