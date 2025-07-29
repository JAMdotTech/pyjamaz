import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE136HashRequest, MsgCE136WorkReport
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamWorkReportRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE136_WorkReportRequest.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        pass


    def initiator_message(self, data: bytes):
        logger.debug(f"CE136 initiator received work report")
        msg = MsgCE136WorkReport.from_jam_bytes(JamBytes(data))
        self.protocol.ce136_received_report(self, msg)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE136 acceptor received request")
        msg = MsgCE136HashRequest.from_jam_bytes(JamBytes(data))
        self.protocol.ce136_received_request(self, msg)


    def acceptor_reset(self, reset_code: int):
        pass


    def handle_fin(self):
        super().handle_fin()
        logger.debug(f"CE136 request successful with FIN")