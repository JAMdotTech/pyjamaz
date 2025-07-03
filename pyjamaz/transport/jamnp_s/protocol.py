import asyncio
import logging
import ssl

from typing import Dict
from typing import Optional, cast

from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect
from jamcodec.types import VarInt64

from pyjamaz.models.block import Block
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP

from pyjamaz.transport.types import ProtocolType
from pyjamaz.transport.jamnp_s.message_types import MsgCE128BlockRequestDirection, MsgCE128BlockRequest, MsgUP0Handshake, MsgUP0Announcement
from pyjamaz.transport.jamnp_s.streams.stream_128 import StreamBlockRequest
from pyjamaz.transport.jamnp_s.connection_base import ConnectionBase
from pyjamaz.transport.jamnp_s.connection_initiator import ConnectionInitiator
from pyjamaz.transport.jamnp_s.connection_acceptor import ConnectionAcceptor


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


def wrap_protocol(wrapper, protocol, host, port):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.protocol = wrapper
        instance.host = host
        instance.port = port
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
    def __init__(self, host, port, certificate, private_key, app):
        self.host = host
        self.port = port
        self.pubsub = app.pubsub
        self.app = app

        self.state_requesting_blocks = False

        bl_hash = app.retrieve_block_hash(0).hex()
        if bl_hash.startswith('0x'): bl_hash = bl_hash[2:]
        bl_hash = bl_hash[:8]

        self.protocol_name = JAMNPS.PROTOCOL_NAME.format(bl_hash)
        self.session_ticket_store = SessionTicketStore()
        self.configuration = QuicConfiguration(
            alpn_protocols=[self.protocol_name],
            is_client=True,
            #quic_logger=quic_logger,
            #verify_mode=ssl.CERT_REQUIRED,
            verify_mode=ssl.CERT_NONE,
            #idle_timeout=300000
        )
        self.cert = certificate
        self.pk = private_key
        self.configuration.load_cert_chain(certificate, private_key)
        self.conn_accepted = {}   # All incomming connections
        self.conn_initiated = {}  # All outgoing connections (who we connect to)


    async def listen(self):
        logger.debug(f'Listening on {self.host}:{self.port}')
        await serve(
            self.host,
            self.port,
            configuration=self.configuration,
            create_protocol=wrap_protocol(self, ConnectionAcceptor, self.host, self.port),
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
                    create_protocol=wrap_protocol(self, ConnectionInitiator, host, port),
            ) as client:
                client = cast(ConnectionInitiator, client)
                self.conn_initiated[(host, port)] = client
                await client.wait_closed()
                del self.conn_initiated[(host, port)]
        except ConnectionError as exc:
            if (host, port) in self.conn_initiated:
                del self.conn_initiated[(host, port)]
            logger.warning(f"💩 ClientProtocol Cannot connect to {host}:{port} {exc}")


    def up0_send_handshake(self, conn: ConnectionBase):
        # Create a presistent UP0 stream for the connection
        # stream_up = conn.open_jam_stream(StreamUP)
        # conn.stream_up = stream_up
        # slot = self.app.state.timeslot.number
        # header_hash = self.app.retrieve_block_hash(slot)
        # leafs = [] #TODO
        # handshake = MsgUP0Handshake(
        #     header_hash=header_hash,
        #     timeslot=slot,
        #     leafs=leafs
        # )
        # logger.debug(f"Sending Handshake on stream {stream_up.stream_id} to {conn.host}:{conn.port} with hash {header_hash}")
        # conn.send(
        #     stream_up.stream_id,
        #     stream_up.create_message(handshake.to_jam_bytes().to_bytes()),
        # )

        #TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! fix zie hierboven!!!!
        stream_up = conn.open_jam_stream(StreamUP)
        conn.stream_up = stream_up
        slot = self.app.state.timeslot.number
        bl_ts = slot.to_bytes(length=4, byteorder='little') #self.conn.protocol.app.state.timeslot.number
        bl_hash = self.app.retrieve_block_hash(slot)
        final = bl_hash + bl_ts
        leafs = bytes()  # [bytes.fromhex(h) + s.to_bytes(length=4, byteorder='little') for h, s in []]
        leaf_count = VarInt64.encode(len(leafs)).to_bytes()
        handshake = final + leaf_count + leafs
        logger.debug(f'Sending handshake {handshake} to {conn.host}:{conn.port}')
        conn.send(
            stream_up.stream_id,
            stream_up.stream_type + (len(handshake)).to_bytes(length=4, byteorder='little') + handshake,
        )


    def up0_received_handshake(self, conn: ConnectionBase, msg: MsgUP0Handshake):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            return

        block = self.app.retrieve_block_by_hash(msg.header_hash) #TODO: missch een efficientere exists check toevoegen
        #TODO: ook nog iets doen met slot en leafs ook mee requesten?
        if not block:
            logger.debug(f"Received newer block from handshake: {msg.header_hash} request blocks")
            self.state_requesting_blocks = True
            #self.ce128_initiate_block_request(conn, MsgCE128BlockRequest(msg.header_hash, MsgCE128BlockRequestDirection.DESC.value, 1)) #TODO: max_blocks=1 for now, >1 results in error from node?
            slot = self.app.state.timeslot.number
            bl_hash = self.app.retrieve_block_hash(slot)
            self.ce128_initiate_block_request(conn, MsgCE128BlockRequest(bl_hash, MsgCE128BlockRequestDirection.ASC.value, 1)) #TODO: max_blocks=1 for now, >1 results in error from node?


    def up0_received_announcement(self, conn: ConnectionBase, msg: MsgUP0Announcement):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            return

        block = self.app.retrieve_block_by_hash(msg.header.hash) #TODO: missch een efficientere exists check toevoegen
        #TODO: ook nog iets doen met bijhorende finalized header_hash & slot?
        if not block:
            logger.debug(f"Received new block announcement from up0: {msg.header.hash}")
            self.state_requesting_blocks = True
            self.ce128_initiate_block_request(conn, MsgCE128BlockRequest(msg.header.hash, MsgCE128BlockRequestDirection.ASC.value, 1)) #TODO: max_blocks=1 for now, >1 results in error from node?


    def ce128_initiate_block_request(self, conn: ConnectionBase, req: MsgCE128BlockRequest):
        stream = conn.open_jam_stream(StreamBlockRequest)
        print(f"PROTOCOL INITIATING BLOCK REQUEST ON STREAMID: {stream.stream_id} header hash: {req.header_hash} direction: {req.direction}, max_block: {req.max_blocks}")
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes()),
            end_stream=True
        )


    def ce128_received_block_request(self, conn: ConnectionBase, block: Block):
        print(f"PROTOCOL RECEIVED BLOCK REQUEST")
        asyncio.create_task(self.app.import_queue_add(block))
        self.ce128_initiate_block_request(conn, MsgCE128BlockRequest(block.header.hash, MsgCE128BlockRequestDirection.ASC.value, 1))  # TODO: max_blocks=1 for now, >1 results in error from node?


    def ce128_finished_block_request(self):
        self.state_requesting_blocks = False
        logger.debug("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!Finished block request")
        asyncio.create_task(self.app.process_import_queue())


    async def broadcast_block(self, block):
        block_bytes = block.to_jam_bytes().to_bytes()
        logger.debug(f'JAMNP broadcasting block announcement to {len(self.conn_accepted)} clients')
        for client_id, client in self.conn_accepted.items():
            logger.debug(f"JAMNP send block to client {client}")
            await client.send_block_announcement(block_bytes)
