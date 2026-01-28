from dataclasses import dataclass, field
from typing import Tuple, List, Type

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable, T
from jamcodec.types import H256, Tuple as JamTuple, Vec, Bytes, Array, U8
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE

from pyjamaz.models.block import Block, Header
from pyjamaz.utils import log_execution_time


@dataclass
class ChainspecDump(Serializable):
    keyvals: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(H256, Bytes))})
    state_root: bytes = field(metadata={'codec': H256})


@dataclass
class StateDump(Serializable):
    state_root: bytes = field(metadata={'codec': H256})
    keyvals: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})


@dataclass
class Trace(Serializable):
    pre_state: StateDump = field(metadata={'codec': StateDump.to_codec_def()})
    block: Block = field(metadata={'codec': Block.to_codec_def()})
    post_state: StateDump = field(metadata={'codec': StateDump.to_codec_def()})

    @classmethod
    @log_execution_time
    def from_jam_bytes(cls: Type[T], scale_bytes: JamBytes) -> T:
        return super(Trace, cls).from_jam_bytes(scale_bytes)

@dataclass
class TraceGenesis(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    state: StateDump = field(metadata={'codec': StateDump.to_codec_def()})


@dataclass
class D3LItem(Serializable):
    segment_root: bytes = field(metadata={'codec': H256})
    segments: List[bytes] = field(metadata={'codec': Vec(Array(U8, EC_SEGMENT_SIZE))})
