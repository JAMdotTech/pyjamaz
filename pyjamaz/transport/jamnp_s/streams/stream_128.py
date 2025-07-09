import logging

from jamcodec.base import JamBytes

from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.message_types import MsgCE128BlockRequest
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamBlockRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE128_BlockRequest.value.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        print(f"CE128 RECEIVED RESET: {reset_code}")
        self.protocol.ce128_finished_block_request()
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        print(f"RECEIVED INITIATED CE128 MSG: {len(data)}")
        if len(data) == 0: #int.from_bytes(b'\x00\x00\x00\x00')
            #TODO: send FIN? Let protocol know were finished?
            print(f'!!!!!!!!!ConnectionInitiator StreamBlockRequest.initiator_message received empty data')
            self.initiator_reset(reset_code=0)
            return

        block = Block.from_jam_bytes(JamBytes(data))
        block_hash = block.header.hash
        print(f"Parsed block: {block_hash.hex()} parent:{block.header.parent.hex()}")

        self.protocol.ce128_received_block_request(self.conn, block)

    def acceptor_message(self, data: bytes):
        print("RECEIVED ACCEPTOR BLOCK REQUEST!!!!!!!!!!!!!!!!!!!!!!!!")
        self.protocol.ce128_send_block_request(self.conn, MsgCE128BlockRequest.from_jam_bytes(JamBytes(data)))
