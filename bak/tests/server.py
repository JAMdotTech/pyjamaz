import argparse
import asyncio
import logging
import ssl
import struct
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, ProtocolNegotiated, HandshakeCompleted
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket


class TestProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event: QuicEvent):
        #print("EVENT RECEIVED: ", event)
        #self._quic.tls.certificate
        # if isinstance(event, ProtocolNegotiated):
        #     import pdb;pdb.set_trace()
        # if isinstance(event, HandshakeCompleted):
        #     import pdb;pdb.set_trace()
        if isinstance(event, StreamDataReceived):
            print("RECEIVED DATA: ", event.data)
            payload = str(event.data[:2]).replace("CLIENT ", "").encode('utf-8')
            #payload = struct.unpack("!H", bytes(tt))

            msg = bytes(f"SERVER {payload}", 'utf-8')
            data = struct.pack("!H", len(msg)) + msg
            print("SENDING DATA: ", data)
            self._quic.send_stream_data(event.stream_id, data, end_stream=True)


class SessionTicketStore:

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


def server_verify_certificate(*args, **kwargs):
    # Perform custom validation
    import pdb;pdb.set_trace()
    #valid = validate_peer_certificate(certificates)
    # if not valid:
    #     raise ssl.SSLError("Invalid peer certificate")
    return



async def main(
    host: str,
    port: int,
    configuration: QuicConfiguration,
    session_ticket_store: SessionTicketStore,
    retry: bool,
) -> None:
    await serve(
        host,
        port,
        configuration=configuration,
        create_protocol=TestProtocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
        retry=retry,
    )
    await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DNS over QUIC server")
    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=853,
        help="listen on the specified port (defaults to 853)",
    )
    parser.add_argument(
        "-k",
        "--private-key",
        type=str,
        help="load the TLS private key from the specified file",
    )
    parser.add_argument(
        "-c",
        "--certificate",
        type=str,
        required=True,
        help="load the TLS certificate from the specified file",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="send a retry for new connections",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    # create QUIC logger
    if args.quic_log:
        quic_logger = QuicFileLogger(args.quic_log)
    else:
        quic_logger = None

    configuration = QuicConfiguration(
        alpn_protocols=["test"],
        is_client=False,
        quic_logger=quic_logger,
        #verify_mode=ssl.CERT_NONE,
        #verify_certificate=server_verify_certificate
        #verify_certificate_callback=server_verify_certificate
        #?????https://github.com/aiortc/aioquic/blob/main/tests/test_tls.py#L24
        #def handshake_with_client_input_corruption(
    )

    #import pdb;pdb.set_trace()
    #configuration._request_client_certificate = True
    configuration.load_cert_chain(args.certificate, args.private_key)

    try:
        asyncio.run(
            main(
                host=args.host,
                port=args.port,
                configuration=configuration,
                session_ticket_store=SessionTicketStore(),
                retry=args.retry,
            )
        )
    except KeyboardInterrupt:
        pass