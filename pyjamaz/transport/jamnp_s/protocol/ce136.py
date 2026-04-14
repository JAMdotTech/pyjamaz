from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce136 import MsgCE136HashRequest, MsgCE136WorkReport
from pyjamaz.transport.jamnp_s.types import JAMStream, JAMStreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE136Handler(StreamHandler):
    kind = JAMStreamKind.CE136_WorkReportRequest

    def initiate_request(self, conn, msg: MsgCE136HashRequest) -> JAMStream:
        stream = self.open_outgoing(conn)
        logger.info(f"CE136 initiating request on stream id: {stream.stream_id}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE136 initiator received work report")
        msg = MsgCE136WorkReport.from_jam_bytes(JamBytes(data))
        logger.info(f"CE136 received work report of length {len(msg.report)}")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: JAMStream, data: bytes) -> None:
        logger.debug("CE136 acceptor received request")
        msg = MsgCE136HashRequest.from_jam_bytes(JamBytes(data))
        logger.info(f"CE136 received request for hash {msg.hash.hex()}")
        report = MsgCE136WorkReport(report=b"")
        stream.conn.send(
            stream.stream_id,
            stream.create_message(report.to_jam_bytes().to_bytes()),
            end_stream=True,
        )

    def initiator_fin(self, stream: JAMStream) -> None:
        logger.debug("CE136 request successful with FIN")

    def acceptor_fin(self, stream: JAMStream) -> None:
        logger.debug("CE136 request successful with FIN")
