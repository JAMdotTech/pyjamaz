from dataclasses import dataclass, field
from typing import Tuple, List

from jamcodec.mixins import Serializable
from jamcodec.types import H256, Tuple as JamTuple, Vec, Bytes, Array, U8

from pyjamaz.models.block import Block


@dataclass
class StateDump(Serializable):
    state_root: bytes = field(metadata={'codec': H256})
    keyvals: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})


@dataclass
class Trace(Serializable):
    pre_state: StateDump = field(metadata={'codec': StateDump.to_codec_def()})
    block: Block = field(metadata={'codec': Block.to_codec_def()})
    post_state: StateDump = field(metadata={'codec': StateDump.to_codec_def()})
