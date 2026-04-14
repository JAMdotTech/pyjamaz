import asyncio
import logging
from enum import Enum

from cryptography.hazmat.primitives import serialization

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic.events import (
    ConnectionTerminated,
    HandshakeCompleted,
    QuicEvent,
    StreamDataReceived,
    StreamReset,
)

from pyjamaz.transport.jamnp_s.types import JAMStreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class JAMConnectionDirection(Enum):
    initiator: int = 0
    acceptor: int = 1


class JAMConnection(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Note: is set in wrap_protocol call
        self.direction:JAMConnectionDirection = None
        self.protocol = None
        self.stream_manager = None
        self.jam_connection_ulid = None
        self.host = None
        self.port = None
        self.addr = None
        self.validator_key = None

        self.stream_up = None
        self.streams = {}   #TODO: typings
        self._keepalive_task = asyncio.create_task(self.keepalive())


    def close_stream(self, stream_id: int, clean_close: bool = True, reason: int = 0):
        logger.debug(
            f"Connection {self.jam_connection_ulid} QUIC closing stream {stream_id} (clean: {clean_close})"
        )

        if clean_close:
            self.send(stream_id, b"", end_stream=True)
            return

        self.reset_stream(stream_id, reason)


    def reset_stream(self, stream_id: int, error_code: int):
        logger.debug(
            f"Connection {self.jam_connection_ulid} QUIC resetting stream {stream_id} with code {error_code}"
        )
        self._quic.reset_stream(stream_id, error_code=error_code)
        self.transmit()


    def is_connected(self) -> bool:
        """Check if the connection is active and ready"""
        return (
            self._quic is not None
            and not self._quic._close_pending
            and self.stream_up is not None
            and not self.stream_up.closed
        )


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
            logger.error(f"Connection {self.jam_connection_ulid} error")
            logger.error(e)
            raise


    # def connection_made(self, transport):
    #     Note: initiator does not seem to have its connection info available here
    #     super().connection_made(transport)
    #     self.host, self.port = transport._extra["sockname"][0:2]
    #     self.addr = f"{self.host}:{self.port}"


    def connection_lost(self, exc):
        logger.debug(f"Connection {self.jam_connection_ulid} QUIC UDP transport closed")
        self._keepalive_task.cancel()
        if self.protocol is not None:
            self.protocol.disconnect(self)
        super().connection_lost(exc)


    async def keepalive(self):
        try:
            while True:
                #TODO: what is a sane amount of time? Usefull for detecting disconnect (early)?
                await asyncio.sleep(3)
                self._quic.send_ping(id(self))
                self.transmit()
        except asyncio.CancelledError:
            pass


    def get_peer_validator_key(self) -> bytes | None:
        peer_certificate = getattr(self._quic.tls, "_peer_certificate", None)
        if peer_certificate is None:
            return None

        public_key = peer_certificate.public_key()
        try:
            return public_key.public_bytes_raw()
        except AttributeError:
            return public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )


    def quic_event_received(self, event: QuicEvent) -> None:
        if event and hasattr(event, "stream_id"):
            if event.stream_id != 0:
                logger.debug(f'Connection {self.jam_connection_ulid} stream {event.stream_id} received data {event}')
        else:
            logger.debug(f'Connection {self.jam_connection_ulid} QUIC received non stream data {event}')

        if isinstance(event, HandshakeCompleted):
            #TODO: enforce:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   Or at least one of the nodes is not a validator.

            peer_validator_key = self.get_peer_validator_key()
            if peer_validator_key is not None:
                if self.validator_key is not None and peer_validator_key != self.validator_key:
                    logger.warning(
                        "Connection %s peer certificate key mismatch: expected %s got %s",
                        self.jam_connection_ulid,
                        self.validator_key.hex(),
                        peer_validator_key.hex(),
                    )
                    self.close(error_code=2, reason_phrase="validator key mismatch")
                    return

                if self.protocol.validator_manager.has_tracked_validator(peer_validator_key):
                    self.protocol.validator_manager.bind_connection(peer_validator_key, self)

            if self.direction == JAMConnectionDirection.initiator:
                addr = f"{self.host}:{self.port}"
                if not self.protocol.peer_registry.activate(self, addr):
                    return

                # Initiating side will send a JAM handshake message and set the stream id
                stream_up = self.stream_manager.open_outgoing(self, JAMStreamKind.UP0_BlockAnnouncement)
                self.stream_up = stream_up
                self.protocol.handler(JAMStreamKind.UP0_BlockAnnouncement).send_handshake(self)
            else:
                # Note: it seems only now we have this info available from the accepting side (aioquick quirk)
                self.host, self.port = self._quic._network_paths[0].addr[0:2]
                addr = f"{self.host}:{self.port}"
                if not self.protocol.peer_registry.activate(self, addr):
                    return

        elif isinstance(event, StreamReset):
            self.stream_manager.receive_reset(self, event.stream_id, event.error_code)

        elif isinstance(event, StreamDataReceived):
            stream_id = event.stream_id
            data = bytes(event.data)

            logger.debug(f"Connection {self.jam_connection_ulid} StreamDataReceived: stream_id={stream_id}, data_len={len(data)}, end_stream={event.end_stream}")

            try:
                self.stream_manager.receive_stream_data(self, stream_id, data, event.end_stream)
            except Exception as e:
                logger.error(f"Connection {self.jam_connection_ulid} Error handling stream data: {e}", exc_info=True)
                raise

        elif isinstance(event, ConnectionTerminated):
            logger.debug(f"Connection {self.jam_connection_ulid} QUIC connection terminated with code {event.error_code}")
            self.protocol.disconnect(self)
