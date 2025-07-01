import asyncio

from jamcodec.base import JamBytes
from jamcodec.types import U32, VarInt64

from pyjamaz.constants import MESSAGE_TYPES

from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection
from pyjamaz.transport.pubsub import PubSubSignal


class StreamUP(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.UP0_BlockAnnouncement.value.to_bytes(length=1, byteorder='little')
        self.handshake_complete = False


    def initiator_handshake(self):
        """
        TODO:
        Both sides should begin by sending a handshake message containing all known leaves (descendants of the latest finalized block with no known children).
        The header hash and slot of the latest finalized block should be included in the handshake message and also in every announcement message that is sent.
        """
        bl_hash = self.conn.protocol.app.retrieve_block_hash(0)
        bl_ts = int(0).to_bytes(length=4, byteorder='little') #self.conn.protocol.app.state.timeslot.number
        final = bl_hash + bl_ts
        print(f"HANDSHAKE FINAL: {bl_hash} {bl_ts} {final}")
        # TODO: vraag app naar leafs vanaf bl_hash
        leafs = bytes()  # [bytes.fromhex(h) + s.to_bytes(length=4, byteorder='little') for h, s in []]
        leaf_count = VarInt64.encode(len(leafs)).to_bytes()
        handshake = final + leaf_count + leafs

        self.conn.send(
            self.stream_id,
            self.stream_type + (len(handshake)).to_bytes(length=4, byteorder='little') + handshake,
        )


    def initiator_message(self, data: bytes):
        #print(f"RECEIVED UP0 MSG: {len(data)}")

        if not self.handshake_complete:
            header_hash = data[:32].hex()
            slot = int.from_bytes(data[32:36], byteorder='little')

            jam_bytes = JamBytes(data[36:])
            leaf_count = VarInt64.decode(jam_bytes)

            for leaf_nr in range(leaf_count):
                leaf_hash = jam_bytes.get_next_bytes(32).hex()
                leaf_slot = U32.decode(jam_bytes)
                #print(f"leaf: {leaf_hash} {leaf_slot}")

            #print(f"HANDSHAKE: {header_hash} {slot} {leaf_count} remaining: {jam_bytes.get_remaining_length()}")
            self.handshake_complete = True

            #self.conn._quic.reset_stream(self.stream_id, error_code=0x0)
            latest_block_hash = self.conn.protocol.app.retrieve_block_hash(self.conn.protocol.app.state.timeslot.number)
            #TODO: check if our latest hash is older than what we received with the handshake
            print(f"REQUEST BLOCKS AFTER HANDSHAKE FOR {latest_block_hash.hex()} timeslot: {self.conn.protocol.app.state.timeslot.number}")
            #TODO: nette dataclass encoders/decoders maken hiervoor!!!
            from pyjamaz.transport.jamnp_s.protocol import JAMNPS
            asyncio.create_task(self.conn.protocol.app.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.REQUEST_BLOCKS, data=[self.conn.host, self.conn.port, latest_block_hash, JAMNPS.DIRECTION_ASC, 1])))
            return

        # After handshake is completed, we receive Announcement messages
        # jam_bytes = JamBytes(data)
        # header = Header.from_jam_bytes(jam_bytes)
        # header_hash = jam_bytes.get_next_bytes(32).hex()
        # slot = U32.decode(jam_bytes)
        # #print(f"UP0 Update: {header} {header_hash} {slot}")
        # #MESSAGE_TYPES.RECEIVED_BLOCK -> moet ook weer checken of we dit block niet al hebben


    def acceptor_message(self, data: bytes):
        pass