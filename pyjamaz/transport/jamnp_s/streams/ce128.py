from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List

from jamcodec.base import JamBytes

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block, Header
from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import (
    MsgCE128BlockRequest,
    MsgCE128BlockRequestDirection,
    MsgCE128BlockRequestResponse,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE128StreamState:
    active: bool = True


class CE128Handler(ContextualStreamHandler):
    kind = StreamKind.CE128_BlockRequest

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE128StreamState()

    def initiate_block_request(self, conn, req: MsgCE128BlockRequest) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(
            f"Initiate block request on stream id: {stream.stream_id} direction: {req.direction}, "
            f"max_block: {req.max_blocks} header hash: {req.header_hash}"
        )
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    async def finish_block_request(self, *args, **kwargs) -> None:
        self.context.state_requesting_blocks = False

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug(
            f"CE128 initiated stream {stream.stream_id} received block request response: {len(data)} bytes"
        )
        req = MsgCE128BlockRequestResponse.from_jam_bytes(JamBytes(data))
        blocks = req.blocks
        logger.info(f"Parsed {len(blocks)} blocks")
        asyncio.create_task(
            self.context.app.import_queue_add_blocks(
                blocks,
                on_success=MESSAGE_TYPES.CE128_SUCCESS,
                on_failure=MESSAGE_TYPES.CE128_FAILURE,
            )
        )

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug(f"CE128 acceptor stream {stream.stream_id} received block request")
        self._send_block_request_response(
            stream,
            MsgCE128BlockRequest.from_jam_bytes(JamBytes(data)),
        )

    def initiator_fin(self, stream: ManagedStream) -> None:
        self._abort_block_request()

    def acceptor_fin(self, stream: ManagedStream) -> None:
        self._abort_block_request()

    def initiator_reset(self, stream: ManagedStream, reset_code: int) -> None:
        asyncio.create_task(self.finish_block_request(reset_code))

    def acceptor_reset(self, stream: ManagedStream, reset_code: int) -> None:
        asyncio.create_task(self.finish_block_request(reset_code))

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)

    def _send_block_request_response(self, stream: ManagedStream, block_req: MsgCE128BlockRequest) -> None:
        block: Block = None
        blocks: List[Block] = []
        last_block_hash = self.context.app.retrieve_block_hash(self.context.app.working_state.timeslot.number)
        block_header: Header = self.context.app.retrieve_block_header(block_req.header_hash)
        next_hash = block_req.header_hash

        if block_header and block_req.max_blocks > 0:
            for _ in range(block_req.max_blocks):
                if block_req.direction == MsgCE128BlockRequestDirection.ASC.value:
                    block_child_hash: bytes = self.context.app.retrieve_block_child_hash(next_hash)
                    if block_child_hash:
                        block = self.context.app.retrieve_block_by_hash(block_child_hash)
                        next_hash = block.header.hash
                    else:
                        break
                elif block_req.direction == MsgCE128BlockRequestDirection.DESC.value:
                    block = self.context.app.retrieve_block_by_hash(next_hash)
                    if not block or block.header.timeslot == 0 or block.header.hash == bytes(32):
                        break
                    next_hash = block.header.parent
                else:
                    raise RuntimeError("Unsupported CE128 block request direction")

                blocks.append(block)

        if blocks:
            logger.info(
                f"Send {len(blocks)} blocks (direction={block_req.direction} max blocks={block_req.max_blocks})"
            )
            stream.conn.send(
                stream.stream_id,
                stream.create_message(MsgCE128BlockRequestResponse(blocks=blocks).to_jam_bytes().to_bytes()),
                end_stream=True,
            )
            return

        logger.info(
            f"No blocks to send requested: {block_req.header_hash.hex()} current: {last_block_hash.hex()}"
        )
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def _abort_block_request(self) -> None:
        logger.info(f"Finished, start parsing import queue {len(self.context.app.import_queue)}")
        asyncio.create_task(
            self.context.app.process_import_queue(
                on_success=MESSAGE_TYPES.CE128_SUCCESS,
                on_failure=MESSAGE_TYPES.CE128_FAILURE,
            )
        )
