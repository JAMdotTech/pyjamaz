from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce139 import (
    MsgCE139SegmentRequest,
    MsgCE139SegmentShard,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE139Handler(StreamHandler):
    kind = StreamKind.CE139_SegmentShardRequest

    def initiate_request(self, conn, req: MsgCE139SegmentRequest) -> ManagedStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE139 initiator received shards")
        chunk_size = max(1, len(data))
        [
            MsgCE139SegmentShard.from_jam_bytes(JamBytes(chunk))
            for chunk in self._chunks(data, chunk_size)
        ]
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE139 acceptor received request")
        msg = MsgCE139SegmentRequest.from_jam_bytes(JamBytes(data))
        shards = [MsgCE139SegmentShard(bytes_=b"") for _ in msg.segment_indices]
        for shard in shards:
            stream.conn.send(
                stream.stream_id,
                stream.create_message(shard.to_jam_bytes().to_bytes()),
                end_stream=(shard == shards[-1]),
            )

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("CE139 success with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("CE139 success with FIN")

    @staticmethod
    def _chunks(data: bytes, chunk_size: int):
        for idx in range(0, len(data), chunk_size):
            yield data[idx : idx + chunk_size]
