import asyncio
from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived


class EchoClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_received = asyncio.Event()

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("Handshake with server completed.")
            # Send a message after the handshake
            stream_id = self._quic.get_next_available_stream_id()
            self._quic.send_stream_data(stream_id, b"Hello, Server!", end_stream=True)

        elif isinstance(event, StreamDataReceived):
            print(f"Response from server: {event.data.decode()}")
            self.response_received.set()

    async def wait_for_response(self):
        await self.response_received.wait()


async def main():
    configuration = QuicConfiguration(is_client=True)
    configuration.load_verify_locations("./bak/tests/cert.pem")  # Path to the server certificate

    # Connect to the server and use the EchoClientProtocol
    async with connect(
        "::1",
        9000,
        configuration=configuration,
        create_protocol=EchoClientProtocol,
    ) as protocol:
        assert isinstance(protocol, EchoClientProtocol)
        await protocol.wait_for_response()


if __name__ == "__main__":
    asyncio.run(main())
