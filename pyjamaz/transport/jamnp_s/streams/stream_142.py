import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE142PreimageAnnouncement
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamPreimageAnnouncement(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE142_PreimageAnnouncement.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        pass


    def initiator_message(self, data: bytes):
        if len(data) == 0:
            return
        logger.warning(f"Unexpected data in CE142 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_reset(self, reset_code: int):
        pass


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE142 acceptor received preimage announcement")
        msg = MsgCE142PreimageAnnouncement.from_jam_bytes(JamBytes(data))
        self.protocol.ce142_received_announcement(self, msg)


    def handle_fin(self):
        super().handle_fin()
        logger.info(f"Success with code with FIN")