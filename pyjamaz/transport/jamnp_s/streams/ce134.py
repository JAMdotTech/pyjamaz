from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from jamcodec.base import JamBytes

from pyjamaz.models.common import WorkPackage
from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import (
    MsgCE134RefineResponse,
    MsgCE134WorkPackageBundle,
    MsgCE134WorkPackageSharing,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE134StreamState:
    received_mappings: bool = False
    sharing_msg: Optional[MsgCE134WorkPackageSharing] = None


class CE134Handler(ContextualStreamHandler):
    kind = StreamKind.CE134_WorkPackageSharing

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE134StreamState()

    def initiate_workpackage_sharing(
        self,
        conn,
        sharing: MsgCE134WorkPackageSharing,
        bundle: MsgCE134WorkPackageBundle,
    ) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"Initiate sharing workpage on stream id: {stream.stream_id} to {conn.host}:{conn.port}")
        conn.send(
            stream.stream_id,
            stream.create_message(sharing.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=False,
        )
        conn.send(
            stream.stream_id,
            stream.create_message(bundle.to_jam_bytes().to_bytes()),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        state = self._streams[stream.stream_key]
        if state.received_mappings:
            logger.warning(f"Unexpected data in CE134 initiator after mappings: {len(data)} bytes")
            raise ValueError("Unexpected data in CE134 initiator after mappings")

        logger.debug("CE134 initiator received refine response")
        msg = MsgCE134RefineResponse.from_jam_bytes(JamBytes(data))
        state.received_mappings = True
        self._handle_refine_response(stream, msg)

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        state = self._streams[stream.stream_key]
        if not state.received_mappings:
            logger.debug("CE134 acceptor received mappings")
            msg = MsgCE134WorkPackageSharing.from_jam_bytes(JamBytes(data))
            state.received_mappings = True
            state.sharing_msg = msg
            logger.info(f"ce134_received_workpackage_sharing for core {msg.core_index}")
            return

        logger.debug("CE134 acceptor received bundle")
        msg = MsgCE134WorkPackageBundle.from_jam_bytes(JamBytes(data))
        self._handle_bundle(stream, msg)

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("Success with FIN")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)

    def _handle_bundle(self, stream: ManagedStream, msg: MsgCE134WorkPackageBundle) -> None:
        logger.info("ce134_received_bundle")
        work_report = self.context.app.process_work_package(msg.work_package)

        report_hash = work_report.hash()
        signature = self.context.app.config.keys.ed25519.sign(report_hash)
        response = MsgCE134RefineResponse(report_hash=report_hash, signature=signature)
        stream.conn.send(
            stream.stream_id,
            stream.create_message(response.to_jam_bytes().to_bytes()),
            end_stream=True,
        )

    def _handle_refine_response(self, stream: ManagedStream, msg: MsgCE134RefineResponse) -> None:
        logger.info("ce134_received_refine_response")
        work_report = None
        if work_report is not None:
            self.context.app.guarantee_work_report(work_report, self.context.app.current_timeslot())
        stream.conn.send(stream.stream_id, b"", end_stream=True)
