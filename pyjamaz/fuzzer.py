import asyncio
import logging
import os
import typing
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import U8, String, Vec, Array, Bytes, Tuple as JamTuple, H256
from jamcodec.exceptions import ScaleDecodeException

from pyjamaz.settings import GP_VERSION, APP_VERSION
from pyjamaz.models.block import Block, Header
from pyjamaz.utils import format_hash

if typing.TYPE_CHECKING:
    from pyjamaz.app import PyjamazApp

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
    name: str = field(metadata={'codec': String})
    app_version: Version = field(metadata={'codec': Version.to_codec_def()})
    jam_version: Version = field(metadata={'codec': Version.to_codec_def()})


@dataclass
class SetStateMessage(Serializable):
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    state: List[Tuple[bytes, bytes]] = field(metadata={'codec': Vec(JamTuple(Array(U8, 31), Bytes))})


@dataclass
class Message(Serializable):
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
    async def fuzzer_decode(cls, reader: asyncio.StreamReader) -> "Message":
        """Read one framed JSON message and return it as a dict."""
        header = await reader.readexactly(HEADER_LEN)
        length = int.from_bytes(header, "little")
        if length > MAX_MESSAGE_SIZE:
            raise ValueError("Incoming message too large: %d bytes" % length)
        payload = await reader.readexactly(length)
        try:
            return Message.from_jam_bytes(JamBytes(payload))
        except ScaleDecodeException as e:
            raise ValueError(f"Malformed message: {e}") from e


class TargetServer:
    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app
        # Wipe any stale socket first
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.path)
        addr = self.server.sockets[0].getsockname()
        logging.info(f'🥋 PyJAMaz JAM [Fuzzer]')
        logging.info(f"🌐 Listening on {addr}")
        logging.info(f'🧾 Graypaper version: {GP_VERSION} ')

        async with self.server:
            await self.server.serve_forever()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logging.info(f"[target] Accepted connection from {peer}")
        try:
            # Handshake: wait for their PeerInfo first.
            them = await Message.fuzzer_decode(reader)

            ours = Message(
                peer_info=PeerInfoMessage(
                    name="PyJAMaz",
                    app_version=Version.from_str(APP_VERSION),
                    jam_version=Version.from_str(GP_VERSION)
                )
            )
            writer.write(ours.fuzzer_encode())
            await writer.drain()
            logging.info(
                f"[target] Handshake complete with {them.peer_info.name} (v{them.peer_info.app_version})"
            )

            # Main request‑response loop
            while True:
                try:
                    req = await Message.fuzzer_decode(reader)
                except asyncio.IncompleteReadError:
                    # EOF – fuzzer closed the connection cleanly
                    break
                except Exception as e:
                    logging.error(f"[target] Decode error: {e}; closing session")
                    break

                try:
                    rsp = await self._dispatch(req)
                except Exception as e:
                    logging.error(f"[target] Handler error for {req}: {e}")
                    break  # blunt termination on malformed/unexpected messages

                writer.write(rsp.fuzzer_encode())
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            logging.info("[target] Session finished")


    async def _dispatch(self, req: Message) -> Message:
        """
        Request - response pattern for fuzzer

        Parameters
        ----------
        req: Message

        Returns
        -------
        Message
        """
        # TODO finish implementation
        if req.peer_info is not None:
            return Message(
                peer_info=PeerInfoMessage(
                    name="PyJAMaz",
                    app_version=Version.from_str(APP_VERSION),
                    jam_version=Version.from_str(GP_VERSION)
                )
            )
        elif req.get_state is not None:

            return Message(
                state=list(self.app.state_db)
            )
        elif req.set_state is not None:

            # Update state from trace pre-state
            for k, v in req.set_state.state:
                self.app.state_db.put(bytes(k), bytes(v))

            self.app.state = self.app.retrieve_jam_state()
            await self.app.update_state_trie()

            # Add to ancestors
            self.app.block_context.ancestor_headers.append(req.set_state.header)

            logging.info(f"💾 State set to {format_hash(self.app.state_trie_root)}")
            return Message(state_root=self.app.state_trie_root)

        elif req.import_block is not None:
            await self.app.import_block(req.import_block)
            logging.info(f"✅ Block {format_hash(req.import_block.header.hash)} imported -> state root: {format_hash(self.app.state_trie_root)}")
            return Message(state_root=self.app.state_trie_root)

        else:
            raise RuntimeError(f"Unknown incoming message {req.to_json()}")


class FuzzerSession:
    def __init__(self, path: str, app: 'PyjamazApp') -> None:
        self.path = path
        self.app = app
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_unix_connection(self.path)
        await self._do_handshake()

    async def _do_handshake(self) -> None:
        # Send our PeerInfo first
        jam_version = Version.from_str(GP_VERSION)

        our_peerinfo = Message(
            peer_info=PeerInfoMessage(
                name="PyJAMaz",
                app_version=Version.from_str(APP_VERSION),
                jam_version=jam_version
            )
        )
        self.writer.write(our_peerinfo.fuzzer_encode())
        await self.writer.drain()

        # Await the target's PeerInfo.
        try:
            target_peerinfo = await asyncio.wait_for(Message.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError("Target did not send PeerInfo in time")

        if target_peerinfo.peer_info.jam_version != jam_version:
            raise RuntimeError(
                f"Protocol version mismatch: ours={GP_VERSION}, theirs={target_peerinfo.peer_info.jam_version}"
            )
        logging.info(f"[fuzzer] Connected to {target_peerinfo.peer_info.name} (v{target_peerinfo.peer_info.app_version})")


    async def send_request(self, req: Message) -> Message:
        """Send *req* and return the parsed response."""

        # logging.debug(f"[fuzzer] Sending {req.to_json()}")
        self.writer.write(req.fuzzer_encode())
        await self.writer.drain()
        try:
            rsp = await asyncio.wait_for(Message.fuzzer_decode(self.reader), timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Target timed out when responding to {req.to_json()}")
        # TODO message type sanity checks
        # logging.debug(f"[fuzzer] Received {rsp.to_json()}")
        return rsp

    async def close(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()
        logging.info("[fuzzer] Session closed")

