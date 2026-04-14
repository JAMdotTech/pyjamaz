from __future__ import annotations

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.types import JAMStream, JAMStreamKind


class CE129Handler(StreamHandler):
    kind = JAMStreamKind.CE129_StateRequest

    def initiator_message(self, stream: JAMStream, data: bytes) -> None:
        pass

    def acceptor_message(self, stream: JAMStream, data: bytes) -> None:
        pass
