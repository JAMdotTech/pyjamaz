import asyncio
import logging
import struct
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
from jamcodec.base import JamBytes

from pyjamaz.models.block import Block

logger = logging.getLogger("jamnps")


def wrap_protocol(host, protocol):
    def create_protocol(*args, **kwargs):
        instance = protocol(*args, **kwargs)
        instance.host = host
        return instance

    return create_protocol


class JAMNPSProtocol(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = None    # Note: should be set in wrap_protocol
        self.stream_up_0 = None

    def build_handshake_message(self):
        #TODO:
        return b"1"


class ServerProtocol(JAMNPSProtocol):

    async def send_block_announcement(self, block_bytes):
        if self.stream_up_0 is None:
            raise Exception("NO UP 0 block_announcement channel opend yet??")

        self._quic.send_stream_data(self.stream_up_0, (len(block_bytes).to_bytes(length=4, byteorder='little')) + block_bytes)
        self.transmit()
        #TODO: nodig? https://superfastpython.com/asyncio-shield/
        #waiter = self._loop.create_future()
        #self.transmit()
        #return await asyncio.shield(waiter)
        print("SERVER: Block announcement sent to", self, self.stream_up_0, len(block_bytes))

    def quic_event_received(self, event: QuicEvent):
        print("!!!SERVER EVENT:", event)
        if isinstance(event, HandshakeCompleted):
            # TODO: check client certificate
            # print("Handshake with peer completed.")
            # if self._quic.configuration.alpn_protocols[0] != "jamnp-s/0/00000000":
            #     self._quic.close()
            #     return
            self.client_id = id(self)
            self.host.conn_in[self.client_id] = self  # Store reference for broadcasting
            print(f"SERVER: New incomming connection {self.client_id} connected.")

        #TODO: remove connections on connection closed/lost etc

        elif isinstance(event, StreamDataReceived):
            print("SERVER RECEIVED: ", event.data)
            if self.stream_up_0 is None:
                self.stream_up_0 = event.stream_id
                print("SETTING CHANNEL: ", self.stream_up_0)

            if event.stream_id == self.stream_up_0:
                # Process incoming data (either handshake or announcement)
                print("Server: Opened UP 0 Block announcement stream", self, event.stream_id)

    # TODO: handle graceful
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination
    #         print("Connection terminated")


class ClientProtocol(JAMNPSProtocol):

    def quic_event_received(self, event: QuicEvent) -> None:
        print("!!!CLIENT EVENT: quic_event_received", event)
        if isinstance(event, StreamDataReceived):
            print("CLIENT RECEIVED:", event.data)
            #received = struct.unpack("!H", bytes(event.data[:2]))[0]
            #TODO: raise asyncio event(block_bytes)
            byte_data = bytes(event.data)
            #msg_type = byte_data[0]
            msg_type = JAMNPS.MSG.UP0_BlockAnnouncement
            msg_len = int.from_bytes(byte_data[0:4], byteorder='little')
            #TODO: hoe differentieren tussen een lopende stream en een nieuwe message?
            match msg_type:
                case JAMNPS.MSG.UP0_BlockAnnouncement:
                    #block = Block.from_jam_bytes(JamBytes(byte_data[4:(4+msg_len)]))
                    pass

    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination
    #         print("Connection terminated")

    async def open_stream_up_0(self):
        # Initiate UP 0 stream by sending the Handshake message
        self.stream_up_0 = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(
            self.stream_up_0,
            self.build_handshake_message(),
        )
        print("CLIENT: Block announcement stream opened")


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

    def __init__(self, host, port, certificate, private_key):
        self.host = host
        self.port = port
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

        logger.debug(f"Connecting to {host}:{port}")
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

    async def broadcast_block_announcement(self, block_bytes):
        print("self.conn_in", self.conn_in)
        for client_id, client in self.conn_in.items():
            print("SERVER: SENDING TO CLIENT: ", client_id, client)
            await client.send_block_announcement(block_bytes)
