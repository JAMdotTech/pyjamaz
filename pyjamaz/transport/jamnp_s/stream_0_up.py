from jamcodec.base import JamBytes
from jamcodec.types import U32, VarInt64

from pyjamaz.models.block import Header
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType


class StreamUP(Stream):

    def __init__(self, stream_id: int, connection):
        super().__init__(stream_id, connection)
        self.stream_type = StreamType.UP0_BlockAnnouncement.value.to_bytes(length=1, byteorder='little')
        self.handshake_complete = False

    def send_handshake(self):
        """
        TODO:
        Both sides should begin by sending a handshake message containing all known leaves (descendants of the latest finalized block with no known children).
        The header hash and slot of the latest finalized block should be included in the handshake message and also in every announcement message that is sent.
        """
        final = bytes.fromhex(self.conn.protocol.first_block_hash) + self.conn.protocol.first_slot.to_bytes(length=4, byteorder='little')
        leafs = bytes()  # [bytes.fromhex(h) + s.to_bytes(length=4, byteorder='little') for h, s in []] #TODO: vraag app naar leafs vanaf first_block
        leaf_count = VarInt64.encode(len(leafs)).to_bytes()
        handshake = final + leaf_count + leafs

        self.conn._quic.send_stream_data(
            self.stream_id,
            self.stream_type + (len(handshake)).to_bytes(length=4, byteorder='little') + handshake,
        )


    def parse_message(self, data: bytes):
        print(f"RECEIVED UP0 MSG: {len(data)}")

        if not self.handshake_complete:
            header_hash = data[:32].hex()
            slot = int.from_bytes(data[32:36], byteorder='little')

            jam_bytes = JamBytes(data[36:])
            leaf_count = VarInt64.decode(jam_bytes)

            for leaf_nr in range(leaf_count):
                leaf_hash = jam_bytes.get_next_bytes(32).hex()
                leaf_slot = U32.decode(jam_bytes)
                print(f"leaf: {leaf_hash} {leaf_slot}")

            print(f"HANDSHAKE: {header_hash} {slot} {leaf_count} remaining: {jam_bytes.get_remaining_length()}")
            self.handshake_complete = True

            # TODO: temp adhoc 128 stream, send notification instead!!!!!
            from pyjamaz.transport.jamnp_s.stream_128_block_request import StreamBlockRequest
            stream_id = self.conn._quic.get_next_available_stream_id()
            self.conn.streams[stream_id] = StreamBlockRequest(stream_id, self.conn)
            self.conn.streams[stream_id].send_block_request(header_hash, 1, 1)

            return

        #test = Header.from_jam_bytes(JamBytes(data))
