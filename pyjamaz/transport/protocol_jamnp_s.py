import asyncio
import logging
import struct
import ssl

from typing import Dict, Optional
from typing import Optional, cast

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket

from aioquic.asyncio.client import connect


logger = logging.getLogger("jamnps")


class ServerProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event: QuicEvent):
        #print("SERVER quic_event_received", event)
        if isinstance(event, StreamDataReceived):
            print("SERVER: ", event.data)
            payload = str(event.data[:2]).replace("CLIENT ", "").encode('utf-8')
            #payload = struct.unpack("!H", bytes(tt))

            msg = bytes(f"SERVER {payload}", 'utf-8')
            data = struct.pack("!H", len(msg)) + msg
            print("SERVER SENDING DATA: ", data)
            self._quic.send_stream_data(event.stream_id, data, end_stream=True)


class ClientProtocol(QuicConnectionProtocol):

    async def query(self, msg: str):
        msg = bytes(f"CLIENT {msg}", 'utf-8')
        data = struct.pack("!H", len(msg)) + msg

        # send query and wait for answer
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, data, end_stream=True)
        print("SEND DATA: ", data)
        waiter = self._loop.create_future()
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        print("CLIENT: quic_event_received", event)
        if isinstance(event, StreamDataReceived):
            received = struct.unpack("!H", bytes(event.data[:2]))[0]
            print("RECEIVED DATA:", event.data)

    #
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


    def __init__(self, host, port, certificate, private_key):
        self.host = host
        self.port = port
        self.session_ticket_store = SessionTicketStore()
        self.configuration = QuicConfiguration(
            alpn_protocols=[JAMNPS.PROTOCOL_NAME],
            is_client=False,
            verify_mode=ssl.CERT_NONE
            #quic_logger=quic_logger,
        )
        self.cert = certificate
        self.pk = private_key
        self.configuration.load_cert_chain(certificate, private_key)
        self.connections = {}

        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            level=logging.DEBUG,
        )

    async def listen(self):
        await serve(
            self.host,
            self.port,
            configuration=self.configuration,
            create_protocol=ServerProtocol,
            session_ticket_fetcher=self.session_ticket_store.pop,
            session_ticket_handler=self.session_ticket_store.add,
            retry=True,
        )

    async def connect(self, host, port):
        configuration = QuicConfiguration(alpn_protocols=[JAMNPS.PROTOCOL_NAME], is_client=True, verify_mode=ssl.CERT_NONE)
        configuration.load_cert_chain(certfile=self.cert, keyfile=self.pk)

        logger.debug(f"Connecting to {host}:{port}")
        async with connect(
                host,
                port,
                configuration=configuration,
                # session_ticket_handler=save_session_ticket,
                create_protocol=ClientProtocol,
        ) as client:
            print("CLIENT SEND QUERY")
            client = cast(ClientProtocol, client)
            self.connections[(host, port)] = client
            await client.wait_closed()
            del self.connections[(host, port)]
