from __future__ import annotations

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind


class CE129Handler(StreamHandler):
    kind = StreamKind.CE129_StateRequest

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        pass

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        pass
