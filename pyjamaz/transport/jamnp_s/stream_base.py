import logging
from enum import Enum


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamType(Enum):
    UP0_BlockAnnouncement: int = 0
    CE128_BlockRequest: int = 128
    CE129_StateRequest: int = 129
    CE131_SafroleTicketDistributionStep1: int = 131
    CE132_SafroleTicketDistributionStep2: int = 132
    CE133_WorkPackageSubmission: int = 133
    CE134_WorkPackageSharing: int = 134
    CE135_WorkReportDistribution: int = 135
    CE136_WorkReportRequest: int = 136
    CE137_ShardDistribution: int = 137
    CE138_AuditShardRequest: int = 138
    CE139_SegmentShardRequest: int = 139
    CE140_SegmentShardRequestJustification: int = 140
    CE141_AssuranceDistribution: int = 141
    # 142
    # 143
    # 144
    # 145


class StreamDirection(Enum):
    initiator: int = 0
    acceptor: int = 1


class Stream:

    #TODO: typings on connection
    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        self.stream_id = stream_id
        self.stream_type = None # Note: override in subclass
        self.conn = connection
        self.protocol = connection.protocol
        self.direction = direction

        self._msg_buffer = b""
        self._msg_len = -1


    def _reset_msg(self):
        self._msg_buffer = b""
        self._msg_len = -1


    def initiator_message(self, data: bytes):
        raise Exception("Override this method in Stream subclass")


    def acceptor_message(self, data: bytes):
        raise Exception("Override this method in Stream subclass")


    def create_message(self, payload: bytes):
        return self.stream_type + (len(payload)).to_bytes(length=4, byteorder='little') + payload


    def receive_data(self, data: bytes):

        # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
        while len(data) > 0:

            if self._msg_len == -1:
                # byte_data = bytes(event.data)
                self._msg_len = int.from_bytes(data[0:4], byteorder='little')
                data = data[4:]
                #print(f"NEW MESSAGE: {self.stream_id} msg length: {len(data)} data length: {self._msg_len}")
                # TODO: check message length > 0???!!!!

            msg_complete = False
            if len(self._msg_buffer) + len(data) >= self._msg_len:
                # If we received a full message (or more than 1 message)
                end_offset = self._msg_len - len(self._msg_buffer)
                self._msg_buffer += data[:end_offset]
                data = data[end_offset:]
                msg_complete = True
                #print(f"FULL MESSAGE RECEIVED {self.stream_type} stream type = {int(self.stream_id)}")
            else:
                # Otherwise append only, we expect more data to finish this message
                self._msg_buffer += data
                data = []
                print(f"APPENDING TO EXISTING MESSAGE: {self.stream_id} msg length: {len(data)} data length: {self._msg_len}")

            # If we assembled a new message, parse it
            if msg_complete:
                try:
                    if self.direction == StreamDirection.initiator:
                        self.initiator_message(self._msg_buffer)
                    else:
                        self.acceptor_message(self._msg_buffer)
                finally:
                    self._reset_msg()


    def initiator_reset(self, reset_code: int):
        self.conn.close_jam_stream(self)


    def acceptor_reset(self, reset_code: int):
        self.conn.close_jam_stream(self)
