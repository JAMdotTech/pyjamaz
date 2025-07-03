import asyncio
import logging

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.events import QuicEvent, HandshakeCompleted, StreamReset, StreamDataReceived

from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class JAMConnection(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Note: should be set in wrap_protocol
        self.direction:StreamDirection = None
        self.protocol = None
        self.host = None
        self.port = None

        self.stream_up = None
        self.streams = {}
        #self._keepalive_task = asyncio.create_task(self._keepalive())


    def open_jam_stream(self, StreamCls: Stream):
        stream_id = self._quic.get_next_available_stream_id()
        self.streams[stream_id] = StreamCls(stream_id, connection=self, direction=self.direction)
        return self.streams[stream_id]


    def close_jam_stream(self, stream: Stream, reason:int=0):
        self._quic.reset_stream(stream.stream_id, error_code=reason)
        del self.streams[stream.stream_id]


    def send(self, stream_id: int, data, end_stream=False):
        self._quic.send_stream_data(
            stream_id,
            data,
            end_stream=end_stream
        )
        self.transmit()


    async def _keepalive(self):
        try:
            while True:
                #TODO: what is a sane amount of time?
                await asyncio.sleep(4)
                self._quic.send_ping(id(self))
                self.transmit()
        except asyncio.CancelledError:
            pass


    def quic_event_received(self, event: QuicEvent) -> None:

        if event and hasattr(event, "stream_id"):
            if event.stream_id != 0:
                logger.debug(f'Stream {event.stream_id} received data {event}')
        else:
            logger.debug(f'Received non stream data {event}')

        if isinstance(event, HandshakeCompleted):
            #TODO:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   At least one of the nodes is not a validator.
            if self.stream_up is not None:
                raise Exception("There can be only one UP connection active at a time")

            self.protocol.up0_send_handshake(self)

        elif isinstance(event, StreamReset):
            stream_id = event.stream_id
            reset_code = event.error_code

            logger.info(f'StreamReset {stream_id} {self.direction} code {reset_code}')

            if stream_id not in self.streams:
                raise Exception(f"Stream {stream_id} not available")

            if self.direction == StreamDirection.initiator:
                self.streams[stream_id].initiator_reset(reset_code)
            elif self.direction == StreamDirection.acceptor:
                self.streams[stream_id].acceptor_reset(reset_code)

        elif isinstance(event, StreamDataReceived):

            stream_id = event.stream_id

            if stream_id not in self.streams:
                #logging.warning(f"Stream {stream_id} not available")
                #return
                raise Exception(f"Stream {stream_id} not available")

            self.streams[stream_id].receive_data(bytes(event.data))


    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination

