import logging

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted, StreamReset

from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class ConnectionAcceptor(ConnectionBase):

    def quic_event_received(self, event: QuicEvent) -> None:
        if event and hasattr(event, "stream_id"):
            if event.stream_id != 0:
                logger.debug(f'ConnectionAcceptor STREAM {event.stream_id} DATA {event}')
        else:
            logger.debug(f'ConnectionAcceptor received non stream data {event}')

        if isinstance(event, HandshakeCompleted):
            # TODO:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   At least one of the nodes is not a validator.
            if self.stream_up is not None:
                raise Exception("There can be only one UP connection active at a time")

            self.protocol.up0_send_handshake(self)

        elif isinstance(event, StreamReset):
            stream_id = event.stream_id
            reset_code = event.error_code

            logger.info(f'ConnectionInitiator StreamReset {stream_id} code {reset_code}')

            if stream_id not in self.streams:
                raise Exception(f"Stream {stream_id} not available")

            self.streams[stream_id].initiator_reset(reset_code)

        elif isinstance(event, StreamDataReceived):

            stream_id = event.stream_id

            if stream_id not in self.streams:
                logging.warning(f"Stream {stream_id} not available")
                return

            self.streams[stream_id].receive_data(bytes(event.data))

    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination



