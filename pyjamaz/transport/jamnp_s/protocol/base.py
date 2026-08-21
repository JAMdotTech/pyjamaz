from __future__ import annotations

from typing import TYPE_CHECKING

from pyjamaz.transport.jamnp_s.types import IStreamHandler, JAMStream, StreamDirection

if TYPE_CHECKING:
    from pyjamaz.transport.jamnp_s.connection import JAMConnection
    from pyjamaz.transport.jamnp_s.protocol.context import ProtocolContext
    from pyjamaz.transport.jamnp_s.types import JAMStreamKind


class StreamHandler(IStreamHandler):
    kind: "JAMStreamKind"

    def __init__(self, context: "ProtocolContext") -> None:
        self.context = context

    def init_stream(self, stream: JAMStream) -> None:
        pass

    def on_message(self, stream: JAMStream, data: bytes) -> None:
        if stream.direction == StreamDirection.initiator:
            self.initiator_message(stream, data)
        else:
            self.acceptor_message(stream, data)

    def on_fin(self, stream: JAMStream) -> None:
        if stream.direction == StreamDirection.initiator:
            self.initiator_fin(stream)
        else:
            self.acceptor_fin(stream)

    def on_reset(self, stream: JAMStream, reset_code: int) -> None:
        if stream.direction == StreamDirection.initiator:
            self.initiator_reset(stream, reset_code)
        else:
            self.acceptor_reset(stream, reset_code)

    def on_close(self, stream: JAMStream) -> None:
        pass

    def initiator_message(self, stream: JAMStream, data: bytes) -> None:
        raise NotImplementedError

    def acceptor_message(self, stream: JAMStream, data: bytes) -> None:
        raise NotImplementedError

    def initiator_fin(self, stream: JAMStream) -> None:
        pass

    def acceptor_fin(self, stream: JAMStream) -> None:
        pass

    def initiator_reset(self, stream: JAMStream, reset_code: int) -> None:
        pass

    def acceptor_reset(self, stream: JAMStream, reset_code: int) -> None:
        pass

    def open_outgoing(self, conn: "JAMConnection") -> JAMStream:
        return self.context.stream_manager.open_outgoing(conn, self.kind)
