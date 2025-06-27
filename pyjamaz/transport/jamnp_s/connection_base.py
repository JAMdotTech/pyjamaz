import asyncio
import logging
from aioquic.asyncio import QuicConnectionProtocol, serve

from pyjamaz.transport.jamnp_s.stream import Stream, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class ConnectionBase(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.protocol = None    # Note: should be set in wrap_protocol

        self.stream_up_id = None
        self.streams = {}
        self._keepalive_task = asyncio.create_task(self._keepalive())


    def create_jam_stream(self, StreamCls: Stream):
        stream_id = self._quic.get_next_available_stream_id()
        self.streams[stream_id] = StreamCls(stream_id, connection=self, direction=StreamDirection.initiator)
        return self.streams[stream_id]


    def send(self, stream_id: int, data, end_stream=False):
        self._quic.send_stream_data(
            stream_id,
            data,
            end_stream=end_stream
        )
        self.transmit()


    async def _keepalive(self):
        try:
            while True:
                await asyncio.sleep(4)
                self._quic.send_ping(666)
                self.transmit()
        except asyncio.CancelledError:
            pass