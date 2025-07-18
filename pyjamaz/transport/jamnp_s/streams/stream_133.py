import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE133WorkPackageSubmission, MsgCE133Extrinsic
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamWorkPackageSubmission(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE133_WorkPackageSubmission.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.received_wp = False


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE133 received reset code: {reset_code}")
        self.protocol.ce133_submission_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        logger.warning(f"Unexpected data in CE133 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_reset(self, reset_code: int):
        self.protocol.ce133_submission_failure(reset_code)
        super().reset(reset_code)


    def acceptor_message(self, data: bytes):
        if not self.received_wp:
            logger.debug(f"CE133 acceptor received work package")
            msg = MsgCE133WorkPackageSubmission.from_jam_bytes(JamBytes(data))
            self.protocol.ce133_received_workpackage_submission(self, msg)
            self.received_wp = True
        else:
            logger.debug(f"CE133 acceptor received extrinsic data")
            msg = MsgCE133Extrinsic.from_jam_bytes(JamBytes(data))
            self.protocol.ce133_received_extrinsic_submission(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce133_submission_success(0)