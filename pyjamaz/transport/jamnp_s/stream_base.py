import logging
from enum import Enum
from typing import Optional

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
    CE142_PreimageAnnouncement: int = 142
    CE143_PreimageRequest: int = 143
    CE144_PreimageAnnouncement: int = 144
    # 145


class StreamDirection(Enum):
    initiator: int = 0
    acceptor: int = 1


class Stream:

    # Standard reset codes
    ERROR_GENERAL = 1
    ERROR_INVALID_MESSAGE = 2
    ERROR_INVALID_SIZE = 3
    ERROR_TOO_LARGE = 4
    ERROR_VALIDATION_FAILED = 5

    #TODO: typings on connection
    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        self.stream_id = stream_id
        self.stream_type = None  # Note: override in subclass
        self.stream_type_byte = None # Note: override in subclass
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


    def create_message(self, payload: bytes, add_stream_type:bool=False):
        if add_stream_type:
            # Initial messages over a new stream should de prefixed with a stream type byte
            return self.stream_type_byte + (len(payload)).to_bytes(length=4, byteorder='little') + payload
        else:
            return (len(payload)).to_bytes(length=4, byteorder='little') + payload


    def receive_data(self, data: bytes, end_stream: bool = False):
        try:
            # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
            while len(data) > 0:

                if self._msg_len == -1:
                    # byte_data = bytes(event.data)
                    self._msg_len = int.from_bytes(data[0:4], byteorder='little')
                    data = data[4:]
                    logger.debug(f"Received new message for stream {self.stream_id} with a msg length: {self._msg_len} ({len(data)} received)")
                    # TODO: check message length > 0???!!!!
                    if self._msg_len <= 0:
                        logger.error(f"Message size <= 0 for stream {self.stream_id} {self._msg_len}")
                        self.reset(self.ERROR_INVALID_SIZE)

                    # Add max size check
                    if self._msg_len > self.protocol.MAX_MESSAGE_SIZE:
                        logger.error(f"Message too large for stream {self.stream_id}")
                        self.reset(self.ERROR_TOO_LARGE)
                        return

                msg_complete = False
                if len(self._msg_buffer) + len(data) >= self._msg_len:
                    # If we received a full message (or more than 1 message)
                    end_offset = self._msg_len - len(self._msg_buffer)
                    self._msg_buffer += data[:end_offset]
                    data = data[end_offset:] # Note: this packet could contain start of a new message
                    msg_complete = True
                else:
                    # Otherwise append only, we expect more data to finish this message
                    self._msg_buffer += data
                    logger.debug(f"Appending to message for stream {self.stream_id} ({self._msg_buffer} bytes of {self._msg_len})")
                    data = [] # Note: no new packet can be present in this data

                # If we assembled a new message, parse it
                if msg_complete:
                    logger.debug(f"Message complete for stream {self.stream_id}")
                    try:
                        if self.direction == StreamDirection.initiator:
                            self.initiator_message(self._msg_buffer)
                        else:
                            self.acceptor_message(self._msg_buffer)
                    except Exception as e:
                        self.handle_error(e)
                    finally:
                        self._reset_msg()

            if end_stream:
                logger.debug(f"Received FIN on stream {self.stream_id}")
                self.handle_fin()

        except Exception as e:
            self.handle_error(e)


    def handle_error(self, exc: Exception):
        if isinstance(exc, ValueError):
            code = self.ERROR_INVALID_MESSAGE
        elif isinstance(exc, MemoryError):
            code = self.ERROR_TOO_LARGE
        else:
            code = self.ERROR_GENERAL
        logger.error(f"Stream {self.stream_id} error: {exc}")
        self.reset(code)


    def handle_fin(self):
        self.conn.close_jam_stream(self, clean_close=True)


    def reset(self, reset_code: int):
        if self.direction == StreamDirection.initiator:
            self.initiator_reset(reset_code)
        else:
            self.acceptor_reset(reset_code)
        self.conn.close_jam_stream(self, reason=reset_code, clean_close=False)


    def initiator_reset(self, reset_code: int):
        self.conn.close_jam_stream(self)


    def acceptor_reset(self, reset_code: int):
        self.conn.close_jam_stream(self)
