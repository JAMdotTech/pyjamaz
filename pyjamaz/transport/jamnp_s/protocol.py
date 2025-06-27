import logging
import ssl

from typing import Dict
from typing import Optional, cast

from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect

from pyjamaz.transport.jamnp_s.connection_initiator import ConnectionInitiator
from pyjamaz.transport.jamnp_s.connection_acceptor import ConnectionAcceptor
from pyjamaz.transport.types import ProtocolType


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


def wrap_protocol(wrapper, protocol):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.protocol = wrapper
        return instance

    return create_protocol


class SessionTicketStore:

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


class JAMNPS(ProtocolType):

    PROTOCOL_NAME = "jamnp-s/0/{}"

    #TODO: add role enum: validator, guarantors, light_client, builder, ...
    def __init__(self, host, port, certificate, private_key, app, initial_slot_nr, initial_block_hash, role):
        self.host = host
        self.port = port
        self.pubsub = app.pubsub
        self.app = app

        #################TODO: haal deze info uit app ipv arg??
        self.first_block_hash = initial_block_hash
        self.first_slot = initial_slot_nr
        bl_hash = initial_block_hash
        if bl_hash.startswith('0x'): bl_hash = bl_hash[2:]
        bl_hash = bl_hash[:8]
        ##################

        self.protocol_name = JAMNPS.PROTOCOL_NAME.format(bl_hash)
        self.session_ticket_store = SessionTicketStore()
        self.configuration = QuicConfiguration(
            alpn_protocols=[self.protocol_name],
            is_client=True,
            #quic_logger=quic_logger,
            #verify_mode=ssl.CERT_REQUIRED,
            verify_mode=ssl.CERT_NONE,
            idle_timeout=300000
        )
        self.cert = certificate
        self.pk = private_key
        self.configuration.load_cert_chain(certificate, private_key)
        self.conn_in = {}   # All incomming connections
        self.conn_out = {}  # All outgoing connections (who we connect to)


    async def listen(self):
        logger.debug(f'Listening on {self.host}:{self.port}')
        await serve(
            self.host,
            self.port,
            configuration=self.configuration,
            create_protocol=wrap_protocol(self, ConnectionAcceptor),
            session_ticket_fetcher=self.session_ticket_store.pop,
            session_ticket_handler=self.session_ticket_store.add,
            retry=True,
        )

    async def connect(self, host, port):
        configuration = QuicConfiguration(
            alpn_protocols=[self.protocol_name],
            is_client=True,
            #verify_mode=ssl.CERT_REQUIRED,
            verify_mode=ssl.CERT_NONE,
            idle_timeout=300000
        )
        configuration.load_cert_chain(certfile=self.cert, keyfile=self.pk)

        logger.debug(f"ClientProtocol Connecting to {host}:{port}")
        try:
            async with connect(
                    host,
                    port,
                    configuration=configuration,
                    # session_ticket_handler=save_session_ticket,
                    create_protocol=wrap_protocol(self, ConnectionInitiator),
            ) as client:
                client = cast(ConnectionInitiator, client)
                self.conn_out[(host, port)] = client
                #await client.open_stream_up()
                await client.wait_closed()
                del self.conn_out[(host, port)]
        except ConnectionError as exc:
            if (host, port) in self.conn_out:
                del self.conn_out[(host, port)]
            logger.warning(f"💩 ClientProtocol Cannot connect to {host}:{port} {exc}")


    async def request_blocks(self, direction, max_blocks, block_bytes):
        #TODO: temp hack, should be provided with a specific peer?
        conn_key = list(self.conn_out.keys())[0]
        conn = self.conn_out[conn_key]
        await conn.send_blocks_request(0, 100, block_bytes)


    async def broadcast_block(self, block):
        block_bytes = block.to_jam_bytes().to_bytes()
        logger.debug(f'ServerProtocol broadcasting block announcement to {len(self.conn_in)} clients')
        for client_id, client in self.conn_in.items():
            logger.debug(f"ServerProtocol send block to client {client}")
            await client.send_block_announcement(block_bytes)
