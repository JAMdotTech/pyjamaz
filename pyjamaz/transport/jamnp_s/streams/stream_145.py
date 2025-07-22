import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE145JudgmentPublication
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamJudgmentPublication(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE145_JudgmentPublication.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE145 received reset code: {reset_code}")
        self.protocol.ce145_publication_failure(reset_code)


    def initiator_message(self, data: bytes):
        logger.warning(f"Unexpected data in CE145 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE145 acceptor received judgment")
        msg = MsgCE145JudgmentPublication.from_jam_bytes(JamBytes(data))
        self.protocol.ce145_received_judgment(self, msg)


    def acceptor_reset(self, reset_code: int):
        logger.debug(f"CE145 received reset code: {reset_code}")
        self.protocol.ce145_publication_failure(reset_code)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce145_publication_success(0) 