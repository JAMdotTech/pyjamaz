import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE138ShardRequest, MsgCE138BundleShard, MsgCE138Justification
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamAuditShardRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE138_AuditShardRequest.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        pass


    def initiator_message(self, data: bytes):
        logger.debug(f"CE138 initiator received response")
        bundle = MsgCE138BundleShard.from_jam_bytes(JamBytes(data[:len(data)//2]))
        just = MsgCE138Justification.from_jam_bytes(JamBytes(data[len(data)//2:]))
        self.protocol.ce138_received_shard(self, bundle, just)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE138 acceptor received request")
        msg = MsgCE138ShardRequest.from_jam_bytes(JamBytes(data))
        self.protocol.ce138_received_request(self, msg)


    def acceptor_reset(self, reset_code: int):
        pass


    def handle_fin(self):
        super().handle_fin()
        logger.info(f"CE138 success FIN")