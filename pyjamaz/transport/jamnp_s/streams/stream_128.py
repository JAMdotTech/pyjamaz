from jamcodec.base import JamBytes

from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.stream import Stream, StreamType, StreamDirection


class StreamBlockRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE128_BlockRequest.value.to_bytes(length=1, byteorder='little')


    def initiator_block_request(self, header_hash, direction, max_blocks):
        header_hash = bytes.fromhex(header_hash)
        direction = direction.to_bytes(length=1, byteorder='little')
        max_blocks = max_blocks.to_bytes(length=4, byteorder='little')
        payload = header_hash + direction + max_blocks

        print("SENDING BLOCK REQUEST!!!!!!!")
        self.conn.send(
            self.stream_id,
            self.stream_type + (len(payload)).to_bytes(length=4, byteorder='little') + payload,
            end_stream=True
        )


    def initiator_message(self, data: bytes):
        print(f"RECEIVED CE128 MSG: {len(data)}")
        block = Block.from_jam_bytes(JamBytes(data))
        print(f"Parsed block: {block}")

    def acceptor_message(self, data: bytes):
        pass