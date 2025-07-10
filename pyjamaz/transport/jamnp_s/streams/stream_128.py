import logging

from jamcodec.base import JamBytes

from pyjamaz.transport.jamnp_s.message_types import MsgCE128BlockRequest, MsgCE128BlockRequestResponse
from pyjamaz.transport.jamnp_s.stream_base import Stream, StreamType, StreamDirection

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class StreamBlockRequest(Stream):

    def __init__(self, stream_id: int, connection, direction: StreamDirection):
        super().__init__(stream_id, connection, direction)
        self.stream_type = StreamType.CE128_BlockRequest.value
        self.stream_type_byte = self.stream_type.to_bytes(length=1, byteorder='little')


    def initiator_reset(self, reset_code: int):
        logger.debug(f"CE128 received reset code: {reset_code}")
        self.protocol.ce128_abort_block_request()
        super().initiator_reset(reset_code)


    def initiator_message(self, data: bytes):
        if len(data) == 0: #int.from_bytes(b'\x00\x00\x00\x00')
            #TODO: send FIN? Let protocol know were finished?
            print(f'!!!!!!!!!ConnectionInitiator StreamBlockRequest.initiator_message received empty data')
            self.initiator_reset(reset_code=0)
            return

        logger.debug(f"CE128 initiated stream {self.stream_id} received block request response: {len(data)} bytes")
        req = MsgCE128BlockRequestResponse.from_jam_bytes(JamBytes(data))
        self.protocol.ce128_received_block_request(self, req)


    def acceptor_message(self, data: bytes):
        logger.debug(f"CE128 acceptor stream {self.stream_id} received block request")
        self.protocol.ce128_send_block_request(self, MsgCE128BlockRequest.from_jam_bytes(JamBytes(data)))
