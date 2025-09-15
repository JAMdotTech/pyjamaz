import asyncio

from dataclasses import dataclass, field
from typing import List, Tuple

from jamcodec.exceptions import ScaleDecodeException
from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import U8, String, Vec, Array, Bytes, Tuple as JamTuple, H256, Null, UnsignedInteger

from pyjamaz.models.block import Block, Header

HEADER_LEN = 4
MAX_MESSAGE_SIZE = 16 * 1024 * 1024
REQUEST_TIMEOUT = 60.0


@dataclass
class Version(Serializable):
    major: int = field(metadata={'codec': U8})
    minor: int = field(metadata={'codec': U8})
    patch: int = field(metadata={'codec': U8})

    @classmethod
    def from_str(cls, version_str: str) -> "Version":
        version_parts = version_str.split('.')
        return Version(
            major=int(version_parts[0]), minor=int(version_parts[1]), patch=int(version_parts[2])
        )

    def __str__(self):
        return f'{self.major}.{self.minor}.{self.patch}'


@dataclass
class SetStateMessage(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    state: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})
    ancestry: List[bytes] = field(metadata={'codec': Vec(H256)})

    def __post_init__(self):
        if len(self.ancestry) > 24:
            raise ValueError(f'ancestry > 24')


class Features():
    BLOCK_ANCESTRY: int = 1 << 0
    SIMPLE_FORKING: int = 1 << 1
    RESERVED: int      = 1 << 31

    def __init__(self, fork:bool=False, ancestry:bool=False):
        self._value = 0 & 0xFFFFFFFF
        self.simple_forking = fork
        self.block_ancestry = ancestry

    def _get_flag(self, mask: int) -> bool:
        return (self._value & mask) != 0

    def _set_flag(self, mask: int, enabled: bool):
        if enabled:
            self._value |= mask
        else:
            self._value &= ~mask & 0xFFFFFFFF  # keep 32-bit mask

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


class FeaturesCodec(UnsignedInteger):

    def __init__(self):
        super().__init__(bits=32)

    def decode(self, data: JamBytes):
        val = super().decode(data)
        instance = Features()
        instance._value = val
        return instance

    def serialize(self, value: int) -> int:
        return value

    def deserialize(self, value: Features) -> int:
        if type(value) is int:
            return value

        if type(value) is not Features:
            raise ValueError('Value must be an Features')

        return value._value


@dataclass
class PeerInfoMessage(Serializable):
    fuzz_version: int = field(metadata={'codec': U8})
    features: Features = field(metadata={'codec': FeaturesCodec()})
    jam_version: Version = field(metadata={'codec': Version.to_codec_def()})
    app_version: Version = field(metadata={'codec': Version.to_codec_def()})
    name: str = field(metadata={'codec': String})


@dataclass
class FuzzerMessage(Serializable):
    peer_info: PeerInfoMessage = field(default=None, metadata={'codec': PeerInfoMessage.to_codec_def()})
    import_block: Block = field(default=None, metadata={'codec': Block.to_codec_def()})
    set_state: SetStateMessage = field(default=None, metadata={'codec': SetStateMessage.to_codec_def()})
    get_state: bytes = field(default=None, metadata={'codec': H256})
    state: List[Tuple[bytes, bytes]] = field(default=None, metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})
    state_root: bytes = field(default=None, metadata={'codec': H256})
    error: str = field(default=None, metadata={'codec': String})

    _codec_enum = True


    def fuzzer_encode(self) -> bytes:
        """Serialize *msg* as JAM-encoded bytes with an U32 length prefix."""
        blob = self.to_jam_bytes().to_bytes()
        if len(blob) > MAX_MESSAGE_SIZE:
            raise ValueError("Message too large: %d bytes" % len(blob))
        return len(blob).to_bytes(HEADER_LEN, "little") + blob


    @classmethod
    async def fuzzer_decode(cls, reader: asyncio.StreamReader) -> "FuzzerMessage":
        """Read one framed JSON message and return it as a dict."""
        header = await reader.readexactly(HEADER_LEN)
        length = int.from_bytes(header, "little")
        if length > MAX_MESSAGE_SIZE:
            raise ValueError("Incoming message too large: %d bytes" % length)
        payload = await reader.readexactly(length)
        try:
            return cls.from_jam_bytes(JamBytes(payload))
        except ScaleDecodeException as e:
            raise ValueError(f"Malformed message: {e}") from e
