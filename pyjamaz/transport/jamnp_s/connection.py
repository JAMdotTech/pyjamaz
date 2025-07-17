import asyncio
import logging

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.events import QuicEvent, HandshakeCompleted, StreamReset, StreamDataReceived, ConnectionTerminated

from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamDirection
from pyjamaz.transport.jamnp_s.stream_map import StreamLookup
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class JAMConnection(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Note: should be set in wrap_protocol
        self.direction:StreamDirection = None #TODO: JAMConnectionDirection!
        self.protocol = None
        self.jam_connection_ulid = None
        self.host = None
        self.port = None

        self.stream_up = None
        self.streams = {}
        #self._keepalive_task = asyncio.create_task(self._keepalive())


    def open_jam_stream(self, StreamCls: Stream, direction:StreamDirection, stream_id: int=None):
        if stream_id is None:
            stream_id = self._quic.get_next_available_stream_id()
            logger.debug(f"QUIC initiating stream {stream_id} for {direction}")
        else:
            logger.debug(f"QUIC accepting stream {stream_id} for {direction}")

        self.streams[stream_id] = StreamCls(stream_id, connection=self, direction=direction)
        return self.streams[stream_id]


    def close_jam_stream(self, stream: Stream, reason:int=0, clean_close: bool = False):
        logger.info(f"QUIC closing JAM stream {stream.stream_type} {stream.stream_id} for {stream.direction} (clean: {clean_close})")
        if clean_close:
            self.send(stream.stream_id, b'', end_stream=True)
        else:
            self._quic.reset_stream(stream.stream_id, error_code=reason)
        if stream.stream_id in self.streams:
            del self.streams[stream.stream_id]


    def is_connected(self) -> bool:
        """Check if the connection is active and ready"""
        return self._quic is not None and not self._quic._close_pending


    def send(self, stream_id: int, data: bytes, end_stream=False):
        try:
            self._quic.send_stream_data(
                stream_id,
                data,
                end_stream=end_stream
            )
            self.transmit()
        except Exception as e:
            #TODO!!!!!!!!!!!!!!!!!!
            logger.error(e)


    def connection_lost(self, exc):
        logger.info("QUIC UDP transport closed")
        self.protocol.disconnect(self)
        super().connection_lost(exc)


    async def _keepalive(self):
        try:
            while True:
                #TODO: what is a sane amount of time? Usefull for detecting disconnect (early)?
                await asyncio.sleep(3)
                self._quic.send_ping(id(self))
                self.transmit()
        except asyncio.CancelledError:
            pass


    def quic_event_received(self, event: QuicEvent) -> None:

        if event and hasattr(event, "stream_id"):
            if event.stream_id != 0:
                logger.debug(f'QUIC stream {event.stream_id} received data {event}')
        else:
            logger.debug(f'QUIC received non stream data {event}')

        if isinstance(event, HandshakeCompleted):
            #TODO:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   At least one of the nodes is not a validator.
            if self.stream_up is not None:
                raise Exception("There can be only one UP connection active at a time")

            if self.direction == StreamDirection.initiator:
                # Initiating side will send a JAM handshake message and set the stream id
                stream_up = self.open_jam_stream(StreamUP, direction=self.direction)
                self.stream_up = stream_up
                self.protocol.up0_send_handshake(self)
            else:
                # Note: it seems only now we have this info available from the accepting side
                self.host, self.port = self._quic._network_paths[0].addr

        elif isinstance(event, StreamReset):
            stream_id = event.stream_id
            reset_code = event.error_code

            logger.info(f'QUIC StreamReset {stream_id} {self.direction} code {reset_code}')

            if stream_id not in self.streams:
                #raise Exception(f"QUIC stream {stream_id} not available")
                logger.debug(f"QUIC stream {stream_id} already closed")
                return

            self.streams[stream_id].reset(reset_code)

        elif isinstance(event, StreamDataReceived):

            stream_id = event.stream_id
            data = bytes(event.data)
            
            logger.debug(f"StreamDataReceived: stream_id={stream_id}, data_len={len(data)}, end_stream={event.end_stream}")

            try:
                if stream_id not in self.streams:
                    if self.direction == StreamDirection.acceptor:
                        stream_type = int(data[0])
                        stream_cls = StreamLookup.get(stream_type)
                        if stream_cls is None:
                            raise Exception(f"QUIC stream {stream_id} is not mapped (type {stream_type})")

                        stream_obj = self.open_jam_stream(stream_cls, direction=self.direction, stream_id=stream_id)

                        if stream_cls == StreamUP:
                            # If we're on the acceptor side of this stream, send a handshake message back
                            if self.stream_up is None or self.stream_up.stream_id < stream_id:
                                self.stream_up = stream_obj
                                #self.protocol.up0_send_handshake(self)

                        # Only the first time an acceptor receives a message, we expect a stream id byte
                        data = data[1:]
                    else:
                        #TODO: of idem? kan een accepting connection bv ook een block request terug sturen?
                        raise Exception(f"Received data from unknown stream id: {stream_id}")

                self.streams[stream_id].receive_data(data, event.end_stream)
            except Exception as e:
                logger.error(f"Error handling stream data: {e}", exc_info=True)
                # Reset the stream with an error code
                self._quic.reset_stream(stream_id, error_code=2)
                raise

        elif isinstance(event, ConnectionTerminated):
            logger.info(f"QUIC connection terminated with code {event.error_code}")
            self.protocol.disconnect(self)
