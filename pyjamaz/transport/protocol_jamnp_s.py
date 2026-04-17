import logging
import ssl
from enum import Enum

from typing import Dict, Optional, cast

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect
from jamcodec.base import JamBytes
from jamcodec.types import Vec

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.models.block import Block
from pyjamaz.settings import JAMNPS_MAX_MESSAGE_SIZE
from pyjamaz.transport.framing import JAMNPSFrameParser, InvalidJAMNPSMessage, encode_frame
from pyjamaz.transport.pubsub import PubSubSignal
from pyjamaz.transport.types import ProtocolType


logger = logging.getLogger("pyjamaz.transport")


def wrap_protocol(wrapper, protocol):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.wrapper = wrapper
        return instance

    return create_protocol


class JAMNPSProtocol(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrapper = None    # Note: should be set in wrap_protocol
        self.stream_up_0 = None

        # Keep parsing state per stream so fragmented and concatenated frames cannot desynchronize each other.
        self._stream_parsers: dict[int, JAMNPSFrameParser] = {}

    def _get_parser(self, stream_id: int) -> JAMNPSFrameParser:
        if stream_id not in self._stream_parsers:
            self._stream_parsers[stream_id] = JAMNPSFrameParser(
                max_payload_size=JAMNPS_MAX_MESSAGE_SIZE
            )
        return self._stream_parsers[stream_id]

    @staticmethod
    def encode_frame(msg_type: int, payload: bytes) -> bytes:
        return encode_frame(msg_type, payload)

    def build_handshake_message(self):
        #TODO: implement handshake response according to JAMSNP
        """Both sides should begin by sending a handshake message containing all known leaves (descendants of the latest finalized block with no known children)."""
        logger.debug(f"Building handshake message for UP-0 stream")
        return self.encode_frame(JAMNPS.MSG.UP0_OPEN.value, b"")


class ServerProtocol(JAMNPSProtocol):

    async def send_block_announcement(self, block_bytes):
        if self.stream_up_0 is None:
            raise Exception("NO UP 0 block_announcement channel opend yet??")

        """
        TODO:
        For now we only send length++, we should send:
            Final = Header Hash ++ Slot
            Leaf = Header Hash ++ Slot
            Handshake = Final ++ len++[Leaf]
            Announcement = Header ++ Final
        """
        self._quic.send_stream_data(
            self.stream_up_0,
            self.encode_frame(JAMNPS.MSG.UP0_BlockAnnouncement.value, block_bytes)
        )
        self.transmit()
        logger.debug(f"ServerProtocol Block announcement sent to stream {self.stream_up_0} ({len(block_bytes)})")

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, HandshakeCompleted):
            # TODO: check client certificate and alpn
            # if self._quic.configuration.alpn_protocols[0] != "jamnp-s/0/00000000":
            #     self._quic.close()
            #     return

            self.client_id = id(self)
            self.wrapper.conn_in[self.client_id] = self  # Store reference for broadcasting

            logger.debug(f'ServerProtocol new connected client #{self.client_id}')

        #TODO: remove connections on connection closed/lost etc

        elif isinstance(event, StreamDataReceived):
            logger.debug(f'Server received data: {event.data}')

            if self.stream_up_0 is None:
                self.stream_up_0 = event.stream_id
                logger.debug(f'ServerProtocol new UP-0 stream ({self.stream_up_0}) for client #{self.client_id}')

            # if event.stream_id == self.stream_up_0:
            #     # Process incoming data (either handshake or announcement)
            #     logger.debug(f'ServerProtocol new UP-0 stream ({self.stream_up_0}) for client #{self.client_id}')

            try:
                frames = self._get_parser(event.stream_id).feed_data(bytes(event.data))
            except InvalidJAMNPSMessage as exc:
                logger.warning(f"ServerProtocol invalid frame on stream {event.stream_id}: {exc}")
                self._stream_parsers.pop(event.stream_id, None)
                return

            for msg_type, payload in frames:
                logger.debug(f'ServerProtocol new message {msg_type} ({len(payload)} bytes)')

                match msg_type:
                    case JAMNPS.MSG.UP0_OPEN.value:
                        logger.debug(f'ServerProtocol PARSED UP-0')

                    case JAMNPS.MSG.CE128_BlockRequest.value:
                        logger.debug(f'ServerProtocol RECEIVED NEW BLOCKSREQUEST')
                        direction = 1
                        max_blocks = 1000
                        block = Block.from_jam_bytes(JamBytes(payload))

                        logger.debug(
                            f"ServerProtocol Block Requests received {self.stream_up_0} direction: {direction}, max_blocks: {max_blocks}, block: {block.header.timeslot}"
                        )

                        blocks = []
                        #TODO: take direction and max_blocks into account
                        #TODO: we decode and serialize blocks unnecessary here, improve!
                        #TODO: check the max blocks and a hardcoded max of X
                        while block.header.parent != bytes(32):
                            block = self.wrapper.app.retrieve_block_by_hash(block.header.parent)
                            if not block:
                                break
                            blocks.append(block)

                        block_list = Vec(Block.to_codec_def()).new()
                        serialized_blocks = block_list.encode([b.to_jam_bytes() for b in blocks])

                        logger.debug(
                            f"ServerProtocol Block Requests sending {len(blocks)} blocks"
                        )

                        self._quic.send_stream_data(
                            self.stream_up_0,
                            self.encode_frame(JAMNPS.MSG.CE128_BlockRequest.value, serialized_blocks.to_bytes())
                        )
                        self.transmit()

                    case _:
                        raise InvalidJAMNPSMessage(f"Invalid JAMNPS message: {msg_type}")

        elif isinstance(event, ConnectionTerminated):
            # Handle connection termination
            if id(self) in self.wrapper.conn_in:
                logger.debug(f'Client #{self.client_id} disconnected')
                # print(f'Client #{self.client_id} disconnected')
                del self.wrapper.conn_in[id(self)]


class ClientProtocol(JAMNPSProtocol):

    async def send_blocks_request(self, direction, max_blocks, block_bytes):
        #TODO: moet over een nieuwe stream/connectie?? misbruiken voor nu de up0 stream
        data = (
            # int(direction).to_bytes(length=1, byteorder='little') +
            # int(max_blocks).to_bytes(length=1, byteorder='little') +
            block_bytes
        )
        self._quic.send_stream_data(
            self.stream_up_0,
            self.encode_frame(JAMNPS.MSG.CE128_BlockRequest.value, data)
        )
        self.transmit()
        logger.debug(f"ClientProtocol Block Requests sent to stream {self.stream_up_0} ({len(data)})")


    def quic_event_received(self, event: QuicEvent) -> None:
        logger.debug(f'ClientProtocol received data')

        if isinstance(event, StreamDataReceived):

            try:
                frames = self._get_parser(event.stream_id).feed_data(bytes(event.data))
            except InvalidJAMNPSMessage as exc:
                logger.warning(f"ClientProtocol invalid frame on stream {event.stream_id}: {exc}")
                self._stream_parsers.pop(event.stream_id, None)
                return

            for msg_type, payload in frames:
                logger.debug(
                    f'ClientProtocol new message {msg_type} ({len(payload)} bytes)'
                )

                match msg_type:
                    case JAMNPS.MSG.UP0_BlockAnnouncement.value:
                        logger.debug(f'ClientProtocol RECEIVED_BLOCK: {len(payload)}')
                        self.wrapper.broadcaster.send_stream.send_nowait(
                            PubSubSignal(topic=MESSAGE_TYPES.RECEIVED_BLOCK, data=payload)
                        )

                    case JAMNPS.MSG.CE128_BlockRequest.value:
                        logger.debug(f'ClientProtocol RECEIVED REQUESTED BLOCKS: {len(payload)}')
                        self.wrapper.broadcaster.send_stream.send_nowait(
                            PubSubSignal(topic=MESSAGE_TYPES.REQUESTED_BLOCKS, data=payload)
                        )

                    case _:
                        raise InvalidJAMNPSMessage(f"Invalid JAMNPS message: {msg_type}")

    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination

    async def open_stream_up_0(self):
        # Initiate UP 0 stream by sending the
        self.stream_up_0 = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(
            self.stream_up_0,
            self.build_handshake_message(),
        )
        logger.debug(f'ClientProtocol Block announcement stream opened')


class SessionTicketStore:

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


class JAMNPS(ProtocolType):

    class MSG(Enum):
        UP0_OPEN: int = 66
        UP0_BlockAnnouncement: int = 0
        CE128_BlockRequest: int = 128

    #TODO: 00000000 -> vervang met de eerste 8 nibbles vd genesis header hash op __init__
    PROTOCOL_NAME = "jamnp-s/0/00000000"

    #                 (host, port, certificate_file, pk_file, app, 0, "0259fbe9b7dd6f3ce7d7027d87453e886bf39ea902b7bae59af1d3c63b2db4ec")
    def __init__(self, host, port, certificate, private_key, app):
        self.host = host
        self.port = port
        self.broadcaster = app.pubsub
        self.app = app
        self.session_ticket_store = SessionTicketStore()
        self.configuration = QuicConfiguration(
            alpn_protocols=[JAMNPS.PROTOCOL_NAME],
            is_client=False,
            #quic_logger=quic_logger,
            #verify_mode=ssl.CERT_REQUIRED
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
            create_protocol=wrap_protocol(self, ServerProtocol),
            session_ticket_fetcher=self.session_ticket_store.pop,
            session_ticket_handler=self.session_ticket_store.add,
            retry=True,
        )

    async def connect(self, host, port):
        configuration = QuicConfiguration(
            alpn_protocols=[JAMNPS.PROTOCOL_NAME],
            is_client=True,
            #verify_mode=ssl.CERT_REQUIRED
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
                    create_protocol=wrap_protocol(self, ClientProtocol),
            ) as client:
                client = cast(ClientProtocol, client)
                self.conn_out[(host, port)] = client
                await client.open_stream_up_0()
                await client.wait_closed()
                del self.conn_out[(host, port)]
        except ConnectionError:
            if (host, port) in self.conn_out:
                del self.conn_out[(host, port)]
            logger.debug(f"💩 ClientProtocol Cannot connect to {host}:{port}")


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
