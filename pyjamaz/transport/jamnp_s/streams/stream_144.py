import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE144Announcement, MsgCE144Evidence
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamAuditAnnouncement(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE144_AuditAnnouncement.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.received_announcement = False


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE144 received reset code: {reset_code}")
        self.protocol.ce144_announcement_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        logger.warning(f"Unexpected data in CE144 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_message(self, data: bytes):
        if not self.received_announcement:
            logger.debug(f"CE144 acceptor received announcement")
            msg = MsgCE144Announcement.from_jam_bytes(JamBytes(data))
            self.protocol.ce144_received_announcement(self, msg)
            self.received_announcement = True
        else:
            logger.debug(f"CE144 acceptor received evidence")
            msg = MsgCE144Evidence.from_jam_bytes(JamBytes(data))
            self.protocol.ce144_received_evidence(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce144_announcement_success(0) 