import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE134WorkPackageSharing, MsgCE134WorkPackageBundle, MsgCE134RefineResponse
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamWorkPackageSharing(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE134_WorkPackageSharing.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.received_mappings = False


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE134 received reset code: {reset_code}")
        self.protocol.ce134_sharing_failure(reset_code)
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        if not self.received_mappings:
            logger.debug(f"CE134 initiator received refine response")
            msg = MsgCE134RefineResponse.from_jam_bytes(JamBytes(data))
            self.protocol.ce134_received_refine_response(self, msg)
            self.received_mappings = True
        else:
            logger.warning(f"Unexpected data in CE134 initiator after mappings: {len(data)} bytes")
            self.handle_error("Unexpected data after mappings", 1)


    def acceptor_reset(self, reset_code: int):
        self.protocol.ce134_sharing_failure(reset_code)
        super().reset(reset_code)


    def acceptor_message(self, data: bytes):
        if not self.received_mappings:
            logger.debug(f"CE134 acceptor received mappings")
            msg = MsgCE134WorkPackageSharing.from_jam_bytes(JamBytes(data))
            self.protocol.ce134_received_workpackage_sharing(self, msg)
            self.received_mappings = True
        else:
            logger.debug(f"CE134 acceptor received bundle")
            msg = MsgCE134WorkPackageBundle.from_jam_bytes(JamBytes(data))
            self.protocol.ce134_received_bundle(self, msg)


    def handle_fin(self):
        super().handle_fin()
        self.protocol.ce134_sharing_success(0)