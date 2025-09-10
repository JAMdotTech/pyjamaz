import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import U8, String, Vec, Array, Bytes, Tuple as JamTuple, H256
from jamcodec.exceptions import ScaleDecodeException

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
class PeerInfoMessage(Serializable):
    app_version: Version = field(metadata={'codec': Version.to_codec_def()})
    jam_version: Version = field(metadata={'codec': Version.to_codec_def()})
    name: str = field(metadata={'codec': String})


@dataclass
class SetStateMessage(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    state: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})


@dataclass
class FuzzerMessage(Serializable):
    peer_info: PeerInfoMessage = field(default=None, metadata={'codec': PeerInfoMessage.to_codec_def()})
    import_block: Block = field(default=None, metadata={'codec': Block.to_codec_def()})
    set_state: SetStateMessage = field(default=None, metadata={'codec': SetStateMessage.to_codec_def()})
    get_state: bytes = field(default=None, metadata={'codec': H256})
    state: List[Tuple[bytes, bytes]] = field(default=None, metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})
    state_root: bytes = field(default=None, metadata={'codec': H256})

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
            return FuzzerMessage.from_jam_bytes(JamBytes(payload))
        except ScaleDecodeException as e:
            raise ValueError(f"Malformed message: {e}") from e
