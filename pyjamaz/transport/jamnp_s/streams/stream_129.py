from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection


class StreamStateRequest(Stream):

    BOUNDARY_NODE = 0
    KEY_VALUE = 1

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE129_StateRequest.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.state = self.BOUNDARY_NODE


    def initiate_state_request(self, header_hash, direction, max_blocks):
        pass


    def initiator_message(self, data: bytes):
        if self.state == self.BOUNDARY_NODE:
            pass
        elif self.state == self.KEY_VALUE:
            pass


    def acceptor_message(self, data: bytes):
        pass