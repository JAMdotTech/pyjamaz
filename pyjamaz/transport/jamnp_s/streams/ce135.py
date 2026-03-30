from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import MsgCE135GuaranteedWorkReport
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE135Handler(ContextualStreamHandler):
    kind = StreamKind.CE135_WorkReportDistribution

    def initiate_distribution(self, conn, msg: MsgCE135GuaranteedWorkReport) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"CE135 initiating distribution on stream id: {stream.stream_id}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE135 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE135 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE135 acceptor received work report")
        MsgCE135GuaranteedWorkReport.from_jam_bytes(JamBytes(data))
        logger.info("CE135 received work report")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("CE135 distribution successful with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("CE135 distribution successful with FIN")
