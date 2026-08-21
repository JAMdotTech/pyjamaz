from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U8, U32

from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.protocol.messages.common import ImplicitVec


class MsgCE128BlockRequestDirection(Enum):
    ASC = 0
    DESC = 1


@dataclass
class MsgCE128BlockRequest(Serializable):
    header_hash: bytes = field(metadata={"codec": H256})
    direction: int = field(metadata={"codec": U8})
    max_blocks: int = field(metadata={"codec": U32})


@dataclass
class MsgCE128BlockRequestResponse(Serializable):
    blocks: List[Block] = field(metadata={"codec": ImplicitVec(Block.to_codec_def())})
