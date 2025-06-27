import asyncio
import logging
import struct
from typing import List

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted

from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase
from pyjamaz.transport.jamnp_s.stream_0_up import StreamUP

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class ConnectionInitiator(ConnectionBase):


    def quic_event_received(self, event: QuicEvent) -> None:
        logger.debug(f'ProtocolInitiator received data {event}')

        if isinstance(event, HandshakeCompleted):
            #TODO:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   At least one of the nodes is not a validator.
            if self.stream_up_id is not None:
                raise Exception("There can be only one UP connection active at a time")

            self.stream_up_id = self._quic.get_next_available_stream_id()
            self.streams[self.stream_up_id] = StreamUP(self.stream_up_id, self)
            self.streams[self.stream_up_id].send_handshake()

        elif isinstance(event, StreamDataReceived):

            stream_id = event.stream_id

            if stream_id not in self.streams:
                raise Exception(f"Stream {stream_id} not available")

            self.streams[stream_id].receive_data(bytes(event.data))


    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination


    async def send_blocks_request(self, direction, max_blocks, block_bytes):
        #!!!!!!!!!!!!TODO: moet over een nieuwe stream -> creeer een nieuwe stream
        # data = (
        #     # int(direction).to_bytes(length=1, byteorder='little') +
        #     # int(max_blocks).to_bytes(length=1, byteorder='little') +
        #     block_bytes
        # )
        # self._quic.send_stream_data(
        #     self.stream_up,
        #     (int(StreamType.CE128_BlockRequest.value).to_bytes(length=1, byteorder='little') +
        #      len(data).to_bytes(length=4, byteorder='little') +
        #      data)
        # )
        # self.transmit()
        logger.debug(f"ClientProtocol Block Requests sent to stream {self.stream_up_id} ({len(data)})")
