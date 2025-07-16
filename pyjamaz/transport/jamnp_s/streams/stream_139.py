import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE139SegmentRequest, MsgCE139SegmentShard
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamSegmentShardRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE139_SegmentShardRequest.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE139 received reset code: {reset_code}")
        self.protocol.ce139_request_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        logger.debug(f"CE139 initiator received shards")
        shards = [MsgCE139SegmentShard.from_jam_bytes(JamBytes(d)) for d in chunks(data, 4104 // R)]  # R from spec
        self.protocol.ce139_received_shards(self, shards)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE139 acceptor received request")
        msg = MsgCE139SegmentRequest.from_jam_bytes(JamBytes(data))
        self.protocol.ce139_received_request(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce139_request_success(0)