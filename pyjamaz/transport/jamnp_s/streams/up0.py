from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.connection import JAMConnectionDirection
from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import (
    MsgCE128BlockRequest,
    MsgCE128BlockRequestDirection,
    MsgUP0Announcement,
    MsgUP0Handshake,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamDirection, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class UPState(enum.Enum):
    IN_PROGRESS = 0
    CONNECTED = 1


@dataclass
class UP0StreamState:
    phase: UPState = UPState.IN_PROGRESS


class UP0Handler(ContextualStreamHandler):
    kind = StreamKind.UP0_BlockAnnouncement

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = UP0StreamState()

    def send_handshake(self, conn) -> None:
        slot = self.context.app.working_state.timeslot.number
        header_hash = self.context.app.retrieve_block_hash(slot)
        handshake = MsgUP0Handshake(
            header_hash=header_hash,
            timeslot=slot,
            leafs=[],
        )
        logger.info(
            f"Send handshake on stream {conn.stream_up.stream_id} to {conn.host}:{conn.port} with hash {header_hash}"
        )

        conn.send(
            conn.stream_up.stream_id,
            conn.stream_up.create_message(
                handshake.to_jam_bytes().to_bytes(),
                add_stream_type=conn.direction == JAMConnectionDirection.initiator,
            ),
        )

    async def broadcast_block(self, block) -> None:
        logger.info(f"Broadcast {block.header.hash.hex()} to {len(self.context.connections)} connections")

        payload = MsgUP0Announcement(
            header=block.header,
            header_hash=block.header.hash,
            timeslot=block.header.timeslot,
        ).to_jam_bytes().to_bytes()

        for conn in self.context.connections.values():
            if not conn.is_connected():
                logger.debug(
                    f"Skipping broadcast to {conn.host}:{conn.port} - connection is not fully established yet"
                )
                continue

            logger.debug(f"Send block header to client {conn.host}:{conn.port} with hash {block.header.hash.hex()}")
            conn.send(
                conn.stream_up.stream_id,
                conn.stream_up.create_message(payload),
                end_stream=False,
            )

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        self._receive_message(stream, data)

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        self._receive_message(stream, data)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.warning(f"Unexpected FIN on persistent UP0 stream {stream.stream_id}")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.warning(f"Unexpected FIN on persistent UP0 stream {stream.stream_id}")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)

    def _receive_message(self, stream: ManagedStream, data: bytes) -> None:
        state = self._streams[stream.stream_key]

        if state.phase == UPState.IN_PROGRESS:
            state.phase = UPState.CONNECTED
            msg = MsgUP0Handshake.from_jam_bytes(JamBytes(data))
            self._handle_handshake(stream, msg)
            return

        if state.phase == UPState.CONNECTED:
            msg = MsgUP0Announcement.from_jam_bytes(JamBytes(data))
            self._handle_announcement(stream.conn, msg)
            return

        raise RuntimeError(f"Unexpected state {state.phase}")

    def _handle_handshake(self, stream: ManagedStream, msg: MsgUP0Handshake) -> None:
        if stream.direction == StreamDirection.acceptor:
            self.send_handshake(stream.conn)

        if self.context.state_requesting_blocks:
            logger.debug("Skipping handshake block header check, already importing blocks")
            return

        block = self.context.app.retrieve_block_by_hash(msg.header_hash)
        if block:
            return

        logger.info(f"Received newer block from handshake: {msg.header_hash} -> initiate CE128RequestBlocks")
        self._initiate_block_sync(stream.conn, msg.header_hash)

    def _handle_announcement(self, conn, msg: MsgUP0Announcement) -> None:
        if self.context.state_requesting_blocks:
            logger.debug("Skipping block header announcement check, already importing blocks")
            return

        block = self.context.app.retrieve_block_by_hash(msg.header.hash)
        if block:
            return

        logger.info(f"Received new block announcement from up0: {msg.header.hash}")
        self._initiate_block_sync(conn, announced_hash=msg.header.hash)

    def _initiate_block_sync(self, conn, announced_hash: bytes) -> None:
        self.context.state_requesting_blocks = True
        curr_hash = self.context.app.retrieve_block_hash(self.context.app.working_state.timeslot.number)
        ce128_handler = self.context.get_handler(StreamKind.CE128_BlockRequest)
        ce128_handler.initiate_block_request(
            conn,
            MsgCE128BlockRequest(
                curr_hash,
                MsgCE128BlockRequestDirection.ASC.value,
                10,
            ),
        )
