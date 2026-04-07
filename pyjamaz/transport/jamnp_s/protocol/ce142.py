from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce142 import MsgCE142PreimageAnnouncement
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE142Handler(StreamHandler):
    kind = StreamKind.CE142_PreimageAnnouncement

    def initiate_announcement(self, conn, msg: MsgCE142PreimageAnnouncement) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"Initiating preimage announcement on stream id: {stream.stream_id} to {conn.host}:{conn.port}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        if len(data) == 0:
            return
        logger.warning(f"Unexpected data in CE142 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE142 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE142 acceptor received preimage announcement")
        msg = MsgCE142PreimageAnnouncement.from_jam_bytes(JamBytes(data))
        logger.info(f"Received preimage announcement for hash {msg.hash.hex()}")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with code with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with code with FIN")
