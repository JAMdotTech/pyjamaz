from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Optional, cast

from ulid import ULID

from aioquic.asyncio import serve
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.transport.jamnp_s.connection import JAMConnection, JAMConnectionDirection
from pyjamaz.transport.jamnp_s.peers import PeerRegistry
from pyjamaz.transport.jamnp_s.stream_manager import StreamManager
from pyjamaz.transport.jamnp_s.protocol import ProtocolContext, ProtocolSharedState, register_handlers
from pyjamaz.transport.jamnp_s.types import JAMStreamKind
from pyjamaz.transport.jamnp_s.validator_manager import ValidatorConnectionManager
from pyjamaz.transport.types import ProtocolType

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

"""
Note: Monkeypatch :S

we monkeypatch aioquic.quic.connection.QuicConnection._initialize
after aioquic creates its internal TLS context, it sets self.tls._request_client_certificate = True
that makes the server send a TLS CertificateRequest, so the client includes its certificate during the handshake
pyjamaz/transport/jamnp_s/connection.py reads the peer certificate on HandshakeCompleted to derive the remote validator key and bind the connection

As of aioquic is 1.2.0
  - QuicConfiguration has no public request_client_certificate option in aioquic/quic/configuration.py
  - aioquic TLS context keeps _request_client_certificate = False by default, explicitly marked "for test purposes only" in aioquic/tls.py:1276
  - the server only emits CertificateRequest when that private flag is true in aioquic/tls.py:2036
"""
if QuicConnection is not None and not getattr(QuicConnection, "_pyjamaz_client_cert_patch", False):
    _original_initialize = QuicConnection._initialize

    def _initialize_with_client_certificate(self, peer_cid: bytes) -> None:
        _original_initialize(self, peer_cid)
        self.tls._request_client_certificate = True

    QuicConnection._initialize = _initialize_with_client_certificate
    QuicConnection._pyjamaz_client_cert_patch = True


def quick_client_config(protocol_name: str, certificate: str, private_key: str) -> QuicConfiguration:
    configuration = QuicConfiguration(
        alpn_protocols=[protocol_name],
        is_client=True,
        verify_mode=ssl.CERT_NONE,
    )
    configuration.load_cert_chain(certfile=certificate, keyfile=private_key)
    return configuration


def quick_server_config(protocol_name: str, certificate: str, private_key: str) -> QuicConfiguration:
    configuration = QuicConfiguration(
        alpn_protocols=[protocol_name],
        is_client=False,
    )
    configuration.load_cert_chain(certificate, private_key)
    return configuration


def _create_jam_connection(
    network: "JAMNPS",
    direction: JAMConnectionDirection,
    host: str,
    port: int,
    validator_key: Optional[bytes],
):
    def create_connection(*args, **kwargs):
        conn = JAMConnection(*args, **kwargs)
        conn.protocol = network
        conn.direction = direction
        conn.stream_manager = network.stream_manager
        conn.jam_connection_ulid = ULID()
        conn.validator_key = validator_key

        if direction == JAMConnectionDirection.initiator:
            conn.host = host
            conn.port = port

        network.peer_registry.register(conn)
        if validator_key is not None:
            network.validator_manager.bind_connection(validator_key, conn)

        return conn

    return create_connection


class JAMNPS(ProtocolType):
    MAX_MESSAGE_SIZE = 10000000
    PROTOCOL_NAME = "jamnp-s/0/{}"
    VALIDATOR_CHECK_INTERVAL = 3.0

    def __init__(self, host, port, certificate, private_key, app):
        self.host = host
        self.port = port
        self.pubsub = app.pubsub
        self.app = app
        self.cert = certificate
        self.pk = private_key

        bl_hash = app.retrieve_block_hash(0).hex()
        if bl_hash.startswith("0x"):
            bl_hash = bl_hash[2:]
        bl_hash = bl_hash[:8]

        self.protocol_name = JAMNPS.PROTOCOL_NAME.format(bl_hash)
        self.configuration = quick_client_config(self.protocol_name, certificate, private_key)
        self.conn_out = None
        self.connection_tasks: dict[str, asyncio.Task[None]] = {}

        self.peer_registry = PeerRegistry(self)
        self.stream_manager = StreamManager(self.MAX_MESSAGE_SIZE)
        self.validator_manager = ValidatorConnectionManager(
            app=self.app,
            connect_callback=self.connect,
            disconnect_callback=self.disconnect,
            port_override=self.port,
        )
        self.context = ProtocolContext(
            app=self.app,
            peer_registry=self.peer_registry,
            validator_manager=self.validator_manager,
            stream_manager=self.stream_manager,
            state=ProtocolSharedState(),
        )
        self.protocol_handlers = register_handlers(self.stream_manager, self.context)

        #TODO: add all handlers
        up0_handler = self.handler(JAMStreamKind.UP0_BlockAnnouncement)
        ce128_handler = self.handler(JAMStreamKind.CE128_BlockRequest)
        ce131_handler = self.handler(JAMStreamKind.CE131_SafroleTicketDistributionStep1)

        self.pubsub.subscribe(MESSAGE_TYPES.PRODUCED_BLOCK, up0_handler.broadcast_block)
        self.pubsub.subscribe(MESSAGE_TYPES.CE128_SUCCESS, ce128_handler.finish_block_request)
        self.pubsub.subscribe(MESSAGE_TYPES.CE128_FAILURE, ce128_handler.finish_block_request)
        self.pubsub.subscribe(MESSAGE_TYPES.TICKET_ADD, ce131_handler.broadcast_own_ticket)


    @property
    def validator(self):
        return self.validator_manager.validator


    @property
    def validator_dns(self):
        return self.validator_manager.validator_dns


    @property
    def validator_port(self):
        return self.validator_manager.validator_port


    @property
    def validator_address(self):
        return self.validator_manager.validator_address


    def handler(self, kind: JAMStreamKind):
        return self.protocol_handlers[kind]


    async def listen(self):
        logger.info(f"Listening on {self.host}:{self.port}")

        server_conf = quick_server_config(self.protocol_name, self.cert, self.pk)
        await serve(
            self.host,
            self.port,
            configuration=server_conf,
            create_protocol=_create_jam_connection(
                self,
                JAMConnectionDirection.acceptor,
                self.host,
                self.port,
                None,
            ),
            retry=True,
        )


    def should_initiate_connection(self, validator_a: bytes, validator_b: bytes) -> bool:
        return self.validator_manager.should_initiate_connection(validator_a, validator_b)


    async def update_connections(self):
        await self.validator_manager.update_validator_connections()


    async def connect(self, host: str, port: int, validator_key: Optional[bytes]):
        addr = f"{host}:{port}"
        if addr in self.peer_registry.conn_addr:
            logger.warning(f"Ignoring duplicate connection to {addr}")
            return

        if addr in self.connection_tasks:
            logger.debug(f"Connection attempt already in progress for {addr}")
            return

        task = asyncio.create_task(self.connect_task(host, port, validator_key))
        self.connection_tasks[addr] = task

        def _cleanup(finished: asyncio.Task[None]) -> None:
            self.connection_tasks.pop(addr, None)
            try:
                finished.result()
            except Exception as exc:
                logger.warning(f"💩 Connection task for {addr} failed: {exc}")

        task.add_done_callback(_cleanup)


    async def connect_task(self, host: str, port: int, validator_key: Optional[bytes]) -> None:
        configuration = quick_client_config(self.protocol_name, self.cert, self.pk)

        logger.info(f"Connecting to {host}:{port}")
        try:
            async with connect(
                host,
                port,
                configuration=configuration,
                create_protocol=_create_jam_connection(
                    self,
                    JAMConnectionDirection.initiator,
                    host,
                    port,
                    validator_key,
                ),
            ) as client:
                client = cast(JAMConnection, client)
                await client.wait_closed()
                self.disconnect(client)
        except ConnectionError as exc:
            logger.warning(f"💩 Cannot connect to {host}:{port} {exc}")


    async def check_connections(self) -> None:
        while True:
            try:
                await self.update_connections()
            except Exception as exc:
                logger.warning(f"Validator connectivity maintenance failed: {exc}")
            await asyncio.sleep(self.VALIDATOR_CHECK_INTERVAL)


    def disconnect(self, connection: JAMConnection, validator_key: Optional[bytes] = None):
        self.stream_manager.cleanup_connection(connection)
        self.peer_registry.unregister(connection)
        self.validator_manager.on_disconnect(connection, validator_key)
