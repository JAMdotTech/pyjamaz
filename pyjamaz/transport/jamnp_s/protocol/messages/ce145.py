from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from jamcodec.mixins import Serializable
from jamcodec.types import H256, H512, U8, U32


class JudgmentValidity(Enum):
    INVALID = 0
    VALID = 1


@dataclass
class MsgCE145JudgmentPublication(Serializable):
    epoch_index: int = field(metadata={"codec": U32})
    validator_index: int = field(metadata={"codec": U32})
    validity: int = field(metadata={"codec": U8})
    wr_hash: bytes = field(metadata={"codec": H256})
    signature: bytes = field(metadata={"codec": H512})
