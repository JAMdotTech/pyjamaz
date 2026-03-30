from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import MsgCE141Assurance
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE141Handler(ContextualStreamHandler):
    kind = StreamKind.CE141_AssuranceDistribution

    def initiate_distribution(self, conn, msg: MsgCE141Assurance) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"Initiating assurance distribution on stream id: {stream.stream_id} to {conn.host}:{conn.port}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE141 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE141 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE141 acceptor received assurance")
        MsgCE141Assurance.from_jam_bytes(JamBytes(data))
        logger.info("Received assurance")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with code with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with code with FIN")
