from dataclasses import dataclass, field
from typing import List, Tuple

from jamcodec.mixins import Serializable
from jamcodec.types import U8, String, Vec, Array, Bytes, Tuple as JamTuple, H256, Null

from pyjamaz.models.block import Block
from pyjamaz.transport.fuzzer.v0.types import Version, SetStateMessage


class Features(Serializable):
    BLOCK_ANCESTRY: int = 1 << 0
    SIMPLE_FORKING: int = 1 << 1
    EXTENSION: int      = 1 << 31

    def __init__(self, value: int = 0):
        super().__init__(bits=32)
        self._value = value & 0xFFFFFFFF

    def _get_flag(self, mask: int) -> bool:
        return (self._value & mask) != 0

    def _set_flag(self, mask: int, enabled: bool):
        if enabled:
            self._value |= mask
        else:
            self._value &= ~mask & 0xFFFFFFFF  # keep 32-bit mask

    def encode(self, x:int):
        return U32.encode(x)

    def decode(self, x:int):
        return Features.from_int(U32.decode(x))

    @property
    def block_ancestry(self) -> bool:
        return self._get_flag(self.BLOCK_ANCESTRY)

    @block_ancestry.setter
    def block_ancestry(self, value: bool):
        self._set_flag(self.BLOCK_ANCESTRY, value)

    @property
    def simple_forking(self) -> bool:
        return self._get_flag(self.SIMPLE_FORKING)

    @simple_forking.setter
    def simple_forking(self, value: bool):
        self._set_flag(self.SIMPLE_FORKING, value)

    def to_int(self) -> int:
        return self._value

    @classmethod
    def from_int(cls, value: int) -> "Features":
        return cls(value)


@dataclass
class PeerInfoMessage(Serializable):
    fuzz_version: int = field(metadata={'codec': U8})
    app_version: Version = field(metadata={'codec': Version.to_codec_def()})
    jam_version: Version = field(metadata={'codec': Version.to_codec_def()})
    features: Features = field(metadata={'codec': Features.to_codec_def()})
    name: str = field(metadata={'codec': String})


@dataclass
class FuzzerMessage(Serializable):
    peer_info: PeerInfoMessage = field(default=None, metadata={'codec': PeerInfoMessage.to_codec_def()})
    import_block: Block = field(default=None, metadata={'codec': Block.to_codec_def()})
    set_state: SetStateMessage = field(default=None, metadata={'codec': SetStateMessage.to_codec_def()})
    get_state: bytes = field(default=None, metadata={'codec': H256})
    state: List[Tuple[bytes, bytes]] = field(default=None, metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})
    state_root: bytes = field(default=None, metadata={'codec': H256})
    error: None = field(default=None, metadata={'codec': Null})

    _codec_enum = True
