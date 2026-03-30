from __future__ import annotations

import logging
from typing import Optional, cast

from aioquic.asyncio import serve
from aioquic.asyncio.client import connect

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.transport.jamnp_s.connection import JAMConnection, JAMConnectionDirection
from pyjamaz.transport.jamnp_s.streams import ProtocolContext, ProtocolSharedState, register_handlers
from pyjamaz.transport.jamnp_s.network import (
    build_client_configuration,
    build_server_configuration,
    create_connection_factory,
)
from pyjamaz.transport.jamnp_s.peers import PeerRegistry
from pyjamaz.transport.jamnp_s.stream_manager import StreamManager
from pyjamaz.transport.jamnp_s.types import StreamKind
from pyjamaz.transport.jamnp_s.validator_manager import ValidatorConnectionManager
from pyjamaz.transport.types import ProtocolType

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class JAMNPS(ProtocolType):
    MAX_MESSAGE_SIZE = 10000000
    PROTOCOL_NAME = "jamnp-s/0/{}"

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
        self.configuration = build_client_configuration(self.protocol_name, certificate, private_key)
        self.conn_out = None

        self.peer_registry = PeerRegistry(self)
        self.stream_manager = StreamManager(self.MAX_MESSAGE_SIZE)
        self.validator_manager = ValidatorConnectionManager(
            app=self.app,
            connect_callback=self.connect,
            disconnect_callback=self.disconnect,
        )
        self.context = ProtocolContext(
            app=self.app,
            peer_registry=self.peer_registry,
            validator_manager=self.validator_manager,
            stream_manager=self.stream_manager,
            state=ProtocolSharedState(),
        )
        self.protocol_handlers = register_handlers(self.stream_manager, self.context)

        # Hook up signals that require protocol handling
        up0_handler = self.handler(StreamKind.UP0_BlockAnnouncement)
        ce128_handler = self.handler(StreamKind.CE128_BlockRequest)
        ce131_handler = self.handler(StreamKind.CE131_SafroleTicketDistributionStep1)

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

    def handler(self, kind: StreamKind):
        return self.protocol_handlers[kind]

    async def listen(self):
        logger.info(f"Listening on {self.host}:{self.port}")

        server_conf = build_server_configuration(self.protocol_name, self.cert, self.pk)
        await serve(
            self.host,
            self.port,
            configuration=server_conf,
            create_protocol=create_connection_factory(
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

    async def update_validator_connections(self):
        await self.validator_manager.update_connections()

    async def connect(self, host: str, port: int, validator_key: Optional[bytes]):
        configuration = build_client_configuration(self.protocol_name, self.cert, self.pk)

        addr = f"{host}:{port}"
        if addr in self.peer_registry.conn_addr:
            logger.warning(f"Ignoring duplicate connection to {addr}")
            return

        logger.info(f"Connecting to {host}:{port}")
        try:
            async with connect(
                host,
                port,
                configuration=configuration,
                create_protocol=create_connection_factory(
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

    def disconnect(self, connection: JAMConnection, validator_key: Optional[bytes] = None):
        self.stream_manager.cleanup_connection(connection)
        self.peer_registry.unregister(connection)
        self.validator_manager.on_disconnect(connection, validator_key)
