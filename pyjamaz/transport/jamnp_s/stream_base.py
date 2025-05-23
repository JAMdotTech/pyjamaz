import logging
from enum import Enum

from aioquic.asyncio import QuicConnectionProtocol, serve


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


class InvalidStreamType(Exception):
    pass


class StreamType(Enum):
    UP0_OPEN: int = 66
    UP0_BlockAnnouncement: int = 0
    CE128_BlockRequest: int = 128


#TODO: StreamBase,Client & Server -> Connection* maken
class StreamBase(QuicConnectionProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrapper = None    # Note: should be set in wrap_protocol
        self.stream_up_0 = None
        #TODO: this buffer should be made per stream_id (for now, we always assume stream_up_0)
        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1
        self._msg_offset = -1

    def _reset_msg(self):
        self._msg_buffer = b""
        self._msg_len = -1
        self._msg_type = -1
        self._msg_offset = -1

    # #TODO: deprecated!!!!!
    # def build_handshake_message(self):
    #     #TODO: implement handshake response according to JAMSNP
    #     """Both sides should begin by sending a handshake message containing all known leaves (descendants of the latest finalized block with no known children)."""
    #     logger.debug(f"Building handshake message for UP-0 stream")
    #
    #     """
    #     async def send_handshake(
    #         self, finalized_hash: bytes, finalized_slot: int,
    #         leaves: List[Tuple[bytes, int]],
    #     ):
    #         final = encode_final(finalized_hash, finalized_slot)
    #         leaves_enc = [encode_leaf(h, s) for h, s in leaves]
    #         await self.stream.write(UP0_KIND + encode_handshake(final, leaves_enc))
    #     """
    #
    #     return (
    #         int(JAMNPSMessage.UP0_OPEN.value).to_bytes(
    #             length=1,
    #             byteorder='little'
    #         )
    #     )
