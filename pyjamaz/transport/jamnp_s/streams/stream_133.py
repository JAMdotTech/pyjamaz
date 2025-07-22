import logging

from jamcodec.base import JamBytes

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.transport.jamnp_s.message_types import MsgCE133WorkPackageSubmission, MsgCE133Extrinsic
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamWorkPackageSubmission(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE133_WorkPackageSubmission.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')
        self.received_wp = None


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE133 received reset code: {reset_code}")
        #self.protocol.ce133_submission_failure(reset_code)
        self.received_wp = None


    def initiator_message(self, data: bytes):
        logger.warning(f"Unexpected data in CE133 initiator: {len(data)} bytes")
        self.handle_error("Unexpected data", 1)


    def acceptor_reset(self, reset_code: int):
        logger.debug(f"CE133 received reset code: {reset_code}")
        #self.protocol.ce133_submission_failure(reset_code)
        self.received_wp = None


    def acceptor_message(self, data: bytes):
        if self.received_wp is None:
            logger.debug(f"CE133 acceptor received work package")
            msg = MsgCE133WorkPackageSubmission.from_jam_bytes(JamBytes(data))
            self.received_wp = msg.work_package
            #self.protocol.ce133_received_workpackage_submission(self, msg) #TODO: do we need this event at protocol level?
        else:
            logger.debug(f"CE133 acceptor received extrinsic data")

            extrinsics_data = JamBytes(data)
            extriniscs_list = []

            for item in self.received_wp.items:
                for ext in item.extrinsic:
                    ext_data = extrinsics_data.get_next_bytes(ext.len)
                    if blake2b_256_hash(ext_data) != ext.hash:
                        #TODO: handle at protocol level
                        raise ValueError("Extrinsic hash mismatch")

                    extriniscs_list.append(ext_data)

            self.protocol.ce133_received_extrinsic_submission(self, self.received_wp, extriniscs_list)


    def handle_fin(self):
        super().handle_fin()
        self.received_wp = None
        self.protocol.ce133_submission_success(0)