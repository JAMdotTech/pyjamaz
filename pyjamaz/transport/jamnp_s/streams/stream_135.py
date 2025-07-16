import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE135GuaranteedWorkReport
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamWorkReportDistribution(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE135_WorkReportDistribution.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE135 received reset code: {reset_code}")
        self.protocol.ce135_distribution_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        logger.warning(f"Unexpected data in CE135 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_reset(self, reset_code: int):
        self.protocol.ce135_distribution_failure(reset_code)
        super().reset(reset_code)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE135 acceptor received work report")
        msg = MsgCE135GuaranteedWorkReport.from_jam_bytes(JamBytes(data))
        self.protocol.ce135_received_report(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce135_distribution_success(0)