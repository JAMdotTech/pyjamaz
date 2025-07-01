from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection


class StreamSafroleTicketDistributionStep2(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE132_SafroleTicketDistributionStep2.value.to_bytes(length=1, byteorder='little')

    def initiate_state_request(self, header_hash, direction, max_blocks):
        # Note: Sends message to all current validators
        pass


    def initiator_message(self, data: bytes):
        pass


    def acceptor_message(self, data: bytes):
        pass