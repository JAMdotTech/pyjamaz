import asyncio
import logging
import ssl

from typing import Dict, List
from typing import Optional, cast

from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect
from ulid import ULID

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block, Header
from pyjamaz.transport.jamnp_s.stream_base import StreamDirection

from pyjamaz.transport.types import ProtocolType
from pyjamaz.transport.jamnp_s.message_types import MsgCE128BlockRequestDirection, MsgCE128BlockRequest, \
    MsgUP0Handshake, MsgUP0Announcement, MsgCE128BlockRequestResponse
from pyjamaz.transport.jamnp_s.streams.stream_128 import StreamBlockRequest
from pyjamaz.transport.jamnp_s.connection import JAMConnection


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


#TODO: typings
def wrap_protocol(protocol, quic_connection, direction, host, port):
    def create_connection(*args, **kwargs):
        conn = quic_connection(*args, **kwargs)
        conn.protocol = protocol
        conn.direction = direction

        conn.jam_connection_ulid = ULID()
        protocol.connections[conn.jam_connection_ulid] = conn

        # Note: for accepting connections addr & port are known after the QUIC handshake, see JAMConnection::HandshakeComplete
        if direction == StreamDirection.initiator:
            conn.host = host
            conn.port = port
            protocol.conn_initiated.add(conn.jam_connection_ulid)
        else:
            protocol.conn_accepted.add(conn.jam_connection_ulid)

        return conn

    return create_connection


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

        self.pubsub.subscribe(MESSAGE_TYPES.CE128_SUCCESS, self.ce128_processed_block_request)
        self.pubsub.subscribe(MESSAGE_TYPES.CE128_FAILURE, self.ce128_processed_block_request)

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

        self.connections = {}   # All connections
        self.conn_accepted = set()   # All incomming connections
        self.conn_initiated = set()  # All outgoing connections (who we connect to)


    async def listen(self):
        logger.debug(f'Listening on {self.host}:{self.port}')

        server_conf = QuicConfiguration(
            alpn_protocols=[self.protocol_name],
            is_client=False,
            #verify_mode=ssl.CERT_NONE,
        )
        server_conf.load_cert_chain(self.cert, self.pk)

        await serve(
            self.host,
            self.port,
            configuration=server_conf,
            create_protocol=wrap_protocol(self, JAMConnection, StreamDirection.acceptor, self.host, self.port),
            #session_ticket_fetcher=self.session_ticket_store.pop,
            #session_ticket_handler=self.session_ticket_store.add,
            retry=True,
        )


    async def connect(self, host, port):
        configuration = QuicConfiguration(
            alpn_protocols=[self.protocol_name],
            is_client=True,
            #verify_mode=ssl.CERT_REQUIRED,
            verify_mode=ssl.CERT_NONE,
            #idle_timeout=300000
        )
        configuration.load_cert_chain(certfile=self.cert, keyfile=self.pk)

        logger.debug(f"Connecting to {host}:{port}")
        try:
            async with connect(
                    host,
                    port,
                    configuration=configuration,
                    # session_ticket_handler=save_session_ticket,
                    create_protocol=wrap_protocol(self, JAMConnection, StreamDirection.initiator, host, port),
            ) as client:
                client = cast(JAMConnection, client)
                await client.wait_closed()
                self.disconnect(client)
        except ConnectionError as exc:
            logger.warning(f"💩 ClientProtocol Cannot connect to {host}:{port} {exc}")


    def disconnect(self, connection: JAMConnection):
        if connection.direction == StreamDirection.initiator:
            self.conn_initiated.remove(connection.jam_connection_ulid)
        else:
            self.conn_accepted.remove(connection.jam_connection_ulid)

        del self.connections[connection.jam_connection_ulid]


    def up0_send_handshake(self, conn: JAMConnection):
        # Create a presistent UP0 stream for this connection
        slot = self.app.state.timeslot.number
        header_hash = self.app.retrieve_block_hash(slot)
        leafs = [] #TODO
        handshake = MsgUP0Handshake(
            header_hash=header_hash,
            timeslot=slot,
            leafs=leafs
        )
        logger.debug(f"Sending Handshake on stream {conn.stream_up.stream_id} to {conn.host}:{conn.port} with hash {header_hash}")

        add_stream_type = conn.direction == StreamDirection.initiator

        conn.send(
            conn.stream_up.stream_id,
            conn.stream_up.create_message(handshake.to_jam_bytes().to_bytes(), add_stream_type=add_stream_type),
        )


    def up0_received_handshake(self, conn: JAMConnection, msg: MsgUP0Handshake):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            logger.debug(f"Skipping handshake block header check, already importing blocks")
            return

        block = self.app.retrieve_block_by_hash(msg.header_hash) #TODO: missch een efficientere exists check toevoegen
        #TODO: ook nog iets doen met slot en leafs ook mee requesten?
        if not block:
            logger.debug(f"Received newer block from handshake: {msg.header_hash} -> initiate CE128RequestBlocks")
            self.state_requesting_blocks = True
            #self.ce128_initiate_block_request(conn, MsgCE128BlockRequest(msg.header_hash, MsgCE128BlockRequestDirection.DESC.value, 1)) #TODO: max_blocks=1 for now, >1 results in error from node?
            #slot = self.app.state.timeslot.number
            #bl_hash = self.app.retrieve_block_hash(slot)
            # TODO: max_blocks could be derived using current block timeslot and received blockhash timeslot?
            self.ce128_initiate_block_request(
                conn,
                MsgCE128BlockRequest(
                    msg.header_hash,
                    MsgCE128BlockRequestDirection.DESC.value,
                    10
                )
            )


    def up0_received_announcement(self, conn: JAMConnection, msg: MsgUP0Announcement):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            logger.debug(f"Skipping block header announcement check, already importing blocks")
            return

        """
        TODO: send to other nodes (other than this connection)
        Except when:
        A descendant of the block is announced instead.
        The block is not a descendant of the latest finalized block.
        The block, or a descendant of the block, has been announced by the other side of the stream.
        """

        block = self.app.retrieve_block_by_hash(msg.header.hash) #TODO: missch een efficientere exists check toevoegen
        #TODO: ook nog iets doen met bijhorende finalized header_hash & slot?
        if not block:
            logger.debug(f"Received new block announcement from up0: {msg.header.hash}")
            self.state_requesting_blocks = True
            # TODO: max_blocks could be derived using current block timeslot and received blockhash timeslot?
            self.ce128_initiate_block_request(
                conn,
                MsgCE128BlockRequest(
                    msg.header.hash,
                    MsgCE128BlockRequestDirection.DESC.value,
                    10
                )
            )


    async def up0_broadcast_block(self, block: Block):
        logger.debug(f'UP0 broadcasting block announcement to {len(self.connections)} connections')

        msg = MsgUP0Announcement(
            header=block.header,
            header_hash=block.header.hash,
            timeslot=block.header.timeslot
        ).to_jam_bytes().to_bytes()

        for client_id, client in self.connections.items():
            logger.debug(f"UP0 send block header to client {client.host}:{client.port} with hash {block.header.hash}")
            client.send(
                client.stream_up.stream_id,
                client.stream_up.create_message(msg),
                end_stream=False
            )


    def ce128_initiate_block_request(self, conn: JAMConnection, req: MsgCE128BlockRequest):
        #TODO: missch een batch param meegeven, zodat we een grotere reeks kunnen binnenhalen maar batchen...
        stream = conn.open_jam_stream(StreamBlockRequest, direction=StreamDirection.initiator)
        logger.debug(f"CE128 initiating block request on stream id: {stream.stream_id} direction: {req.direction}, max_block: {req.max_blocks} header hash: {req.header_hash}")
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True
        )


    def ce128_received_block_request(self, stream: StreamBlockRequest, req: MsgCE128BlockRequestResponse):
        blocks = req.blocks
        logger.debug(f"CE128 received block request (parsing {len(blocks)} blocks)")
        asyncio.create_task(
            self.app.import_queue_add_blocks(
                blocks,
                process=True,
                on_success=MESSAGE_TYPES.CE128_SUCCESS,
                on_failure=MESSAGE_TYPES.CE128_FAILURE
            )
        )


    def ce128_send_block_request(self, stream: StreamBlockRequest, block_req: MsgCE128BlockRequest):
        block:Block = None
        blocks:List[Block] = []
        first_block_hash = bytes(32)
        last_block_hash = self.app.retrieve_block_hash(self.app.state.timeslot.number)
        #TODO: check <=0 -> bad request
        block_header:Header = self.app.retrieve_block_header(block_req.header_hash)
        next_hash = block_req.header_hash

        if block_header and block_req.max_blocks > 0:
            #direction = 1 + block_req.direction * -2

            for x in range(block_req.max_blocks):

                if block_req.direction == MsgCE128BlockRequestDirection.ASC.value:
                    # Note: exclusive request block hash
                    block_child_hash: bytes = self.app.retrieve_block_child_hash(next_hash)
                    block = self.app.retrieve_block_by_hash(block_child_hash)
                    if block: next_hash = block.header.hash
                elif block_req.direction == MsgCE128BlockRequestDirection.DESC.value:
                    # Note: inclusive request block hash
                    block = self.app.retrieve_block_by_hash(next_hash)
                    if block: next_hash = block.header.parent
                else:
                    # TODO: error
                    raise Exception("HMmmmmmz?????")

                if block and block.header.timeslot > 0:
                    blocks.append(block)
                else:
                    break

        logger.debug(f"CE128 sending {len(blocks)} blocks (direction={block_req.direction} max blocks={block_req.max_blocks})")

        if blocks:
            stream.conn.send(
                stream.stream_id,
                stream.create_message(MsgCE128BlockRequestResponse(blocks=blocks).to_jam_bytes().to_bytes()),
                end_stream=True
            )

        #TODO: check ook direction!!!
        if not block or block_req.header_hash == last_block_hash or block.header.timeslot == 0:
            #TODO: PolkaJAM lijkt in dit geval een reset te sturen????
            #TODO: ook op max_blocks checken -> bijhouden op de stream?
            logger.debug(f"CE128 block request finished")
            stream.acceptor_reset(1) #TODO: REVERSE ENGINEER DEZE CODES


    def ce128_abort_block_request(self):
        logger.debug(f"Finished block request, start parsing import queue {len(self.app._import_queue)}")
        # Note: could happen during a block_request "session"
        asyncio.create_task(
            self.app.process_import_queue(
                on_success=MESSAGE_TYPES.CE128_SUCCESS,
                on_failure=MESSAGE_TYPES.CE128_FAILURE
            )
        )


    async def ce128_processed_block_request(self, *args, **kwargs):
        self.state_requesting_blocks = False