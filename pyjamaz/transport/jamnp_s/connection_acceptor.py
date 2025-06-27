import logging

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted

from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class ConnectionAcceptor(ConnectionBase):

    def quic_event_received(self, event: QuicEvent):
        pass

