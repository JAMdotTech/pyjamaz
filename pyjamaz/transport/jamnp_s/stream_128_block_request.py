from jamcodec.base import JamBytes
from jamcodec.types import U32, VarInt64

from pyjamaz.models.block import Header
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType


class StreamBlockRequest(Stream):

    def __init__(self, stream_id: int, connection):
        super().__init__(stream_id, connection)
        self.stream_type = StreamType.CE128_BlockRequest.value.to_bytes(length=1, byteorder='little')


    def send_block_request(self, header_hash, direction, max_blocks):
        header_hash = bytes.fromhex(header_hash)
        direction = direction.to_bytes(length=1, byteorder='little')
        max_blocks = max_blocks.to_bytes(length=4, byteorder='little')
        payload = header_hash + direction + max_blocks

        print("SENDING BLOCK REQUEST!!!!!!!")
        self.conn._quic.send_stream_data(
            self.stream_id,
            self.stream_type + (len(payload)).to_bytes(length=4, byteorder='little') + payload,
            end_stream=True
        )


    def parse_message(self, data: bytes):
        print(f"RECEIVED CE128 MSG: {len(data)}")
        #test = Header.from_jam_bytes(JamBytes(data))
