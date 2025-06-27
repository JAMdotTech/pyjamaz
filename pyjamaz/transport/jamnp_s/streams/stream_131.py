from pyjamaz.transport.jamnp_s.stream import Stream, StreamType, StreamDirection


class StreamSafroleTicketDistributionStep1(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE131_SafroleTicketDistributionStep1.value.to_bytes(length=1, byteorder='little')

    def initiate_state_request(self, header_hash, direction, max_blocks):
        pass


    def initiator_message(self, data: bytes):
        # Note: Sends message to one specific deterministic validator
        pass


    def acceptor_message(self, data: bytes):
        pass