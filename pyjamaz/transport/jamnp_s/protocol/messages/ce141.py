from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, H512, U8, Vec


@dataclass
class MsgCE141Assurance(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    bitfield: bytes = field(metadata={"codec": Vec(U8)})
    signature: bytes = field(metadata={"codec": H512})
