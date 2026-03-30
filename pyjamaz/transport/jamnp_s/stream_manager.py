from __future__ import annotations

import logging
from typing import Dict, Tuple, TYPE_CHECKING

from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamDirection, StreamHandler, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")

if TYPE_CHECKING:
    from pyjamaz.transport.jamnp_s.connection import JAMConnection


class StreamManager:
    def __init__(self, max_message_size: int) -> None:
        self.max_message_size = max_message_size
        self.handlers: Dict[StreamKind, StreamHandler] = {}
        self._streams: Dict[Tuple[int, int], ManagedStream] = {}
        self._pending_kind_buffers: Dict[Tuple[int, int], bytearray] = {}

    def register_handler(self, handler: StreamHandler) -> None:
        self.handlers[handler.kind] = handler

    def open_outgoing(self, connection: "JAMConnection", kind: StreamKind) -> ManagedStream:
        stream_id = connection._quic.get_next_available_stream_id()
        stream = ManagedStream(
            stream_id=stream_id,
            stream_kind=kind,
            conn=connection,
            direction=StreamDirection.initiator,
        )
        self._register_stream(stream)
        return stream

    def receive_stream_data(
        self,
        connection: "JAMConnection",
        stream_id: int,
        data: bytes,
        end_stream: bool = False,
    ) -> None:
        stream = self._streams.get(self._key(connection, stream_id))

        if stream is None:
            stream = self._resolve_incoming_stream(connection, stream_id, data, end_stream)
            if stream is None:
                return

            pending = self._pending_kind_buffers.pop(self._key(connection, stream_id), bytearray())
            data = bytes(pending[1:])

        self._process_stream_bytes(stream, data, end_stream)

    def receive_reset(self, connection: "JAMConnection", stream_id: int, reset_code: int) -> None:
        key = self._key(connection, stream_id)
        stream = self._streams.get(key)
        if stream is None:
            self._pending_kind_buffers.pop(key, None)
            logger.debug(f"Connection {connection.jam_connection_ulid} QUIC stream {stream_id} already closed")
            return

        logger.info(
            f"Connection {connection.jam_connection_ulid} QUIC StreamReset {stream.stream_kind} ({stream_id}) direction={stream.direction} code {reset_code}"
        )

        try:
            if stream.handler is not None:
                stream.handler.on_reset(stream, reset_code)
        finally:
            self._cleanup_stream(stream)

    def send_reset(self, stream: ManagedStream, reset_code: int) -> None:
        stream.conn.reset_stream(stream.stream_id, reset_code)
        self._cleanup_stream(stream)

    def close_stream(self, stream: ManagedStream, reason: int = 0, clean_close: bool = True) -> None:
        stream.conn.close_stream(stream.stream_id, clean_close=clean_close, reason=reason)
        self._cleanup_stream(stream)

    def cleanup_connection(self, connection: "JAMConnection") -> None:
        conn_key = id(connection)

        for key, stream in list(self._streams.items()):
            if key[0] != conn_key:
                continue
            self._cleanup_stream(stream)

        for key in [key for key in self._pending_kind_buffers if key[0] == conn_key]:
            self._pending_kind_buffers.pop(key, None)

        connection.streams.clear()
        connection.stream_up = None

    def _resolve_incoming_stream(
        self,
        connection: "JAMConnection",
        stream_id: int,
        data: bytes,
        end_stream: bool,
    ) -> ManagedStream | None:
        key = self._key(connection, stream_id)
        pending = self._pending_kind_buffers.setdefault(key, bytearray())
        if data:
            pending.extend(data)

        if len(pending) < 1:
            if end_stream:
                self._reset_unknown_stream(
                    connection, stream_id, ManagedStream.ERROR_INVALID_MESSAGE, "Stream ended before stream kind was received"
                )
            return None

        try:
            kind = StreamKind(pending[0])
        except ValueError:
            self._reset_unknown_stream(
                connection,
                stream_id,
                ManagedStream.ERROR_INVALID_MESSAGE,
                f"QUIC stream {stream_id} is not mapped (type {pending[0]})",
            )
            return None

        stream = ManagedStream(
            stream_id=stream_id,
            stream_kind=kind,
            conn=connection,
            direction=StreamDirection.acceptor,
        )
        self._register_stream(stream)
        return stream

    def _process_stream_bytes(self, stream: ManagedStream, data: bytes, end_stream: bool) -> None:
        if data:
            stream.recv_buffer.extend(data)

        try:
            while True:
                if stream.expected_len is None:
                    if len(stream.recv_buffer) < 4:
                        break

                    stream.expected_len = int.from_bytes(stream.recv_buffer[:4], byteorder="little")
                    del stream.recv_buffer[:4]

                    logger.debug(
                        f"Received new message for stream {stream.stream_id} with a msg length: {stream.expected_len} ({len(stream.recv_buffer)} buffered)"
                    )

                    if stream.expected_len <= 0:
                        raise ValueError(f"Message size <= 0 for stream {stream.stream_id} {stream.expected_len}")
                    if stream.expected_len > self.max_message_size:
                        raise MemoryError(f"Message too large for stream {stream.stream_id}")

                if len(stream.recv_buffer) < stream.expected_len:
                    break

                message = bytes(stream.recv_buffer[:stream.expected_len])
                del stream.recv_buffer[:stream.expected_len]
                stream.expected_len = None

                logger.debug(f"Message complete for stream {stream.stream_id}")
                if stream.handler is not None:
                    stream.handler.on_message(stream, message)

                if stream.closed:
                    return

            if not end_stream:
                return

            if stream.expected_len is not None or len(stream.recv_buffer) > 0:
                raise ValueError(f"Incomplete framed message on FIN for stream {stream.stream_id}")

            logger.debug(f"Received FIN on stream {stream.stream_id}")
            if stream.handler is not None:
                stream.handler.on_fin(stream)
        except Exception as exc:
            stream.handle_error(exc)
            return

        self._cleanup_stream(stream)

    def _register_stream(self, stream: ManagedStream) -> None:
        handler = self.handlers.get(stream.stream_kind)
        if handler is None:
            raise ValueError(f"Unsupported stream kind: {stream.stream_kind}")

        stream.handler = handler
        self._streams[self._key(stream.conn, stream.stream_id)] = stream
        stream.conn.streams[stream.stream_id] = stream
        if stream.stream_kind == StreamKind.UP0_BlockAnnouncement:
            stream.conn.stream_up = stream

        handler.init_stream(stream)

    def _cleanup_stream(self, stream: ManagedStream) -> None:
        if stream.closed:
            return

        stream.closed = True

        if stream.handler is not None:
            on_close = getattr(stream.handler, "on_close", None)
            if callable(on_close):
                on_close(stream)

        self._streams.pop(self._key(stream.conn, stream.stream_id), None)
        stream.conn.streams.pop(stream.stream_id, None)

        if stream.conn.stream_up is stream:
            stream.conn.stream_up = None

    def _reset_unknown_stream(
        self,
        connection: "JAMConnection",
        stream_id: int,
        error_code: int,
        reason: str,
    ) -> None:
        logger.error(reason)
        connection.reset_stream(stream_id, error_code)
        self._pending_kind_buffers.pop(self._key(connection, stream_id), None)

    @staticmethod
    def _key(connection: "JAMConnection", stream_id: int) -> Tuple[int, int]:
        return id(connection), stream_id
