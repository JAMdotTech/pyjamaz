from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import Array, H256, U8, U32


@dataclass
class MsgCE129KeyRangeRequest(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    key_start: bytes = field(metadata={"codec": Array(U8, 31)})
    key_end: bytes = field(metadata={"codec": Array(U8, 31)})
    max_size: int = field(metadata={"codec": U32})
