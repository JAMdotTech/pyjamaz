import logging
import ssl
from enum import Enum

from typing import Dict, Optional
from typing import Optional, cast

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect

from pyjamaz.constants import MESSAGE_TYPES


logger = logging.getLogger("JAMNPSProtocol")
logger.setLevel(logging.DEBUG) #TODO: tmp!


def wrap_protocol(wrapper, protocol):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.wrapper = wrapper
        return instance

    return create_protocol


class InvalidJAMNPSMessage(Exception):
    pass


class JAMNPSProtocol(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrapper = None    # Note: should be set in wrap_protocol
        self.stream_up_0 = None
        #TODO: this buffer should be made per stream_id (for now, we always assume stream_up_0)
        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1

    def _reset_msg(self):
        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1

    def build_handshake_message(self):
        #TODO: implement handshake response according to JAMSNP
        """Both sides should begin by sending a handshake message containing all known leaves (descendants of the latest finalized block with no known children)."""
        return b"1"


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
        self._quic.send_stream_data(self.stream_up_0, (len(block_bytes).to_bytes(length=4, byteorder='little')) + block_bytes)
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

            logger.info(f'ServerProtocol new connected client #{self.client_id}')

        #TODO: remove connections on connection closed/lost etc

        elif isinstance(event, StreamDataReceived):
            logger.debug(f'Server received data: {event.data}')

            if self.stream_up_0 is None:
                self.stream_up_0 = event.stream_id

            if event.stream_id == self.stream_up_0:
                # Process incoming data (either handshake or announcement)
                logger.info(f'ServerProtocol new UP-0 stream ({self.stream_up_0}) for client #{self.client_id}')

        elif isinstance(event, ConnectionTerminated):
            # Handle connection termination
            if id(self) in self.wrapper.conn_in:
                del self.wrapper.conn_in[id(self)]


class ClientProtocol(JAMNPSProtocol):

    def quic_event_received(self, event: QuicEvent) -> None:
        logger.debug(f'ClientProtocol received data')

        if isinstance(event, StreamDataReceived):

            #TODO: for now we only support 1 stream (UP-0)
            #stream_id = event.stream_id
            #stream = self._get_or_create_stream(stream_id)

            byte_data = bytes(event.data)
            bytes_left = byte_data

            # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
            while len(bytes_left) > 0:

                #TODO: do this per channel
                if not self._msg_buffer:
                    # Note: first message always contains expected message length
                    self._msg_len = int.from_bytes(byte_data[0:4], byteorder='little') + 4
                    # TODO: msg_type is hardcoded to UP0_BlockAnnouncement for now
                    self._msg_type = JAMNPS.MSG.UP0_BlockAnnouncement
                    logger.debug(f'ClientProtocol received UP0_BlockAnnouncement')

                nr_bytes_remaining = self._msg_len-len(self._msg_buffer)
                self._msg_buffer += bytes_left[:nr_bytes_remaining]
                bytes_left = bytes_left[nr_bytes_remaining:]

                # If we assembled a new message, parse it
                if 0 < self._msg_len == len(self._msg_buffer):

                    match self._msg_type:

                        case JAMNPS.MSG.UP0_BlockAnnouncement:
                            self.wrapper.broadcaster.send_stream.send_nowait({"message_type": MESSAGE_TYPES.IMPORT_BLOCK_BYTES, "data": self._msg_buffer[4:self._msg_len]})
                            self._reset_msg()

                        case _:
                            raise InvalidJAMNPSMessage(f"Invalid JAMNPS message: {self._msg_type}")


    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination

    async def open_stream_up_0(self):
        # Initiate UP 0 stream by sending the Handshake message
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


class JAMNPS(object):

    class MSG(Enum):
        UP0_BlockAnnouncement: int = 0

    #TODO: 00000000 -> vervang met de eerste 8 nibbles vd genesis header hash op __init__
    PROTOCOL_NAME = "jamnp-s/0/00000000"


    def __init__(self, host, port, certificate, private_key, broadcaster):
        self.host = host
        self.port = port
        self.broadcaster = broadcaster
        self.session_ticket_store = SessionTicketStore()
        self.configuration = QuicConfiguration(
            alpn_protocols=[JAMNPS.PROTOCOL_NAME],
            is_client=False,
            #quic_logger=quic_logger,
            #verify_mode=ssl.CERT_REQUIRED
            verify_mode=ssl.CERT_NONE
        )
        self.cert = certificate
        self.pk = private_key
        self.configuration.load_cert_chain(certificate, private_key)
        self.conn_in = {}   # All incomming connections
        self.conn_out = {}  # All outgoing connections (who we connect to)

        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            level=logging.DEBUG,
        )

    async def listen(self):
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
            verify_mode=ssl.CERT_NONE
        )
        configuration.load_cert_chain(certfile=self.cert, keyfile=self.pk)
        #configuration.idle_timeout = 300000  # Set idle timeout to 5 minutes

        logger.info(f"ClientProtocol Connecting to {host}:{port}")
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
            logger.info(f"💩 ClientProtocol Cannot connect to {host}:{port}")


    async def broadcast_block(self, block):
        block_bytes = block.to_jam_bytes().to_bytes()
        for client_id, client in self.conn_in.items():
            logger.debug(f"send block to client {client}")
            await client.send_block_announcement(block_bytes)
