import logging

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted

from jamcodec.base import JamBytes
from jamcodec.types import Vec

from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class ConnectionAcceptor(ConnectionBase):

    # #TODO: deprecated!!!!!!
    # async def send_block_announcement(self, block_bytes):
    #     if self.stream_up is None:
    #         raise Exception("NO UP 0 block_announcement channel opend yet??")
    #
    #     """
    #     TODO:
    #     For now we only send length++, we should send:
    #         Final = Header Hash ++ Slot
    #         Leaf = Header Hash ++ Slot
    #         Handshake = Final ++ len++[Leaf]
    #         Announcement = Header ++ Final
    #     """
    #     self._quic.send_stream_data(
    #         self.stream_up,
    #         (int(StreamType.UP0_BlockAnnouncement.value).to_bytes(length=1, byteorder='little') +
    #          len(block_bytes).to_bytes(length=4, byteorder='little') +
    #          block_bytes)
    #     )
    #     self.transmit()
    #     logger.debug(f"ServerProtocol Block announcement sent to stream {self.stream_up} ({len(block_bytes)})")

    def quic_event_received(self, event: QuicEvent):
        # if isinstance(event, HandshakeCompleted):
        #     # TODO: check client certificate and alpn
        #     # if self._quic.configuration.alpn_protocols[0] != "jamnp-s/0/00000000":
        #     #     self._quic.close()
        #     #     return
        #
        #     self.client_id = id(self)
        #     self.protocol.conn_in[self.client_id] = self  # Store reference for broadcasting
        #
        #     logger.debug(f'ServerProtocol new connected client #{self.client_id}')
        #
        # #TODO: remove connections on connection closed/lost etc
        #
        # elif isinstance(event, StreamDataReceived):
        #     logger.debug(f'Server received data: {event.data}')
        #
        #     if self.stream_up is None:
        #         self.stream_up = event.stream_id
        #         logger.debug(f'ServerProtocol new UP-0 stream ({self.stream_up}) for client #{self.client_id}')
        #
        #     # if event.stream_id == self.stream_up:
        #     #     # Process incoming data (either handshake or announcement)
        #     #     logger.debug(f'ServerProtocol new UP-0 stream ({self.stream_up}) for client #{self.client_id}')
        #
        #     byte_data = bytes(event.data)
        #     bytes_left = byte_data
        #
        #     # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
        #     while len(bytes_left) > 0:
        #
        #         #TODO: do this per channel
        #         if not self._msg_buffer:
        #             # Note: first message always contains expected message type & length
        #             # TODO: kunnen msg_type en msg_len ook opgesplitst zijn in 2 messages?? gaan nu uit dat dit atomair is
        #             self._msg_type = int.from_bytes(byte_data[0:1], byteorder='little')
        #             self._msg_offset = 5
        #             self._msg_len = int.from_bytes(byte_data[1:5], byteorder='little') + self._msg_offset
        #             logger.debug(f'ServerProtocol new message {self._msg_type} ({self._msg_len} bytes)')
        #
        #         nr_bytes_remaining = self._msg_len-len(self._msg_buffer)
        #         if nr_bytes_remaining > 0:
        #             self._msg_buffer += bytes_left[:nr_bytes_remaining]
        #             bytes_left = bytes_left[nr_bytes_remaining:]
        #         else:
        #             bytes_left = bytes()
        #
        #         # If we assembled a new message, parse it
        #         if 0 < self._msg_len == len(self._msg_buffer):
        #
        #             match self._msg_type:
        #
        #                 case StreamType.UP0_OPEN.value:
        #                     logger.debug(f'ServerProtocol PARSED UP-0')
        #                     self._reset_msg()
        #
        #                 case StreamType.CE128_BlockRequest.value:
        #                     logger.debug(f'ServerProtocol RECEIVED NEW BLOCKSREQUEST')
        #                     direction = 1#self._msg_buffer[self._msg_offset:self._msg_offset+1]
        #                     max_blocks = 1000 #self._msg_buffer[self._msg_offset+1:self._msg_offset+1+4]
        #                     block = Block.from_jam_bytes(JamBytes(self._msg_buffer[self._msg_offset:self._msg_len]))
        #
        #                     logger.debug(
        #                         f"ServerProtocol Block Requests received {self.stream_up} direction: {direction}, max_blocks: {max_blocks}, block: {block.header.timeslot}")
        #
        #                     blocks = []
        #                     #TODO: take direction and max_blocks into account
        #                     #TODO: we decode and serialize blocks unnecessary here, improve!
        #                     #TODO: check the max blocks and a hardcoded max of X
        #                     while block.header.parent != bytes(32):
        #                         block = self.protocol.app.retrieve_block_by_hash(block.header.parent)
        #                         if not block:
        #                             break
        #                         blocks.append(block)
        #
        #                     block_list = Vec(Block.to_codec_def()).new()
        #                     #TODO: optimize!! :S
        #                     serialized_blocks = block_list.encode([b.to_json() for b in blocks])
        #
        #                     logger.debug(
        #                         f"ServerProtocol Block Requests sending {len(blocks)} blocks")
        #
        #                     self._quic.send_stream_data(
        #                         self.stream_up,
        #                         (int(StreamType.CE128_BlockRequest.value).to_bytes(length=1, byteorder='little') +
        #                          len(serialized_blocks).to_bytes(length=4, byteorder='little') +
        #                          serialized_blocks.to_bytes())
        #                     )
        #                     self.transmit()
        #                     self._reset_msg()
        #
        #                 case _:
        #                     raise InvalidStreamType(f"Invalid JAMNPS message: {self._msg_type}")
        #
        # elif isinstance(event, ConnectionTerminated):
        #     # Handle connection termination
        #     if id(self) in self.protocol.conn_in:
        #         logger.debug(f'Client #{self.client_id} disconnected')
        #         # print(f'Client #{self.client_id} disconnected')
        #         del self.protocol.conn_in[id(self)]
        pass

