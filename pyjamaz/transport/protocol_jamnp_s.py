import asyncio
import logging
import struct
import ssl

from typing import Dict, Optional
from typing import Optional, cast

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect


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
        # Structure `Final`, `Leaf`, `Handshake` as per protocol
        # This is a placeholder; replace with actual message structure
        final = b'\x00' * 32  # Final block header hash and slot placeholder
        leaves = [b'\x00' * 36]  # List of leaves with Header Hash + Slot
        leaves_encoded = b"".join(leaves)
        handshake_message = final + struct.pack("<I", len(leaves)) + leaves_encoded
        handshake_message = b"1"
        return handshake_message


class ServerProtocol(JAMNPSProtocol):

    async def send_block_announcement(self, block_data):
        self._quic.send_stream_data(self.stream_up_0, block_data)
        self.transmit()
        print("Block announcement sent to", self, self.stream_up_0)

    def quic_event_received(self, event: QuicEvent):
        print("!!!SERVER: ", event)
        if isinstance(event, HandshakeCompleted):
            # print("Handshake with peer completed.")
            # if self._quic.configuration.alpn_protocols[0] != "jamnp-s/0/H":
            #     self._quic.close()
            #     return
            self.client_id = id(self)
            self.host.conn_in[self.client_id] = self  # Store reference for broadcasting
            print(f"New incomming connection {self.client_id} connected.")

        #TODO: remove connections on connection closed/lost etc

        elif isinstance(event, StreamDataReceived):
            print("SERVER: ", event.data)
            # payload = str(event.data[:2]).replace("CLIENT ", "").encode('utf-8')
            # #payload = struct.unpack("!H", bytes(tt))
            #
            # msg = bytes(f"SERVER {payload}", 'utf-8')
            # data = struct.pack("!H", len(msg)) + msg
            # print("SERVER SENDING DATA: ", data)
            # self._quic.send_stream_data(event.stream_id, data, end_stream=True)
            # if len(event.data) >= 36:  # Handshake or Announcement
            #     self.process_handshake_or_announcement(event.data)
            if self.stream_up_0 is None:
                self.stream_up_0 = event.stream_id

            if event.stream_id == self.stream_up_0:
                # Process incoming data (either handshake or announcement)
                #self.process_up0_message(event.data)
                print("PROCESS UP 0 MESSAGE", self, event.stream_id)
                #self._quic.send_stream_data(event.stream_id, b"HUH??", end_stream=True)
                self._quic.send_stream_data(event.stream_id, b"HUH??")

    # def process_handshake_or_announcement(self, data):
    #     # Handshake/Announcement structure
    #     # Final (Header Hash + Slot), followed by list of known leaves in handshake
    #     header_hash = data[:32]  # Extract header hash
    #     slot = unpack("<I", data[32:36])[0]  # Extract slot
    #     print(f"Received Handshake/Announcement with Header Hash: {header_hash.hex()}, Slot: {slot}")
    #     # If more data, parse known leaves (Handshake), otherwise this may be an announcement
    #     if len(data) > 36:
    #         leaves = []
    #         offset = 36
    #         while offset < len(data):
    #             leaf_hash = data[offset:offset + 32]
    #             leaf_slot = unpack("<I", data[offset + 32:offset + 36])[0]
    #             leaves.append((leaf_hash.hex(), leaf_slot))
    #             offset += 36
    #         print(f"Received Handshake with leaves: {leaves}")
    #     else:
    #         print("Received block announcement.")


class ClientProtocol(JAMNPSProtocol):

    def quic_event_received(self, event: QuicEvent) -> None:
        print("!!!CLIENT: quic_event_received", event)
        if isinstance(event, StreamDataReceived):
            print("RECEIVED DATA:", event.data)
            #TODO: raise asyncio event(block_data)
            #received = struct.unpack("!H", bytes(event.data[:2]))[0]

    async def handle_stream_data(self, stream_id, data, fin):
        if stream_id == self.stream_up_0:
            if not fin:
                self.process_announcement(data)

    def process_announcement(self, data):
        # Unpack the data as per protocol definitions for Handshake and Announcement structures
        # Example: parse `Final`, `Leaf`, or `Announcement` messages
        print("Received block announcement:", data)

    async def open_stream_up_0(self):
        # Initiate UP 0 stream by sending the Handshake message
        self.stream_up_0 = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(
            self.stream_up_0,
            self.build_handshake_message(),
        )
        print("Block announcement stream opened")


    # async def query(self, msg: str):
    #     msg = bytes(f"CLIENT {msg}", 'utf-8')
    #     data = struct.pack("!H", len(msg)) + msg
    #
    #     # send query and wait for answer
    #     stream_id = self._quic.get_next_available_stream_id()
    #     self._quic.send_stream_data(stream_id, data, end_stream=True)
    #     print("SEND DATA: ", data)
    #     waiter = self._loop.create_future()
    #     self.transmit()
    #
    #     return await asyncio.shield(waiter)

    # async def send_initial_data(self, data=b"CONNECT"):
    #     # Wait until the handshake is complete
    #     await self._handshake_completed.wait()
    #     # Open a new stream and send data
    #     stream_id = self._quic.get_next_available_stream_id()
    #     self._quic.send_stream_data(stream_id, data, end_stream=True)
    #     self.transmit()
    #
    # def quic_event_received(self, event):
    #     if isinstance(event, StreamDataReceived):
    #         stream_id = event.stream_id
    #         data = event.data
    #         end_stream = event.end_stream
    #         # Handle received data
    #         print(f"Received data on stream {stream_id}: {data.decode()}")
    #         if end_stream:
    #             # Optionally close the stream
    #             pass
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination
    #         print("Connection terminated")


class SessionTicketStore:

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


class JAMNPS(object):

    #PROTOCOL_NAME = "jamnp-s/0/00000000"
    PROTOCOL_NAME = "test"

    def __init__(self, app, host, port, certificate, private_key):
        self.app = app
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
        configuration.idle_timeout = 300000  # Set idle timeout to 5 minutes

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

    async def broadcast_block_announcement(self, block):
        for client_id, client in self.conn_in.items():
            print("SENDING TO CLIENT: ", client_id, client)
            await client.send_block_announcement(block)
