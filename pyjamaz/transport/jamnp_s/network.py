from __future__ import annotations

import ssl
from typing import Optional, TYPE_CHECKING

from aioquic.quic.configuration import QuicConfiguration
from ulid import ULID

from pyjamaz.transport.jamnp_s.connection import JAMConnection, JAMConnectionDirection

if TYPE_CHECKING:
    from pyjamaz.transport.jamnp_s.protocol import JAMNPS


def build_client_configuration(protocol_name: str, certificate: str, private_key: str) -> QuicConfiguration:
    configuration = QuicConfiguration(
        alpn_protocols=[protocol_name],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
    )
    configuration.load_cert_chain(certfile=certificate, keyfile=private_key)
    return configuration


def build_server_configuration(protocol_name: str, certificate: str, private_key: str) -> QuicConfiguration:
    configuration = QuicConfiguration(
        alpn_protocols=[protocol_name],
        is_client=False,
    )
    configuration.load_cert_chain(certificate, private_key)
    return configuration


def create_connection_factory(
    protocol: "JAMNPS",
    direction: JAMConnectionDirection,
    host: str,
    port: int,
    validator_key: Optional[bytes],
):
    def create_connection(*args, **kwargs):
        conn = JAMConnection(*args, **kwargs)
        conn.protocol = protocol
        conn.direction = direction
        conn.stream_manager = protocol.stream_manager
        conn.jam_connection_ulid = ULID()
        conn.validator_key = validator_key

        if direction == JAMConnectionDirection.initiator:
            conn.host = host
            conn.port = port

        protocol.peer_registry.register(conn)
        if validator_key is not None:
            protocol.validator_manager.bind_connection(validator_key, conn)

        return conn

    return create_connection
