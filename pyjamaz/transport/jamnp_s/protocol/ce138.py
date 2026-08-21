from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce138 import (
    MsgCE138BundleShard,
    MsgCE138Justification,
    MsgCE138ShardRequest,
)
from pyjamaz.transport.jamnp_s.types import JAMStream, JAMStreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE138Handler(StreamHandler):
    kind = JAMStreamKind.CE138_AuditShardRequest

    def initiate_request(self, conn, req: MsgCE138ShardRequest) -> JAMStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE138 initiator received response")
        bundle = MsgCE138BundleShard.from_jam_bytes(JamBytes(data[: len(data) // 2]))
        just = MsgCE138Justification.from_jam_bytes(JamBytes(data[len(data) // 2 :]))
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE138 acceptor received request")
        MsgCE138ShardRequest.from_jam_bytes(JamBytes(data))
        bundle = MsgCE138BundleShard(bytes_=b"")
        just = MsgCE138Justification(bytes_=b"")
        stream.conn.send(
            stream.stream_id,
            stream.create_message(bundle.to_jam_bytes().to_bytes()),
            end_stream=False,
        )
        stream.conn.send(
            stream.stream_id,
            stream.create_message(just.to_jam_bytes().to_bytes()),
            end_stream=True,
        )

    def initiator_fin(self, stream: JAMStream) -> None:
        logger.info("CE138 success FIN")

    def acceptor_fin(self, stream: JAMStream) -> None:
        logger.info("CE138 success FIN")
