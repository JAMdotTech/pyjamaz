import logging
from enum import Enum


logger = logging.getLogger("pyjamaz.transport.jamnp_s.streams")


class InvalidStreamType(Exception):
    pass


class StreamType(Enum):
    UP0_BlockAnnouncement: int = 0
    CE128_BlockRequest: int = 128
    # 129
    # 131
    # 132
    # 133
    # 134
    # 135
    # 136
    # 137
    # 138
    # 139
    # 140
    # 141
    # 142
    # 143
    # 144
    # 145


class Stream:

    #TODO: typings, and is it really necesary to pass these here?
    def __init__(self, stream_id: int, connection):
        self.stream_id = stream_id
        self.stream_type = None # Note: override in subclass
        self.conn = connection

        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1
        self._msg_offset = -1


    def _reset_msg(self):
        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1
        self._msg_offset = -1


    def parse_message(self, data: bytes):
        raise Exception("Implement this method")


    def receive_data(self, data: bytes):

        # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
        while len(data) > 0:

            if self._msg_len == -1:
                # byte_data = bytes(event.data)
                self._msg_len = int.from_bytes(data[0:4], byteorder='little')
                data = data[4:]
                print(f"NEW MESSAGE: {self.stream_id} msg length: {len(data)} data length: {self._msg_len}")
                # TODO: check message length > 0???!!!!


            parse_message = False
            if len(self._msg_buffer) + len(data) >= self._msg_len:
                # If we received a full message (or more than 1 message)
                end_offset = self._msg_len - len(self._msg_buffer)
                self._msg_buffer += data[:end_offset]
                data = data[end_offset:]
                parse_message = True
                print("FULL MESSAGE RECEIVED")
            else:
                # Otherwise append only, we expect more data to finish this message
                self._msg_buffer += data
                data = []
                print(f"APPENDING TO EXISTING MESSAGE: {self.stream_id} msg length: {len(data)} data length: {self._msg_len}")

            # If we assembled a new message, parse it
            if parse_message:
                try:
                    self.parse_message(self._msg_buffer)
                finally:
                    self._reset_msg()
