import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE140SegmentRequest, MsgCE140SegmentShard, MsgCE140Justification
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamSegmentShardRequestJustification(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE140_SegmentShardRequestJustification.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE140 received reset code: {reset_code}")
        self.protocol.ce140_request_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        logger.debug(f"CE140 initiator received shards and justifications")
        # Parse shards and per-shard justifications
        self.protocol.ce140_received_shards_justified(self, data)  # Simplified


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE140 acceptor received request")
        msg = MsgCE140SegmentRequest.from_jam_bytes(JamBytes(data))
        self.protocol.ce140_received_request(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce140_request_success(0)