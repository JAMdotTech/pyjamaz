from __future__ import annotations

import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce143 import MsgCE143HashRequest, MsgCE143Preimage
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class CE143Handler(StreamHandler):
    kind = StreamKind.CE143_PreimageRequest

    def initiate_request(self, conn, msg: MsgCE143HashRequest) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"CE143 initiating request on stream id: {stream.stream_id}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE143 initiator received preimage")
        msg = MsgCE143Preimage.from_jam_bytes(JamBytes(data))
        logger.info(f"CE143 received preimage of length {len(msg.bytes_)}")
        stream.conn.send(stream.stream_id, b"", end_stream=True)

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug("CE143 acceptor received preimage request")
        msg = MsgCE143HashRequest.from_jam_bytes(JamBytes(data))
        logger.info(f"CE143 received request for hash {msg.hash.hex()}")
        preimage = MsgCE143Preimage(bytes_=b"")
        stream.conn.send(
            stream.stream_id,
            stream.create_message(preimage.to_jam_bytes().to_bytes()),
            end_stream=True,
        )

    def initiator_fin(self, stream: ManagedStream) -> None:
        self._request_success(0)

    def acceptor_fin(self, stream: ManagedStream) -> None:
        self._request_success(0)

    def initiator_reset(self, stream: ManagedStream, reset_code: int) -> None:
        self._request_failure(reset_code)

    def acceptor_reset(self, stream: ManagedStream, reset_code: int) -> None:
        self._request_failure(reset_code)

    @staticmethod
    def _request_success(reset_code: int) -> None:
        logger.info(f"CE143 request successful with code {reset_code}")

    @staticmethod
    def _request_failure(reset_code: int) -> None:
        logger.debug(f"CE143 received reset code: {reset_code}")
        logger.error(f"CE143 request failed with code {reset_code}")
