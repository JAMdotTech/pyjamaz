import logging
import struct
from dataclasses import dataclass, field
from typing import List, Tuple


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


STREAM_UP0 = b"\x00"


def _u32le(n: int) -> bytes:
    return struct.pack("<I", n)

def _size_prefixed(payload: bytes) -> bytes:     # spec: len (u32) + payload
    return _u32le(len(payload)) + payload

# message layouts (hash = 32 bytes, slot = u32)
def encode_final(hash32: bytes, slot: int) -> bytes:
    return hash32 + _u32le(slot)

def encode_leaf(hash32: bytes, slot: int) -> bytes:
    return hash32 + _u32le(slot)

def encode_handshake(final: bytes, leaves: List[bytes]) -> bytes:
    body = final + _size_prefixed(b"".join(leaves))
    return _size_prefixed(body)

def encode_announcement(header: bytes, final: bytes) -> bytes:
    body = header + final
    return _size_prefixed(body)


@dataclass
class StreamBlockAnnounce:
    stream: any
    read_buffer: bytearray = field(default_factory=bytearray)

    async def send_handshake(
        self,
        finalized_hash: bytes,
        finalized_slot: int,
        leaves: List[Tuple[bytes, int]],
    ):
        final = encode_final(finalized_hash, finalized_slot)
        leaves_enc = [encode_leaf(h, s) for h, s in leaves]
        await self.stream.write(STREAM_UP0 + encode_handshake(final, leaves_enc))


    async def send_announcement(
        self,
        header_bytes: bytes,
        finalized_hash: bytes,
        finalized_slot: int,
    ):
        final = encode_final(finalized_hash, finalized_slot)
        await self.stream.write(encode_announcement(header_bytes, final))


    async def iter_messages(self):
        while True:
            # read until we have the 4-byte size prefix
            while len(self.read_buffer) < 4:
                data = await self.stream.read(4096)
                if not data:
                    return
                self.read_buffer.extend(data)

            msg_len = struct.unpack_from("<I", self.read_buffer)[0]
            while len(self.read_buffer) < 4 + msg_len:
                data = await self.stream.read(4096)
                if not data:
                    return
                self.read_buffer.extend(data)

            # pop one complete message
            full = bytes(self.read_buffer[4 : 4 + msg_len])
            del self.read_buffer[: 4 + msg_len]
            yield full

