import logging

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted

from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP

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

            stream_up = self.create_jam_stream(StreamUP)
            self.stream_up_id = stream_up.stream_id
            stream_up.initiator_handshake()

        elif isinstance(event, StreamDataReceived):

            stream_id = event.stream_id

            if stream_id not in self.streams:
                raise Exception(f"Stream {stream_id} not available")

            self.streams[stream_id].receive_data(bytes(event.data))


    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination

