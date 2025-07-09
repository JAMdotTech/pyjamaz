import enum
import logging

from jamcodec.base import JamBytes
from jamcodec.types import U32, VarInt64

from pyjamaz.transport.jamnp_s.message_types import MsgUP0Handshake, MsgUP0Leaf, MsgUP0Announcement
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class UPState(enum.Enum):
    IN_PROGRESS = 0
    CONNECTED = 1


class StreamUP(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.UP0_BlockAnnouncement.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.state = UPState.IN_PROGRESS


    def initiator_message(self, data: bytes):

        match self.state:

            case UPState.IN_PROGRESS:
                self.state = UPState.CONNECTED

                msg = MsgUP0Handshake.from_jam_bytes(JamBytes(data))
                self.protocol.up0_received_handshake(self.conn, msg)

            case UPState.CONNECTED:
                # After handshake is completed, we receive Announcement messages
                msg  = MsgUP0Announcement.from_jam_bytes(JamBytes(data))
                self.protocol.up0_received_announcement(self.conn, msg)

            case _:
                raise RuntimeError(f"Unexpected state {self.state}")


    def acceptor_message(self, data: bytes):
        # Note: in case of UP0, initiator and acceptor have symmetrical message flow
        self.initiator_message(data)
