from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce137 import (
    MsgCE137BundleShard,
    MsgCE137Justification,
    MsgCE137SegmentShard,
    MsgCE137ShardRequest,
)
from pyjamaz.transport.jamnp_s.types import JAMStream, JAMStreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE137Handler(StreamHandler):
    kind = JAMStreamKind.CE137_ShardDistribution

    def initiate_request(self, conn, req: MsgCE137ShardRequest) -> JAMStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    @staticmethod
    def _chunks(data: bytes, chunk_size: int):
        for idx in range(0, len(data), chunk_size):
            yield data[idx : idx + chunk_size]

    def initiator_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE137 initiator received response")
        bundle = MsgCE137BundleShard.from_jam_bytes(JamBytes(data[: len(data) // 3]))
        segments = [
            MsgCE137SegmentShard.from_jam_bytes(JamBytes(chunk))
            for chunk in self._chunks(data, max(1, len(data) // 3))
        ]
        just = MsgCE137Justification.from_jam_bytes(JamBytes(data[-len(data) // 3 :]))
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE137 acceptor received request")
        MsgCE137ShardRequest.from_jam_bytes(JamBytes(data))
        bundle = MsgCE137BundleShard(bytes_=b"")
        segments = [MsgCE137SegmentShard(bytes_=b"") for _ in range(10)]
        just = MsgCE137Justification(bytes_=b"")
        stream.conn.send(
            stream.stream_id,
            stream.create_message(bundle.to_jam_bytes().to_bytes()),
            end_stream=False,
        )
        for segment in segments:
            stream.conn.send(
                stream.stream_id,
                stream.create_message(segment.to_jam_bytes().to_bytes()),
                end_stream=False,
            )
        stream.conn.send(
            stream.stream_id,
            stream.create_message(just.to_jam_bytes().to_bytes()),
            end_stream=True,
        )

    def initiator_fin(self, stream: JAMStream) -> None:
        logger.info("CE137 success with FIN")

    def acceptor_fin(self, stream: JAMStream) -> None:
        logger.info("CE137 success with FIN")
