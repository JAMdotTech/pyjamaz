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
        self.stream_type = StreamType.UP0_BlockAnnouncement.value.to_bytes(length=1, byteorder='little')
        self.state = UPState.IN_PROGRESS


    def initiator_message(self, data: bytes):

        match self.state:

            case UPState.IN_PROGRESS:
                self.state = UPState.CONNECTED

                #msg = MsgUP0Handshake.from_jam_bytes(JamBytes(data))
                ############################
                #TODO:FIX!!!!!! zie hierboven
                header_hash = data[:32] #.hex()
                slot = int.from_bytes(data[32:36], byteorder='little')

                jam_bytes = JamBytes(data[36:])
                leaf_count = VarInt64.decode(jam_bytes)

                logger.debug(f"Received handshake response: header_hash={header_hash} slot={slot} leaf_count={leaf_count}")

                leafs = []
                for leaf_nr in range(leaf_count):
                    leaf_hash = jam_bytes.get_next_bytes(32) #.hex()
                    leaf_slot = U32.decode(jam_bytes)
                    leafs.append(MsgUP0Leaf(leaf_hash, leaf_slot))
                msg = MsgUP0Handshake(
                    header_hash=header_hash,
                    timeslot=slot,
                    leafs=leafs
                )
                ############################################

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
