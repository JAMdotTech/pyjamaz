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
from pyjamaz.models.block import Block, Header, TicketEnvelope
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.transport.jamnp_s.stream_base import StreamDirection
from pyjamaz.transport.jamnp_s.streams.stream_138 import StreamAuditShardRequest
from pyjamaz.transport.jamnp_s.streams.stream_139 import StreamSegmentShardRequest

from pyjamaz.transport.types import ProtocolType
from pyjamaz.transport.jamnp_s.message_types import MsgCE128BlockRequestDirection, MsgCE128BlockRequest, \
    MsgUP0Handshake, MsgUP0Announcement, MsgCE128BlockRequestResponse, \
    MsgCE131SafroleTicketDistribution, MsgCE132SafroleTicketDistribution, \
    MsgCE134WorkPackageSharing, MsgCE134WorkPackageBundle, MsgCE134RefineResponse, \
    MsgCE141Assurance, MsgCE142PreimageAnnouncement, MsgCE143HashRequest, MsgCE143Preimage, \
    MsgCE133WorkPackageSubmission, MsgCE133Extrinsic, MsgCE135GuaranteedWorkReport, \
    MsgCE136HashRequest, MsgCE136WorkReport, \
    MsgCE137ShardRequest, MsgCE137BundleShard, MsgCE137SegmentShard, MsgCE137Justification, \
    MsgCE138ShardRequest, MsgCE138BundleShard, MsgCE138Justification, \
    MsgCE139SegmentRequest, MsgCE139SegmentShard, \
    MsgCE140SegmentRequest, MsgCE140SegmentShard, MsgCE140Justification, \
    MsgCE144Announcement, MsgCE144Evidence, \
    MsgCE145JudgmentPublication, MsgCE131SafroleTicket, MsgCE132SafroleTicket
from pyjamaz.transport.jamnp_s.streams.stream_128 import StreamBlockRequest
from pyjamaz.transport.jamnp_s.streams.stream_131 import StreamSafroleTicketDistributionStep1
from pyjamaz.transport.jamnp_s.streams.stream_132 import StreamSafroleTicketDistributionStep2
from pyjamaz.transport.jamnp_s.streams.stream_134 import StreamWorkPackageSharing
from pyjamaz.transport.jamnp_s.streams.stream_141 import StreamAssuranceDistribution
from pyjamaz.transport.jamnp_s.streams.stream_142 import StreamPreimageAnnouncement
from pyjamaz.transport.jamnp_s.streams.stream_143 import StreamPreimageRequest
from pyjamaz.transport.jamnp_s.streams.stream_133 import StreamWorkPackageSubmission
from pyjamaz.transport.jamnp_s.streams.stream_135 import StreamWorkReportDistribution
from pyjamaz.transport.jamnp_s.streams.stream_136 import StreamWorkReportRequest
from pyjamaz.transport.jamnp_s.streams.stream_137 import StreamShardDistribution
from pyjamaz.transport.jamnp_s.streams.stream_140 import StreamSegmentShardRequestJustification
from pyjamaz.transport.jamnp_s.streams.stream_144 import StreamAuditAnnouncement
from pyjamaz.transport.jamnp_s.streams.stream_145 import StreamJudgmentPublication

from pyjamaz.transport.jamnp_s.connection import JAMConnection


logger = logging.getLogger("pyjamaz.transport.jamnp_s")



class JAMNPS(ProtocolType):

    MAX_MESSAGE_SIZE = 10000000
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

        #TODO:
        # callbacks like ce128_processed_block_request could be created using closure functions
        # (def create_ce128_processed_block_request returning the callback),
        # to create a local state which holds context like which connection/node initiated this event, so we can mark
        # malicious nodes etc...
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
            create_protocol=create_jam_connection(self, JAMConnection, StreamDirection.acceptor, self.host, self.port),
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
                    create_protocol=create_jam_connection(self, JAMConnection, StreamDirection.initiator, host, port),
            ) as client:
                client = cast(JAMConnection, client)
                await client.wait_closed()
                self.disconnect(client)
        except ConnectionError as exc:
            logger.warning(f"💩 ClientProtocol Cannot connect to {host}:{port} {exc}")


    def disconnect(self, connection: JAMConnection):
        if connection.direction == StreamDirection.initiator:
            if connection.jam_connection_ulid in self.conn_initiated:
                self.conn_initiated.remove(connection.jam_connection_ulid)
        else:
            if connection.jam_connection_ulid in self.conn_accepted:
                self.conn_accepted.remove(connection.jam_connection_ulid)

        if connection.jam_connection_ulid in self.connections:
            del self.connections[connection.jam_connection_ulid]


    def up0_send_handshake(self, conn: JAMConnection):
        # Create a presistent UP0 stream for this connection
        slot = self.app.state.timeslot.number
        header_hash = self.app.retrieve_block_hash(slot)
        leafs = [] #TODO: For now, we only work with finalized blocks
        handshake = MsgUP0Handshake(
            header_hash=header_hash,
            timeslot=slot,
            leafs=leafs
        )
        logger.debug(f"up0_send_handshake on stream {conn.stream_up.stream_id} to {conn.host}:{conn.port} with hash {header_hash}")

        add_stream_type = conn.direction == StreamDirection.initiator

        conn.send(
            conn.stream_up.stream_id,
            conn.stream_up.create_message(handshake.to_jam_bytes().to_bytes(), add_stream_type=add_stream_type),
        )


    def up0_received_handshake(self, conn: JAMConnection, msg: MsgUP0Handshake):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            logger.debug(f"up0_received_handshake Skipping handshake block header check, already importing blocks")
            return

        block = self.app.retrieve_block_by_hash(msg.header_hash) #TODO: missch een efficientere exists check toevoegen
        #TODO: ook nog iets doen met slot en leafs ook mee requesten?
        if not block:
            logger.debug(f"up0_received_handshake Received newer block from handshake: {msg.header_hash} -> initiate CE128RequestBlocks")
            self.state_requesting_blocks = True
            curr_hash = self.app.retrieve_block_hash(self.app.state.timeslot.number)
            # TODO: max_blocks could be derived using current block timeslot and received blockhash timeslot?
            self.ce128_initiate_block_request(
                conn,
                MsgCE128BlockRequest(
                    curr_hash, #msg.header_hash,
                    MsgCE128BlockRequestDirection.ASC.value, #MsgCE128BlockRequestDirection.DESC.value,
                    10
                )
            )


    def up0_received_announcement(self, conn: JAMConnection, msg: MsgUP0Announcement):
        # Note: For now we employ a very simple strategy, where we sync blocks from the first node that announced a finalized block greater than we have
        if self.state_requesting_blocks:
            logger.debug(f"up0_received_announcement Skipping block header announcement check, already importing blocks")
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
            logger.debug(f"up0_received_announcement Received new block announcement from up0: {msg.header.hash}")
            self.state_requesting_blocks = True
            curr_hash = self.app.retrieve_block_hash(self.app.state.timeslot.number)
            # TODO: max_blocks could be derived using current block timeslot and received blockhash timeslot?
            self.ce128_initiate_block_request(
                conn,
                MsgCE128BlockRequest(
                    curr_hash, #msg.header.hash,
                    MsgCE128BlockRequestDirection.ASC.value, #MsgCE128BlockRequestDirection.DESC.value,
                    10
                )
            )


    async def up0_broadcast_block(self, block: Block):
        logger.debug(f'up0_broadcast_block to {len(self.connections)} connections')

        msg = MsgUP0Announcement(
            header=block.header,
            header_hash=block.header.hash,
            timeslot=block.header.timeslot
        ).to_jam_bytes().to_bytes()

        for client_id, client in self.connections.items():
            # Check if UP0 stream is established
            if not client.is_connected():
                logger.debug(f"Skipping broadcast to {client.host}:{client.port} - connection is not fully established yet")
                continue
                
            logger.debug(f"up0_broadcast_block send block header to client {client.host}:{client.port} with hash {block.header.hash}")
            client.send(
                client.stream_up.stream_id,
                client.stream_up.create_message(msg),
                end_stream=False
            )


    def ce128_initiate_block_request(self, conn: JAMConnection, req: MsgCE128BlockRequest):
        #TODO: missch een batch param meegeven, zodat we een grotere reeks kunnen binnenhalen maar batchen...
        stream = conn.open_jam_stream(StreamBlockRequest, direction=StreamDirection.initiator)
        logger.debug(f"ce128_initiate_block_request on stream id: {stream.stream_id} direction: {req.direction}, max_block: {req.max_blocks} header hash: {req.header_hash}")
        conn.send(
            stream.stream_id,
            stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True
        )


    def ce128_received_block_request(self, stream: StreamBlockRequest, req: MsgCE128BlockRequestResponse):
        blocks = req.blocks
        logger.debug(f"ce128_received_block_request request (parsing {len(blocks)} blocks)")
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
                    if block_child_hash:
                        block = self.app.retrieve_block_by_hash(block_child_hash)
                        next_hash = block.header.hash
                    else:
                        break
                elif block_req.direction == MsgCE128BlockRequestDirection.DESC.value:
                    # Note: inclusive request block hash
                    block = self.app.retrieve_block_by_hash(next_hash)
                    if not block or block.header.timeslot == 0 or block.header.hash == bytes(32):
                        break

                    next_hash = block.header.parent
                else:
                    # TODO: error
                    raise Exception("ce128_send_block_request HMmmmmmz?????")

                blocks.append(block)

        logger.debug(f"ce128_send_block_request {len(blocks)} blocks (direction={block_req.direction} max blocks={block_req.max_blocks})")

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
            logger.debug(f"ce128_send_block_request finished")
            # stream.acceptor_reset(1) # Replaced with FIN
            stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce128_abort_block_request(self):
        logger.debug(f"ce128_abort_block_request Finished, start parsing import queue {len(self.app._import_queue)}")
        # Note: could happen during a block_request "session"
        #TODO: or do we want to clear the queue?
        asyncio.create_task(
            self.app.process_import_queue(
                on_success=MESSAGE_TYPES.CE128_SUCCESS,
                on_failure=MESSAGE_TYPES.CE128_FAILURE
            )
        )


    async def ce128_processed_block_request(self, *args, **kwargs):
        #TODO: add reason, origin/connection etc
        self.state_requesting_blocks = False


    def up0_failure(self, reset_code: int):
        logger.error(f"up0_failure with code {reset_code}")
        # TODO: handle UP0 reset, e.g., reconnect


    def ce128_block_request_failure(self, reset_code: int):
        logger.error(f"ce128_block_request_failure with code {reset_code}")
        self.state_requesting_blocks = False  # Reset state on failure


    async def ce131_initiate_distribute_own_ticket(self, data):
        #TODO: wrap in a dataclass and pass that in the signal
        epoch_index: int = data[0]
        attempt: int = data[1]
        proof: bytes = data[2]

        msg = MsgCE131SafroleTicketDistribution(
            epoch_index=epoch_index,
            ticket=MsgCE131SafroleTicket(
                attempt=attempt,
                proof=proof
            )
        )

        distributed_count = 0
        for conn in self.connections.values():
            if conn.is_connected():
                try:
                    stream = conn.open_jam_stream(StreamSafroleTicketDistributionStep1, direction=StreamDirection.initiator)
                    logger.debug(f"ce131_initiate_distribute_own_ticket on stream id: {stream.stream_id}")
                    conn.send(
                        stream.stream_id,
                        stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
                        end_stream=True
                    )

                    distributed_count += 1
                except Exception as e:
                    logger.error(f"Failed to distribute ticket to peer: {e}")

        logger.info(f"ce131_initiate_distribute_own_ticket Distributed own ticket to {distributed_count} peers")
        return distributed_count


    def ce131_received_ticket(self, stream: StreamSafroleTicketDistributionStep1, msg: MsgCE131SafroleTicketDistribution):
        logger.debug(f"ce131_received_ticket for epoch {msg.epoch_index}")
        
        # Validate epoch
        current_epoch = self.app.state.timeslot.number // EPOCH_TIMESLOTS
        if msg.epoch_index != current_epoch and msg.epoch_index != current_epoch + 1:
            logger.warning(f"ce131_received_ticket Invalid epoch index {msg.epoch_index}, current epoch is {current_epoch}")
            stream.reset(1)
            return
            
        # Verify ticket
        #TODO: create helper function from this
        try:
            # Get ring public keys from current validators
            ring_public_keys = [v.bandersnatch for v in self.app.state.safrole.validators]
            
            # Get entropy for the epoch
            entropy = self.app.state.entropy.entropy[2]
            
            # Validate the ticket using the block extrinsic accumulator
            #TODO: duplicate with Safrole.create_ticket_body???
            ticket_body = self.app.block_extrinsic.create_ticket_body(
                TicketEnvelope(attempt=msg.ticket.attempt, signature=msg.ticket.proof),
                ring_public_keys,
                entropy
            )
            
            # Check if we already have this ticket
            if ticket_body in self.app.state.safrole.ticket_accumulator:
                logger.debug(f"ce131_received_ticket Ticket already in accumulator")
                stream.reset(2)
                return
                
            # Add ticket to our accumulator
            #TODO: ticketbody can be reused from above
            self.app.block_extrinsic.add_ticket(
                TicketEnvelope(attempt=msg.ticket.attempt, signature=msg.ticket.proof),
                ring_public_keys,
                entropy
            )
            
            logger.info(f"ce131_received_ticket added for epoch {msg.epoch_index}")
            
            #TODO: check if we should forward to (proxy) nodes via CE132
            # Forward to other connections via CE132
            # for conn in self.connections.values():
            #     if conn != stream.conn and conn.is_connected():
            #         self.ce132_initiate_ticket_distribution(
            #             conn,
            #             MsgCE132SafroleTicketDistribution(
            #                 epoch_index=msg.epoch_index,
            #                 ticket=MsgCE132SafroleTicket(
            #                     attempt=msg.ticket.attempt,
            #                     proof=msg.ticket.proof
            #                 )
            #             )
            #         )
            #     logger.debug(f"ce131_received_ticket Forwarded ticket to {len(self.connections) - 1} peers via CE132")
                
        except ValueError as e:
            #TODO: register this, detect bad nodes
            logger.error(f"ce131_received_ticket Invalid ticket: {e}")
            stream.reset(3)
            return

        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce131_ticket_distribution_success(self, reset_code: int):
        logger.debug(f"ce131_ticket_distribution_success with code {reset_code}")
        # TODO: handle success, perhaps update state


    def ce131_ticket_distribution_failure(self, reset_code: int):
        logger.error(f"ce131_ticket_distribution_failure with code {reset_code}")
        # TODO: handle failure, e.g., retry or log


    def ce132_initiate_ticket_distribution(self, conn: JAMConnection, msg: MsgCE132SafroleTicketDistribution):
        stream = conn.open_jam_stream(StreamSafroleTicketDistributionStep2, direction=StreamDirection.initiator)
        logger.debug(f"ce132_initiate_ticket_distribution on stream id: {stream.stream_id}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True
        )


    def ce132_received_ticket(self, stream: StreamSafroleTicketDistributionStep2, msg: MsgCE132SafroleTicketDistribution):
        logger.debug(f"ce132_received_ticket for epoch {msg.epoch_index}")
        
        # Verify epoch index
        current_epoch = self.app.state.timeslot.number // EPOCH_TIMESLOTS
        if msg.epoch_index != current_epoch and msg.epoch_index != current_epoch + 1:
            logger.warning(f"ce132_received_ticket Invalid epoch index {msg.epoch_index}, current epoch is {current_epoch}")
            stream.reset(1)
            return
            
        # Verify ticket proof
        #TODO: duplicate code from CE131 for now, make helper function
        try:
            # Get ring public keys from current validators
            ring_public_keys = [v.bandersnatch for v in self.app.state.safrole.validators]
            
            # Get entropy for the epoch
            entropy = self.app.state.entropy.entropy[2]
            
            # Validate the ticket
            ticket_body = self.app.block_extrinsic.create_ticket_body(
                TicketEnvelope(attempt=msg.ticket.attempt, signature=msg.ticket.proof),
                ring_public_keys,
                entropy
            )
            
            # Check if we already have this ticket
            if ticket_body in self.app.state.safrole.ticket_accumulator:
                logger.debug(f"ce132_received_ticket Ticket already in accumulator (via CE132), ignoring")
                # Don't reset, just close normally as this is expected in CE132
                stream.conn.send(stream.stream_id, b'', end_stream=True)
                return
                
            # Add ticket to our accumulator
            self.app.block_extrinsic.add_ticket(
                TicketEnvelope(attempt=msg.ticket.attempt, signature=msg.ticket.proof),
                ring_public_keys,
                entropy
            )
            
            logger.info(f"ce132_received_ticket Valid ticket received via CE132 (forwarded) for epoch {msg.epoch_index}")
            
        except ValueError as e:
            logger.error(f"ce132_received_ticket Invalid ticket: {e}")
            stream.reset(3)
            return

        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce132_ticket_distribution_success(self, reset_code: int):
        logger.debug(f"ce132_ticket_distribution_success with code {reset_code}")
        # TODO: handle success, perhaps update state


    def ce132_ticket_distribution_failure(self, reset_code: int):
        logger.error(f"ce132_ticket_distribution_failure with code {reset_code}")
        # TODO: handle failure


    def ce134_initiate_sharing(self, conn: JAMConnection, sharing: MsgCE134WorkPackageSharing, bundle: MsgCE134WorkPackageBundle):
        stream = conn.open_jam_stream(StreamWorkPackageSharing, direction=StreamDirection.initiator)
        logger.debug(f"ce134_initiate_sharing on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(sharing.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=False)
        conn.send(stream.stream_id, stream.create_message(bundle.to_jam_bytes().to_bytes()), end_stream=True)


    def ce134_received_sharing(self, stream: StreamWorkPackageSharing, msg: MsgCE134WorkPackageSharing):
        logger.debug(f"ce134_received_sharing for core {msg.core_index}")
        # TODO: process mappings


    def ce134_received_bundle(self, stream: StreamWorkPackageSharing, msg: MsgCE134WorkPackageBundle):
        logger.debug(f"CE134 received bundle")
        # TODO: verify, refine
        if not self.verify_bundle(msg):
            raise ValueError("Invalid bundle")
        response = MsgCE134RefineResponse(report_hash=bytes(32), signature=bytes(64))
        stream.conn.send(stream.stream_id, stream.create_message(response.to_jam_bytes().to_bytes()), end_stream=True)


    def ce134_received_refine_response(self, stream: StreamWorkPackageSharing, msg: MsgCE134RefineResponse):
        logger.debug(f"CE134 received refine response")
        # TODO: process response
        # stream.initiator_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce134_sharing_success(self, reset_code: int):
        logger.debug(f"CE134 sharing successful with code {reset_code}")


    def ce134_sharing_failure(self, reset_code: int):
        logger.error(f"CE134 sharing failed with code {reset_code}")


    def ce141_initiate_distribution(self, conn: JAMConnection, msg: MsgCE141Assurance):
        stream = conn.open_jam_stream(StreamAssuranceDistribution, direction=StreamDirection.initiator)
        logger.debug(f"CE141 initiating distribution on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce141_received_assurance(self, stream: StreamAssuranceDistribution, msg: MsgCE141Assurance):
        logger.debug(f"CE141 received assurance")
        # TODO: process assurance
        # stream.acceptor_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce141_distribution_success(self, reset_code: int):
        logger.debug(f"CE141 distribution successful with code {reset_code}")


    def ce141_distribution_failure(self, reset_code: int):
        logger.error(f"CE141 distribution failed with code {reset_code}")


    def ce142_initiate_announcement(self, conn: JAMConnection, msg: MsgCE142PreimageAnnouncement):
        stream = conn.open_jam_stream(StreamPreimageAnnouncement, direction=StreamDirection.initiator)
        logger.debug(f"CE142 initiating announcement on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce142_received_announcement(self, stream: StreamPreimageAnnouncement, msg: MsgCE142PreimageAnnouncement):
        logger.debug(f"CE142 received announcement for hash {msg.hash.hex()}")
        # TODO: check if needed, request via CE143 if so
        # stream.acceptor_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce142_announcement_success(self, reset_code: int):
        logger.debug(f"CE142 announcement successful with code {reset_code}")


    def ce142_announcement_failure(self, reset_code: int):
        logger.error(f"CE142 announcement failed with code {reset_code}")


    def ce143_initiate_request(self, conn: JAMConnection, msg: MsgCE143HashRequest):
        stream = conn.open_jam_stream(StreamPreimageRequest, direction=StreamDirection.initiator)
        logger.debug(f"CE143 initiating request on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce143_received_request(self, stream: StreamPreimageRequest, msg: MsgCE143HashRequest):
        logger.debug(f"CE143 received request for hash {msg.hash.hex()}")
        # TODO: lookup preimage, send if available
        preimage = MsgCE143Preimage(bytes_=b'')  # placeholder
        stream.conn.send(stream.stream_id, stream.create_message(preimage.to_jam_bytes().to_bytes()), end_stream=True)


    def ce143_received_preimage(self, stream: StreamPreimageRequest, msg: MsgCE143Preimage):
        logger.debug(f"CE143 received preimage of length {len(msg.bytes_)}")
        # TODO: process preimage
        # stream.initiator_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce143_request_success(self, reset_code: int):
        logger.debug(f"CE143 request successful with code {reset_code}")


    def ce143_request_failure(self, reset_code: int):
        logger.error(f"CE143 request failed with code {reset_code}")


    def ce133_initiate_submission(self, conn: JAMConnection, submission: MsgCE133WorkPackageSubmission, extrinsic: MsgCE133Extrinsic):
        stream = conn.open_jam_stream(StreamWorkPackageSubmission, direction=StreamDirection.initiator)
        logger.debug(f"CE133 initiating submission on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(submission.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=False)
        conn.send(stream.stream_id, stream.create_message(extrinsic.to_jam_bytes().to_bytes()), end_stream=True)


    def ce133_received_submission(self, stream: StreamWorkPackageSubmission, msg: MsgCE133WorkPackageSubmission):
        logger.debug(f"CE133 received submission for core {msg.core_index}")
        # TODO: process work package


    def ce133_received_extrinsic(self, stream: StreamWorkPackageSubmission, msg: MsgCE133Extrinsic):
        logger.debug(f"CE133 received extrinsic data of length {len(msg.bytes_)}")
        # TODO: process extrinsic, close stream if successful
        # stream.acceptor_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce133_submission_success(self, reset_code: int):
        logger.debug(f"CE133 submission successful with code {reset_code}")


    def ce133_submission_failure(self, reset_code: int):
        logger.error(f"CE133 submission failed with code {reset_code}")


    def ce135_initiate_distribution(self, conn: JAMConnection, msg: MsgCE135GuaranteedWorkReport):
        stream = conn.open_jam_stream(StreamWorkReportDistribution, direction=StreamDirection.initiator)
        logger.debug(f"CE135 initiating distribution on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce135_received_report(self, stream: StreamWorkReportDistribution, msg: MsgCE135GuaranteedWorkReport):
        logger.debug(f"CE135 received work report")
        # TODO: process report
        # stream.acceptor_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce135_distribution_success(self, reset_code: int):
        logger.debug(f"CE135 distribution successful with code {reset_code}")


    def ce135_distribution_failure(self, reset_code: int):
        logger.error(f"CE135 distribution failed with code {reset_code}")


    def ce136_initiate_request(self, conn: JAMConnection, msg: MsgCE136HashRequest):
        stream = conn.open_jam_stream(StreamWorkReportRequest, direction=StreamDirection.initiator)
        logger.debug(f"CE136 initiating request on stream id: {stream.stream_id}")
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce136_received_request(self, stream: StreamWorkReportRequest, msg: MsgCE136HashRequest):
        logger.debug(f"CE136 received request for hash {msg.hash.hex()}")
        # TODO: lookup work report, send if available
        report = MsgCE136WorkReport(report=b'')  # placeholder
        stream.conn.send(stream.stream_id, stream.create_message(report.to_jam_bytes().to_bytes()), end_stream=True)


    def ce136_received_report(self, stream: StreamWorkReportRequest, msg: MsgCE136WorkReport):
        logger.debug(f"CE136 received work report of length {len(msg.report)}")
        # TODO: process report
        # stream.initiator_reset(0)
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce136_request_success(self, reset_code: int):
        logger.debug(f"CE136 request successful with code {reset_code}")


    def ce136_request_failure(self, reset_code: int):
        logger.error(f"CE136 request failed with code {reset_code}")


    def ce137_initiate_request(self, conn: JAMConnection, req: MsgCE137ShardRequest):
        stream = conn.open_jam_stream(StreamShardDistribution, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce137_received_request(self, stream: StreamShardDistribution, msg: MsgCE137ShardRequest):
        # TODO: fetch and send bundle shard, segment shards, justification
        bundle = MsgCE137BundleShard(bytes_ = b'')
        segments = [MsgCE137SegmentShard(bytes_ = b'') for _ in range(10)]
        just = MsgCE137Justification(bytes_ = b'')
        stream.conn.send(stream.stream_id, stream.create_message(bundle.to_jam_bytes().to_bytes()), end_stream=False)
        for s in segments:
            stream.conn.send(stream.stream_id, stream.create_message(s.to_jam_bytes().to_bytes()), end_stream=False)
        stream.conn.send(stream.stream_id, stream.create_message(just.to_jam_bytes().to_bytes()), end_stream=True)


    def ce137_received_shard(self, stream: StreamShardDistribution, bundle, segments, just):
        # TODO: process
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce137_distribution_success(self, code: int):
        logger.debug(f"CE137 success {code}")


    def ce137_distribution_failure(self, code: int):
        logger.error(f"CE137 failure {code}")


    # Similar for CE138, CE139, CE140
    def ce138_initiate_request(self, conn: JAMConnection, req: MsgCE138ShardRequest):
        stream = conn.open_jam_stream(StreamAuditShardRequest, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce138_received_request(self, stream: StreamAuditShardRequest, msg: MsgCE138ShardRequest):
        # TODO: send bundle shard and justification
        bundle = MsgCE138BundleShard(bytes_ = b'')
        just = MsgCE138Justification(bytes_ = b'')
        stream.conn.send(stream.stream_id, stream.create_message(bundle.to_jam_bytes().to_bytes()), end_stream=False)
        stream.conn.send(stream.stream_id, stream.create_message(just.to_jam_bytes().to_bytes()), end_stream=True)


    def ce138_received_shard(self, stream: StreamAuditShardRequest, bundle, just):
        # TODO: process
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce138_request_success(self, code: int):
        logger.debug(f"CE138 success {code}")


    def ce138_request_failure(self, code: int):
        logger.error(f"CE138 failure {code}")


    def ce139_initiate_request(self, conn: JAMConnection, req: MsgCE139SegmentRequest):
        stream = conn.open_jam_stream(StreamSegmentShardRequest, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce139_received_request(self, stream: StreamSegmentShardRequest, msg: MsgCE139SegmentRequest):
        # TODO: send segment shards
        shards = [MsgCE139SegmentShard(bytes_ = b'') for _ in msg.segment_indices]
        for s in shards:
            stream.conn.send(stream.stream_id, stream.create_message(s.to_jam_bytes().to_bytes()), end_stream=(s == shards[-1]))


    def ce139_received_shards(self, stream: StreamSegmentShardRequest, shards):
        # TODO: process
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce139_request_success(self, code: int):
        logger.debug(f"CE139 success {code}")


    def ce139_request_failure(self, code: int):
        logger.error(f"CE139 failure {code}")


    def ce140_initiate_request(self, conn: JAMConnection, req: MsgCE140SegmentRequest):
        stream = conn.open_jam_stream(StreamSegmentShardRequestJustification, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(req.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce140_received_request(self, stream: StreamSegmentShardRequestJustification, msg: MsgCE140SegmentRequest):
        # TODO: send shards and justifications
        for idx in msg.segment_indices:
            shard = MsgCE140SegmentShard(bytes_ = b'')
            just = MsgCE140Justification(bytes_ = b'')
            stream.conn.send(stream.stream_id, stream.create_message(shard.to_jam_bytes().to_bytes()), end_stream=False)
            stream.conn.send(stream.stream_id, stream.create_message(just.to_jam_bytes().to_bytes()), end_stream=(idx == msg.segment_indices[-1]))


    def ce140_received_shards_justified(self, stream: StreamSegmentShardRequestJustification, data):
        # TODO: parse and process
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce140_request_success(self, code: int):
        logger.debug(f"CE140 success {code}")


    def ce140_request_failure(self, code: int):
        logger.error(f"CE140 failure {code}")


    def ce144_initiate_announcement(self, conn: JAMConnection, ann: MsgCE144Announcement, evidence: MsgCE144Evidence):
        stream = conn.open_jam_stream(StreamAuditAnnouncement, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(ann.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=False)
        conn.send(stream.stream_id, stream.create_message(evidence.to_jam_bytes().to_bytes()), end_stream=True)


    def ce144_received_announcement(self, stream: StreamAuditAnnouncement, msg: MsgCE144Announcement):
        # TODO: process announcement
        pass


    def ce144_received_evidence(self, stream: StreamAuditAnnouncement, msg: MsgCE144Evidence):
        # TODO: process evidence
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce144_announcement_success(self, code: int):
        logger.debug(f"CE144 success {code}")


    def ce144_announcement_failure(self, code: int):
        logger.error(f"CE144 failure {code}")


    def ce145_initiate_publication(self, conn: JAMConnection, msg: MsgCE145JudgmentPublication):
        stream = conn.open_jam_stream(StreamJudgmentPublication, direction=StreamDirection.initiator)
        conn.send(stream.stream_id, stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True), end_stream=True)


    def ce145_received_judgment(self, stream: StreamJudgmentPublication, msg: MsgCE145JudgmentPublication):
        # TODO: process judgment
        stream.conn.send(stream.stream_id, b'', end_stream=True)


    def ce145_publication_success(self, code: int):
        logger.debug(f"CE145 success {code}")


    def ce145_publication_failure(self, code: int):
        logger.error(f"CE145 failure {code}")


    # Temp placeholders
    def verify_ticket_proof(self, msg):
        return True

    def verify_bundle(self, msg):
        return True


def create_jam_connection(protocol: JAMNPS, quic_connection: JAMConnection, direction: StreamDirection, host: str, port: int):
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
