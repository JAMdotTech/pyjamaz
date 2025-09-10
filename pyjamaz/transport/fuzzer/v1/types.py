from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import U8, String, U32

from pyjamaz.transport.fuzzer.v0.types import Version


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
