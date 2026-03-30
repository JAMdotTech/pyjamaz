from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from jamcodec.base import JamBytes

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import WorkPackage
from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import MsgCE133Extrinsic, MsgCE133WorkPackageSubmission
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE133StreamState:
    work_package: Optional[WorkPackage] = None


class CE133Handler(ContextualStreamHandler):
    kind = StreamKind.CE133_WorkPackageSubmission

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE133StreamState()

    def initiate_workpackage_submission(
        self,
        conn,
        wp: MsgCE133WorkPackageSubmission,
        extrinsic: MsgCE133Extrinsic,
    ) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"Initiating workpackage submission on stream id: {stream.stream_id}")
        conn.send(
            stream.stream_id,
            stream.create_message(wp.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=False,
        )
        conn.send(
            stream.stream_id,
            stream.create_message(extrinsic.to_jam_bytes().to_bytes()),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE133 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE133 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        state = self._streams[stream.stream_key]

        if state.work_package is None:
            logger.debug("CE133 acceptor received work package")
            msg = MsgCE133WorkPackageSubmission.from_jam_bytes(JamBytes(data))
            state.work_package = msg.work_package
            return

        logger.debug("CE133 acceptor received extrinsic data")
        extrinsics_list: List[bytes] = []
        extrinsics_data = JamBytes(data)

        for item in state.work_package.items:
            for ext in item.extrinsic:
                ext_data = extrinsics_data.get_next_bytes(ext.len)
                if blake2b_256_hash(ext_data) != ext.hash:
                    raise ValueError("Extrinsic hash mismatch")
                extrinsics_list.append(ext_data)

        stream.conn.send(stream.stream_id, b"", end_stream=True)
        self.context.app.add_work_package(state.work_package, extrinsics_list)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.debug("CE133 submission successful with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.debug("CE133 submission successful with FIN")

    def initiator_reset(self, stream: ManagedStream, reset_code: int) -> None:
        logger.debug(f"CE133 received reset code: {reset_code}")

    def acceptor_reset(self, stream: ManagedStream, reset_code: int) -> None:
        logger.debug(f"CE133 received reset code: {reset_code}")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)
