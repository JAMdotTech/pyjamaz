"""JAMNP-S v1 transport, pinned to jam-np/simple.md at e0b7d291.

The transport authenticates peers and owns framing. AvailabilityRuntime owns
source eligibility, retained data and submission authorization. Each CE stream
has an independent bounded reader; successful requests finish both directions.
"""

import asyncio
import ipaddress
import logging
import ssl
from enum import IntEnum

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import (
    ConnectionTerminated, HandshakeCompleted, StopSendingReceived,
    StreamDataReceived, StreamReset,
)
from jamcodec.base import JamBytes
from jamcodec.types import VarInt64, Vec

from pyjamaz.availability import (
    ImportedSegment, ValidatorShard, verify_audit_shard, verify_import,
    verify_segment_shard, verify_validator_shard,
)
from pyjamaz.bundle import decode_bundle, decode_package
from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.erasure import erasure_data_shards
from pyjamaz.models.block import Block, Header
from pyjamaz.transport.cert import validate_peer_certificate
from pyjamaz.transport.jamnp_messages import (
    InvalidJAMNPSMessage, decode_import_proofs, decode_justification, decode_mappings,
    encode_import_proofs, encode_segment_indices, encode_segment_request, frame, read_count, split_segments,
)
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.transport.types import ProtocolType


logger = logging.getLogger("pyjamaz.transport")
MAX_STREAM_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = 200 * 1024
REQUEST_TIMEOUT = 5.0
REJECTED = 1
CANCELLED = 2


class StreamBuffer:
    """An incremental reader for one stream, including split length prefixes."""

    def __init__(self, maximum: int = MAX_STREAM_BYTES):
        self.buffer = bytearray()
        self.maximum = maximum
        self.received = 0
        self.finished = False
        self.error = None
        self.changed = asyncio.Event()

    def feed(self, data: bytes, finished: bool = False):
        if self.finished or self.error:
            if data:
                raise InvalidJAMNPSMessage("data after stream completion")
            return
        self.received += len(data)
        if len(self.buffer) + len(data) > self.maximum:
            self.abort(InvalidJAMNPSMessage("stream exceeds byte limit"))
            return
        self.buffer.extend(data)
        self.finished = finished
        self.changed.set()

    def abort(self, error: Exception):
        self.error = error
        self.changed.set()

    async def read_exact(self, count: int, *, allow_end: bool = False) -> bytes | None:
        while len(self.buffer) < count:
            if self.error:
                raise self.error
            if self.finished:
                if allow_end and not self.buffer:
                    return None
                raise InvalidJAMNPSMessage("truncated stream")
            self.changed.clear()
            await self.changed.wait()
        if self.error:
            raise self.error
        value = bytes(self.buffer[:count])
        del self.buffer[:count]
        return value

    async def read_message(self, maximum: int = MAX_STREAM_BYTES) -> bytes | None:
        prefix = await self.read_exact(4, allow_end=True)
        if prefix is None:
            return None
        length = int.from_bytes(prefix, "little")
        if length > maximum:
            raise InvalidJAMNPSMessage("message exceeds byte limit")
        return await self.read_exact(length)

    async def read_all(self, maximum_messages: int = 6145) -> list[bytes]:
        messages = []
        while (message := await self.read_message()) is not None:
            if len(messages) >= maximum_messages:
                raise InvalidJAMNPSMessage("too many stream messages")
            messages.append(message)
        return messages


def wrap_protocol(wrapper, protocol, expected_key=None):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.wrapper = wrapper
        instance.expected_key = expected_key
        return instance
    return create_protocol


class JAMNPSProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrapper = None
        self.expected_key = None
        self.peer_key = None
        self.identity_error = None
        self.stream_up_0 = None
        self.streams: dict[int, StreamBuffer] = {}
        self.tasks: dict[int, asyncio.Task] = {}
        self.receive_ready = set()
        # Hold the initial small flow-control window until the stream kind is
        # known and staged submissions are authorized. aioquic normally grows
        # it on receipt, which would let a rejected package upload its body.
        write_limits = self._quic._write_stream_limits
        def write_stream_limits(*, builder, space, stream):
            if stream.stream_id in self.receive_ready:
                return write_limits(builder=builder, space=space, stream=stream)
            highest_offset = stream.receiver.highest_offset
            try:
                stream.receiver.highest_offset = 0
                return write_limits(builder=builder, space=space, stream=stream)
            finally:
                stream.receiver.highest_offset = highest_offset
        self._quic._write_stream_limits = write_stream_limits
        # aioquic 1.3 has no public mutual-TLS switch. Request the client
        # certificate before its TLS context starts; signature possession is
        # checked by TLS, and the v1 identity is checked on HandshakeCompleted.
        if not self._quic.configuration.is_client:
            initialize = self._quic._initialize
            def initialize_with_client_certificate(peer_cid):
                initialize(peer_cid)
                self._quic.tls._request_client_certificate = True
            self._quic._initialize = initialize_with_client_certificate

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            try:
                if event.alpn_protocol not in self.wrapper.configuration.alpn_protocols:
                    raise ValueError("incorrect JAMNP-S version or genesis")
                self.peer_key = validate_peer_certificate(self._quic.tls._peer_certificate, self.expected_key)
                self.wrapper.conn_in[id(self)] = self
            except ValueError as exc:
                self.identity_error = exc
                self.close(error_code=REJECTED, reason_phrase=str(exc))
            super().quic_event_received(event)
        elif isinstance(event, StreamDataReceived):
            reader = self.streams.get(event.stream_id)
            if reader is None:
                local_initiator = 0 if self._quic.configuration.is_client else 1
                if event.stream_id & 1 == local_initiator:
                    return  # Late response bytes after a local cancellation.
                if len(self.streams) >= 64 or event.stream_id & 2:
                    self._reject_stream(event.stream_id)
                    return
                reader = self.streams[event.stream_id] = StreamBuffer()
                self.tasks[event.stream_id] = asyncio.create_task(self._serve_stream(event.stream_id, reader))
            try:
                reader.feed(event.data, event.end_stream)
            except InvalidJAMNPSMessage:
                self._reject_stream(event.stream_id)
        elif isinstance(event, (StreamReset, StopSendingReceived)):
            reader = self.streams.get(event.stream_id)
            if reader:
                reader.abort(ConnectionError("peer reset the JAMNP-S stream"))
            task = self.tasks.get(event.stream_id)
            if task:
                task.cancel()
            if isinstance(event, StopSendingReceived):
                self._quic.reset_stream(event.stream_id, CANCELLED)
                self.transmit()
        elif isinstance(event, ConnectionTerminated):
            for reader in self.streams.values():
                reader.abort(ConnectionError("JAMNP-S connection terminated"))
            for task in self.tasks.values():
                task.cancel()
            if self.wrapper:
                self.wrapper.conn_in.pop(id(self), None)
            super().quic_event_received(event)
        else:
            super().quic_event_received(event)

    def _reject_stream(self, stream_id: int):
        self._quic.reset_stream(stream_id, REJECTED)
        self._quic.stop_stream(stream_id, REJECTED)
        self.transmit()

    def _send_messages(self, stream_id, messages, *, end_stream=True):
        for message in messages:
            self._quic.send_stream_data(stream_id, frame(message))
        if end_stream:
            self._quic.send_stream_data(stream_id, b"", end_stream=True)
        self.transmit()

    def _open_receive_window(self, stream_id):
        self.receive_ready.add(stream_id)
        self._quic._streams[stream_id].max_stream_data_local = MAX_STREAM_BYTES
        self.transmit()

    async def request(self, kind: int, messages: list[bytes], timeout=REQUEST_TIMEOUT) -> list[bytes]:
        if self.identity_error:
            raise ConnectionError(str(self.identity_error))
        if self.peer_key is None:
            raise ConnectionError("peer is not authenticated")
        stream_id = self._quic.get_next_available_stream_id()
        reader = self.streams[stream_id] = StreamBuffer()
        self._quic.send_stream_data(stream_id, bytes([kind]))
        self._open_receive_window(stream_id)
        self._send_messages(stream_id, messages)
        try:
            async with asyncio.timeout(timeout):
                return await reader.read_all()
        except (TimeoutError, asyncio.CancelledError):
            self._quic.reset_stream(stream_id, CANCELLED)
            self._quic.stop_stream(stream_id, CANCELLED)
            self.transmit()
            raise
        finally:
            self.streams.pop(stream_id, None)
            self.receive_ready.discard(stream_id)

    async def _serve_stream(self, stream_id, reader):
        try:
            kind = (await reader.read_exact(1))[0]
            if self.peer_key is None or self.identity_error:
                raise InvalidJAMNPSMessage("unauthenticated peer")
            if kind not in (133, 146):
                self._open_receive_window(stream_id)
            if kind == 0:
                if self._quic.configuration.is_client:
                    raise InvalidJAMNPSMessage("UP0 must be opened by the connection initiator")
                await self._receive_up0(stream_id, reader)
                return
            async with asyncio.timeout(REQUEST_TIMEOUT):
                if kind in (133, 146):
                    responses = await self._submission(stream_id, kind, reader)
                else:
                    limits = {128: 37, 137: 34, 138: 34, 139: 6144 * 38,
                              140: 6144 * 38, 147: 32, 148: 3072 * 36}
                    if kind not in limits:
                        raise InvalidJAMNPSMessage("unsupported stream kind")
                    message = await reader.read_message(limits[kind])
                    if message is None or await reader.read_message(0) is not None:
                        raise InvalidJAMNPSMessage("request requires one message")
                    messages = [message]
                    if kind == 128:
                        responses = [self.wrapper.serve_blocks(messages[0])]
                    elif kind in (137, 138, 139, 140, 147, 148):
                        responses = await self.wrapper.availability.handle_request(self.peer_key, kind, messages)
                    else:
                        raise InvalidJAMNPSMessage("unsupported stream kind")
                self._send_messages(stream_id, responses)
        except asyncio.CancelledError:
            self._reject_stream(stream_id)
            raise
        except Exception as exc:
            logger.debug("Rejecting JAMNP-S stream %s: %s", stream_id, exc)
            self._reject_stream(stream_id)
        finally:
            self.streams.pop(stream_id, None)
            self.tasks.pop(stream_id, None)
            self.receive_ready.discard(stream_id)

    async def _submission(self, stream_id, kind, reader):
        # JAMNP-S CE133/146: authorize the small package before interpreting
        # or processing the later, potentially large, payload frames.
        first = await reader.read_message(MAX_PACKAGE_BYTES + 2)
        if first is None or len(first) < 2:
            raise InvalidJAMNPSMessage("missing submission header")
        core_index = int.from_bytes(first[:2], "little")
        if kind == 133:
            mappings, package_data = {}, first[2:]
        else:
            mappings = decode_mappings(first[2:])
            package_data = await reader.read_message(MAX_PACKAGE_BYTES)
            if package_data is None:
                raise InvalidJAMNPSMessage("missing work package")
        package, consumed = decode_package(package_data)
        if consumed != len(package_data):
            raise InvalidJAMNPSMessage("trailing package bytes")
        context = await self.wrapper.availability.authorize_submission(self.peer_key, core_index, package, mappings)
        self._open_receive_window(stream_id)
        messages = await reader.read_all(maximum_messages=1 if kind == 133 else 3)
        if len(messages) != (1 if kind == 133 else 3):
            raise InvalidJAMNPSMessage("incorrect submission message count")
        return await self.wrapper.availability.complete_submission(context, kind, messages)

    def build_handshake_message(self):
        return self.wrapper.up0_handshake()

    async def open_stream_up_0(self):
        stream_id = self._quic.get_next_available_stream_id()
        reader = self.streams[stream_id] = StreamBuffer()
        self.stream_up_0 = stream_id
        self._quic.send_stream_data(stream_id, b"\x00")
        self._open_receive_window(stream_id)
        self._send_messages(stream_id, [self.build_handshake_message()], end_stream=False)
        self.tasks[stream_id] = asyncio.create_task(self._receive_up0(stream_id, reader, initiated=True))

    async def _receive_up0(self, stream_id, reader, initiated=False):
        if self.stream_up_0 is not None and stream_id < self.stream_up_0:
            raise InvalidJAMNPSMessage("superseded UP0 stream")
        previous = self.stream_up_0
        self.stream_up_0 = stream_id
        if previous is not None and previous != stream_id:
            self._reject_stream(previous)
        try:
            if not initiated:
                self._send_messages(stream_id, [self.build_handshake_message()], end_stream=False)
            handshake = await reader.read_message(1024 * 1024)
            self.wrapper.validate_up0_handshake(handshake)
            while (announcement := await reader.read_message(1024 * 1024)) is not None:
                await self.wrapper.receive_announcement(self, announcement)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._reject_stream(stream_id)
        finally:
            self.streams.pop(stream_id, None)
            self.tasks.pop(stream_id, None)
            if self.stream_up_0 == stream_id:
                self.stream_up_0 = None

    async def send_block_announcement(self, block_bytes):
        if self.stream_up_0 is None:
            return
        block = Block.from_jam_bytes(JamBytes(block_bytes))
        payload = block.header.to_jam_bytes().to_bytes() + self.wrapper.final_descriptor()
        self._send_messages(self.stream_up_0, [payload], end_stream=False)

    async def send_blocks_request(self, direction, max_blocks, block_bytes):
        block = Block.from_jam_bytes(JamBytes(block_bytes))
        await self.wrapper.fetch_blocks(self, block.header.hash, direction, max_blocks)


class ServerProtocol(JAMNPSProtocol):
    pass


class ClientProtocol(JAMNPSProtocol):
    pass


class SessionTicketStore:
    def __init__(self):
        self.tickets = {}

    def add(self, ticket):
        self.tickets[ticket.ticket] = ticket

    def pop(self, label):
        return self.tickets.pop(label, None)


class JAMNPS(ProtocolType):
    class MSG(IntEnum):
        UP0_OPEN = 0
        UP0_BlockAnnouncement = 0
        CE128_BlockRequest = 128
        CE133_WorkPackage = 133
        CE137_ValidatorShard = 137
        CE138_AuditShard = 138
        CE139_SegmentShards = 139
        CE140_ProvenSegmentShards = 140
        CE146_WorkPackageBundle = 146
        CE147_Bundle = 147
        CE148_Segments = 148

    def __init__(self, host, port, certificate, private_key, app, *, genesis_hash=None):
        self.host, self.port, self.cert, self.pk, self.app = host, port, certificate, private_key, app
        self.broadcaster = app.pubsub
        genesis_hash = genesis_hash or getattr(app, "genesis_hash", None) or app.retrieve_block_hash(0)
        if not isinstance(genesis_hash, bytes) or len(genesis_hash) != 32:
            raise ValueError("JAMNP-S requires the chain's genesis header hash")
        self.genesis_hash = genesis_hash
        self.PROTOCOL_NAME = "jamnp-s/1/" + genesis_hash.hex()[:8]
        self.configuration = self._configuration(is_client=False)
        self.conn_in, self.conn_out = {}, {}
        self.session_ticket_store = SessionTicketStore()
        self.server = None

    @property
    def availability(self):
        return self.app.runtime.availability

    def _configuration(self, *, is_client, builder=False):
        protocols = [self.PROTOCOL_NAME + "/builder"] if builder else [self.PROTOCOL_NAME]
        if not is_client:
            protocols.append(self.PROTOCOL_NAME + "/builder")
        configuration = QuicConfiguration(alpn_protocols=protocols, is_client=is_client,
                                          verify_mode=ssl.CERT_NONE, idle_timeout=60,
                                          max_data=MAX_STREAM_BYTES, max_stream_data=MAX_PACKAGE_BYTES + 1024)
        configuration.load_cert_chain(self.cert, self.pk)
        # Self-signed chains are expected. The v1 Ed25519/SAN identity is checked
        # explicitly after TLS, including expected validator-key pinning.
        validate_peer_certificate(configuration.certificate)
        return configuration

    async def listen(self):
        self.server = await serve(self.host, self.port, configuration=self.configuration,
                                  create_protocol=wrap_protocol(self, ServerProtocol),
                                  session_ticket_fetcher=self.session_ticket_store.pop,
                                  session_ticket_handler=self.session_ticket_store.add, retry=True)
        return self.server

    async def connect(self, host, port):
        try:
            async with connect(host, port, configuration=self._configuration(is_client=True),
                               create_protocol=wrap_protocol(self, ClientProtocol)) as client:
                if client.identity_error:
                    raise ConnectionError(str(client.identity_error))
                self.conn_out[(host, port)] = client
                try:
                    await client.open_stream_up_0()
                    await client.wait_closed()
                finally:
                    self.conn_out.pop((host, port), None)
        except ConnectionError as exc:
            logger.debug("Cannot connect to %s:%s: %s", host, port, exc)

    @staticmethod
    def peer_endpoint(peer):
        raw_address = bytes(peer.metadata[:16])
        address = ipaddress.IPv6Address(raw_address)
        host = str(address.ipv4_mapped or address)
        # Older local node metadata stored IPv4 in the first four bytes. Read
        # those persisted endpoints during migration; new metadata uses v1's
        # full 16-byte IPv6 field, including IPv4-mapped addresses.
        if raw_address[4:] == bytes(12) and raw_address[:4] != bytes(4):
            host = str(ipaddress.IPv4Address(raw_address[:4]))
        port = int.from_bytes(peer.metadata[16:18], "little")
        if not port or address.is_unspecified:
            raise ConnectionError("validator has no JAMNP-S endpoint")
        return host, port

    async def request(self, peer, kind: int, messages: list[bytes]) -> list[bytes]:
        # Bounded connection establishment and CE exchange, including FIN.
        host, port = self.peer_endpoint(peer)
        expected_key = bytes(peer.ed25519)
        async with asyncio.timeout(REQUEST_TIMEOUT):
            for protocol in list(self.conn_in.values()):
                if protocol.peer_key == expected_key and not protocol.identity_error:
                    return await protocol.request(kind, messages)
            async with connect(host, port, configuration=self._configuration(is_client=True, builder=kind in (133, 146)),
                               create_protocol=wrap_protocol(self, ClientProtocol, expected_key)) as protocol:
                if protocol.identity_error:
                    raise ConnectionError(str(protocol.identity_error))
                return await protocol.request(kind, messages)

    async def submit_work_package_bundle(self, peer, core_index: int, bundle: bytes, mappings=None) -> None:
        """Submit canonical B(p,l) using staged CE133 or CE146 (a convenience API)."""
        if isinstance(core_index, bool) or not isinstance(core_index, int) or not 0 <= core_index <= 65535:
            raise InvalidJAMNPSMessage("invalid submission core")
        parts = decode_bundle(bundle)
        mappings = mappings or {}
        package_bytes = parts.package.to_jam_bytes().to_bytes()
        extrinsics = b"".join(parts.extrinsics)
        if parts.segments or mappings:
            if len(mappings) > 8 or any(len(key) != 32 or len(root) != 32 for key, root in mappings.items()):
                raise InvalidJAMNPSMessage("invalid submission mappings")
            header = (core_index.to_bytes(2, "little") + VarInt64.encode(len(mappings)).to_bytes()
                      + b"".join(key + mappings[key] for key in sorted(mappings)))
            kind, messages = 146, [header, package_bytes, extrinsics, b"".join(parts.segments),
                                   encode_import_proofs(parts.justifications)]
        else:
            kind, messages = 133, [core_index.to_bytes(2, "little") + package_bytes, extrinsics]
        if await self.request(peer, kind, messages):
            raise InvalidJAMNPSMessage("submission response must contain only FIN")

    async def request_validator_shard(self, peer, spec, shard_index: int) -> ValidatorShard:
        if not 0 <= shard_index < spec.erasure_shards:
            raise InvalidJAMNPSMessage("invalid validator shard index")
        messages = await self.request(peer, 137, [spec.erasure_root + shard_index.to_bytes(2, "little")])
        if len(messages) != 3:
            raise InvalidJAMNPSMessage("incorrect CE137 response message count")
        size = 4104 // erasure_data_shards(spec.erasure_shards)
        count = spec.exports_count + (spec.exports_count + 63) // 64
        shard = ValidatorShard(shard_index, messages[0], split_segments(messages[1], count, size),
                               decode_justification(messages[2]))
        verify_validator_shard(shard, spec)
        return shard

    async def request_audit_shard(self, peer, spec, shard_index: int):
        if not 0 <= shard_index < spec.erasure_shards:
            raise InvalidJAMNPSMessage("invalid audit shard index")
        messages = await self.request(peer, 138, [spec.erasure_root + shard_index.to_bytes(2, "little")])
        if len(messages) != 2:
            raise InvalidJAMNPSMessage("incorrect CE138 response message count")
        proof = decode_justification(messages[1])
        verify_audit_shard(messages[0], shard_index, proof, spec)
        return messages[0], proof

    async def request_segment_shards(self, peer, spec, shard_index: int, segment_indices, *, proven=False):
        count = spec.exports_count + (spec.exports_count + 63) // 64
        if not 0 <= shard_index < spec.erasure_shards or any(not 0 <= i < count for i in segment_indices):
            raise InvalidJAMNPSMessage("invalid segment or validator index")
        messages = await self.request(peer, 140 if proven else 139,
                                      [encode_segment_request(spec.erasure_root, shard_index, segment_indices)])
        expected = 1 + (len(segment_indices) if proven else 0)
        if len(messages) != expected:
            raise InvalidJAMNPSMessage("incorrect segment-shard response message count")
        size = 4104 // erasure_data_shards(spec.erasure_shards)
        chunks = split_segments(messages[0], len(segment_indices), size)
        result = []
        for offset, (index, chunk) in enumerate(zip(segment_indices, chunks)):
            proof = decode_justification(messages[offset + 1], size) if proven else None
            if proven:
                verify_segment_shard(chunk, index, shard_index, proof, spec)
            result.append((chunk, proof))
        return result

    async def request_segments(self, peer, root: bytes, indices) -> list[ImportedSegment]:
        messages = await self.request(peer, 148, [encode_segment_indices(root, indices)])
        if len(messages) != 2:
            raise InvalidJAMNPSMessage("incorrect complete-segment response message count")
        segments = split_segments(messages[0], len(indices))
        proofs = decode_import_proofs(messages[1], len(indices))
        imports = [ImportedSegment(segment, proof) for segment, proof in zip(segments, proofs)]
        for index, imported in zip(indices, imports):
            verify_import(root, index, imported)
        return imports

    async def request_bundle(self, peer, spec) -> bytes:
        messages = await self.request(peer, 147, [spec.erasure_root])
        if len(messages) != 1 or len(messages[0]) != spec.length:
            raise InvalidJAMNPSMessage("incorrect bundle response length")
        # A complete bundle has no individual CE147 co-path. The caller checks
        # it against the source specification when recomputing A(h,b,s,v).
        return messages[0]

    def final_descriptor(self):
        final_hash = self.app.retrieve_finalized_head() or self.genesis_hash
        header = self.app.retrieve_block_header(final_hash)
        slot = header.timeslot if header is not None else 0
        return final_hash + slot.to_bytes(4, "little")

    def _head(self):
        state = getattr(self.app, "working_state", None)
        slot = state.timeslot.number if state is not None else 0
        return self.app.retrieve_block_hash(slot) or self.genesis_hash, slot

    def up0_handshake(self):
        head_hash, slot = self._head()
        # The application currently retains one canonical leaf. This is the
        # complete known-leaf set for that storage model.
        return self.final_descriptor() + VarInt64.encode(1).to_bytes() + head_hash + slot.to_bytes(4, "little")

    @staticmethod
    def validate_up0_handshake(data):
        if data is None or len(data) < 37:
            raise InvalidJAMNPSMessage("missing UP0 handshake")
        stream = JamBytes(data)
        try:
            stream.get_next_bytes(36)
            count = read_count(stream, 16384)
            leaves = [bytes(stream.get_next_bytes(36)) for _ in range(count)]
            if stream.get_remaining_length() or len(set(leaves)) != len(leaves):
                raise InvalidJAMNPSMessage("invalid UP0 leaves")
        except Exception as exc:
            raise InvalidJAMNPSMessage("malformed UP0 handshake") from exc

    async def receive_announcement(self, protocol, payload):
        if len(payload) < 36:
            raise InvalidJAMNPSMessage("truncated block announcement")
        stream = JamBytes(payload[:-36])
        header = Header.from_jam_bytes(stream)
        if stream.get_remaining_length() or header.to_jam_bytes().to_bytes() != payload[:-36]:
            raise InvalidJAMNPSMessage("malformed block announcement")
        if self.app.retrieve_block_header(header.hash) is None:
            await self.fetch_blocks(protocol, header.hash, 1, 1)

    async def fetch_blocks(self, protocol, header_hash, direction, max_blocks):
        if direction not in (0, 1) or not 0 < max_blocks <= 4096:
            raise InvalidJAMNPSMessage("invalid block request limits")
        response = await protocol.request(128, [header_hash + bytes([direction]) + max_blocks.to_bytes(4, "little")])
        if len(response) != 1:
            raise InvalidJAMNPSMessage("incorrect block response message count")
        stream, blocks = JamBytes(response[0]), []
        while stream.get_remaining_length():
            if len(blocks) >= max_blocks:
                raise InvalidJAMNPSMessage("too many returned blocks")
            block = Block.from_jam_bytes(stream)
            blocks.append(block)
        for index, block in enumerate(blocks):
            if index == 0 and ((direction == 1 and block.header.hash != header_hash)
                               or (direction == 0 and block.header.parent != header_hash)):
                raise InvalidJAMNPSMessage("block response has incorrect anchor")
            if index and ((direction == 1 and blocks[index - 1].header.parent != block.header.hash)
                          or (direction == 0 and block.header.parent != blocks[index - 1].header.hash)):
                raise InvalidJAMNPSMessage("block response is not contiguous")
        if blocks:
            # Keep the existing app subscriber's Vec(Block) representation.
            encoded = Vec(Block.to_codec_def()).encode([block.to_jam_bytes() for block in blocks]).to_bytes()
            await self.broadcaster.publish(PubSubSignal(MESSAGE_TYPES.REQUESTED_BLOCKS, encoded))
        return blocks

    def serve_blocks(self, request):
        if len(request) != 37:
            raise InvalidJAMNPSMessage("invalid block request")
        anchor, direction = request[:32], request[32]
        limit = int.from_bytes(request[33:], "little")
        if direction not in (0, 1) or not 0 < limit <= 4096:
            raise InvalidJAMNPSMessage("invalid block request limits")
        # Restrict requests to the retained canonical branch. Its ancestors
        # remain finalizable under the application's committed-state model.
        head_hash, _ = self._head()
        block, children, seen = self.app.retrieve_block_by_hash(head_hash), [], set()
        while block is not None and block.header.hash != anchor:
            if block.header.hash in seen:
                raise InvalidJAMNPSMessage("cyclic block ancestry")
            seen.add(block.header.hash)
            children.append(block)
            block = self.app.retrieve_block_by_hash(block.header.parent)
        if block is None:
            raise InvalidJAMNPSMessage("requested block is outside the finalizable branch")
        if direction == 0:
            blocks = list(reversed(children))[:limit]
        else:
            blocks = []
            while block is not None and len(blocks) < limit:
                blocks.append(block)
                block = self.app.retrieve_block_by_hash(block.header.parent)
        return b"".join(block.to_jam_bytes().to_bytes() for block in blocks)

    async def request_blocks(self, direction, max_blocks, block_bytes):
        if not self.conn_out:
            raise ConnectionError("no connected block peer")
        protocol = next(iter(self.conn_out.values()))
        await protocol.send_blocks_request(direction, max_blocks, block_bytes)

    async def broadcast_block(self, block):
        encoded = block.to_jam_bytes().to_bytes()
        for protocol in list(self.conn_in.values()):
            await protocol.send_block_announcement(encoded)
