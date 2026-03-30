from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import (
    MsgCE140Justification,
    MsgCE140SegmentRequest,
    MsgCE140SegmentShard,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE140Handler(ContextualStreamHandler):
    kind = StreamKind.CE140_SegmentShardRequestJustification

    def initiate_request(self, conn, req: MsgCE140SegmentRequest) -> ManagedStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE140 initiator received shards and justifications")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE140 acceptor received request")
        msg = MsgCE140SegmentRequest.from_jam_bytes(JamBytes(data))
        for idx in msg.segment_indices:
            shard = MsgCE140SegmentShard(bytes_=b"")
            just = MsgCE140Justification(bytes_=b"")
            stream.conn.send(
                stream.stream_id,
                stream.create_message(shard.to_jam_bytes().to_bytes()),
                end_stream=False,
            )
            stream.conn.send(
                stream.stream_id,
                stream.create_message(just.to_jam_bytes().to_bytes()),
                end_stream=(idx == msg.segment_indices[-1]),
            )

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("CE140 success with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("CE140 success with FIN")
