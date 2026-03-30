from __future__ import annotations

from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind


class CE129Handler(ContextualStreamHandler):
    kind = StreamKind.CE129_StateRequest

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        pass

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        pass
