import logging
from enum import Enum

from aioquic.asyncio import QuicConnectionProtocol, serve


logger = logging.getLogger("pyjamaz.transport.jamnp_s")



class ConnectionBase(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.protocol = None    # Note: should be set in wrap_protocol

        self.stream_up_id = None
        self.streams = {}
