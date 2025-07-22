import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE137ShardRequest, MsgCE137BundleShard, MsgCE137SegmentShard, MsgCE137Justification
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamShardDistribution(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE137_ShardDistribution.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE137 received reset code: {reset_code}")
        self.protocol.ce137_distribution_failure(reset_code)


    def _chunks(self, data: bytes, chunk_size: int):
        """Yield successive n-sized chunks from data."""
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]


    def initiator_message(self, data: bytes):
        logger.debug(f"CE137 initiator received response")
        # Parse bundle shard, segment shards, justification
        bundle = MsgCE137BundleShard.from_jam_bytes(JamBytes(data[:len(data)//3]))  # Simplified parsing
        segments = [MsgCE137SegmentShard.from_jam_bytes(JamBytes(d)) for d in self._chunks(data, len(data)//3)]
        just = MsgCE137Justification.from_jam_bytes(JamBytes(data[-len(data)//3:]))
        self.protocol.ce137_received_shard(self, bundle, segments, just)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE137 acceptor received request")
        msg = MsgCE137ShardRequest.from_jam_bytes(JamBytes(data))
        self.protocol.ce137_received_request(self, msg)


    def acceptor_reset(self, reset_code: int):
        logger.debug(f"CE137 received reset code: {reset_code}")
        self.protocol.ce137_distribution_failure(reset_code)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce137_distribution_success(0)