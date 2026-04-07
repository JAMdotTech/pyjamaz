from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce145 import MsgCE145JudgmentPublication
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE145Handler(StreamHandler):
    kind = StreamKind.CE145_JudgmentPublication

    def initiate_publication(self, conn, msg: MsgCE145JudgmentPublication) -> ManagedStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE145 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE145 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE145 acceptor received judgment")
        MsgCE145JudgmentPublication.from_jam_bytes(JamBytes(data))
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("CE145 success with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("CE145 success with FIN")
