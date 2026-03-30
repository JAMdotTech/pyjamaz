from __future__ import annotations

import logging
from dataclasses import dataclass

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import MsgCE144Announcement, MsgCE144Evidence
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE144StreamState:
    received_announcement: bool = False


class CE144Handler(ContextualStreamHandler):
    kind = StreamKind.CE144_AuditAnnouncement

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE144StreamState()

    def initiate_announcement(
        self,
        conn,
        ann: MsgCE144Announcement,
        evidence: MsgCE144Evidence,
    ) -> ManagedStream:
        stream = self.open_outgoing(conn)
        conn.send(
            stream.stream_id,
            stream.create_message(ann.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=False,
        )
        conn.send(
            stream.stream_id,
            stream.create_message(evidence.to_jam_bytes().to_bytes()),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE144 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE144 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        state = self._streams[stream.stream_key]

        if not state.received_announcement:
            logger.debug("CE144 acceptor received announcement")
            MsgCE144Announcement.from_jam_bytes(JamBytes(data))
            state.received_announcement = True
            return

        logger.debug("CE144 acceptor received evidence")
        MsgCE144Evidence.from_jam_bytes(JamBytes(data))
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("CE144 success with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("CE144 success with FIN")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)
