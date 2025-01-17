# Server script
import asyncio
from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived

class EchoServerProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        # Handle Handshake Completed event
        if isinstance(event, HandshakeCompleted):
            print("Handshake completed with client.")

        # Handle Stream Data Received event
        if isinstance(event, StreamDataReceived):
            print(f"Received: {event.data.decode()} on stream {event.stream_id}")
            # Echo back the message
            #asyncio.create_task(self._send_response(event.stream_id, event.data))
            asyncio.create_task(self._send_response(event.stream_id, b"Hello, Client!"))

    async def _send_response(self, stream_id, data):
        self._quic.send_stream_data(stream_id, data, end_stream=True)

async def main():
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain("./bak/tests/cert.pem", "./bak/tests/key.pem")  # Replace with your cert/key paths

    print("Starting server on ::1:4433")
    server = await serve(
        "::1", 9000, configuration=configuration, create_protocol=EchoServerProtocol
    )

    # Keep the server running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Server shutting down...")
        server.close()

if __name__ == "__main__":
    asyncio.run(main())
