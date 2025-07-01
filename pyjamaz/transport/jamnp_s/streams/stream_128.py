import asyncio
import logging

from jamcodec.base import JamBytes

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.protocol import JAMNPS
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection
from pyjamaz.transport.pubsub import PubSubSignal

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamBlockRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE128_BlockRequest.value.to_bytes(length=1, byteorder='little')


    def initiator_block_request(self, header_hash: bytes, direction: bytes, max_blocks: int):
        #TODO: nette data classes maken voor messages vd streams!
        #direction_byte = direction.to_bytes(length=1, byteorder='little')
        max_blocks_bytes = max_blocks.to_bytes(length=4, byteorder='little')
        #direction = int(1).to_bytes(length=1, byteorder='little')
        #max_blocks = int(0).to_bytes(length=4, byteorder='little')
        payload = header_hash + direction + max_blocks_bytes

        print(f"SENDING BLOCK REQUEST streamid {self.stream_id} payload: {self.stream_type + (len(payload)).to_bytes(length=4, byteorder='little') + payload} end_stream=True")

        self.conn.send(
            self.stream_id,
            self.stream_type + (len(payload)).to_bytes(length=4, byteorder='little') + payload,
            end_stream=True
        )


    def initiator_message(self, data: bytes):
        print(f"RECEIVED INITIATED CE128 MSG: {len(data)}")
        if len(data) == 0: #int.from_bytes(b'\x00\x00\x00\x00')
            logger.debug(f'!!!!!!!!!ConnectionInitiator StreamBlockRequest.initiator_message received empty data')
            return

        block = Block.from_jam_bytes(JamBytes(data))
        latest_block_hash = block.header.hash
        print(f"Parsed block: {block.header.hash.hex()} parent:{block.header.parent.hex()}")

        asyncio.create_task(self.conn.protocol.app.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.REQUEST_BLOCKS, data=[self.conn.host, self.conn.port, latest_block_hash, JAMNPS.DIRECTION_ASC, 1])))


    def acceptor_message(self, data: bytes):
        raise Exception("Not implemented YET!!!!!!")
