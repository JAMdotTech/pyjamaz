import asyncio
import logging
import struct
from typing import List

from aioquic.quic.events import QuicEvent, StreamDataReceived, ConnectionTerminated, HandshakeCompleted

from pyjamaz.transport.jamnp_s.stream_messages import StreamBlockAnnounce
from pyjamaz.transport.jamnp_s.stream_base import StreamBase, InvalidStreamType, StreamType


logger = logging.getLogger("pyjamaz.transport.jamnp_s")


# --- wire-format helpers -------------------------------------------------

STREAM_UP0 = b"\x00"

def _u32le(n: int) -> bytes:
    return struct.pack("<I", n)

def _size_prefixed(payload: bytes) -> bytes:     # spec: len (u32) + payload
    return _u32le(len(payload)) + payload

# message layouts (hash = 32 bytes, slot = u32)
def encode_final(hash32: bytes, slot: int) -> bytes:
    return hash32 + _u32le(slot)

def encode_leaf(hash32: bytes, slot: int) -> bytes:
    return hash32 + _u32le(slot)

def encode_handshake(final: bytes, leaves: List[bytes]) -> bytes:
    body = final + _size_prefixed(b"".join(leaves))
    return _size_prefixed(body)

def encode_announcement(header: bytes, final: bytes) -> bytes:
    body = header + final
    return _size_prefixed(body)




class ClientProtocol(StreamBase):

    async def send_blocks_request(self, direction, max_blocks, block_bytes):
        #TODO: moet over een nieuwe stream/connectie?? misbruiken voor nu de up0 stream
        data = (
            # int(direction).to_bytes(length=1, byteorder='little') +
            # int(max_blocks).to_bytes(length=1, byteorder='little') +
            block_bytes
        )
        self._quic.send_stream_data(
            self.stream_up_0,
            (int(StreamType.CE128_BlockRequest.value).to_bytes(length=1, byteorder='little') +
             len(data).to_bytes(length=4, byteorder='little') +
             data)
        )
        self.transmit()
        logger.debug(f"ClientProtocol Block Requests sent to stream {self.stream_up_0} ({len(data)})")


    def quic_event_received(self, event: QuicEvent) -> None:
        logger.debug(f'ClientProtocol received data {event}')

        if isinstance(event, HandshakeCompleted):
            #TODO: meerdere typen streams!!!!! of eenmalig?? uitzoeken!!!!!!!
            #TODO: UP0 alleen wanneer:
            #   Both nodes are validators, and are neighbours in the grid structure.
            #   At least one of the nodes is not a validator.

            # open bidirectional stream for UP 0 (initiator side)   :contentReference[oaicite:1]{index=1}
            # stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
            # quic_stream = self._quic._get_or_create_stream(stream_id=stream_id, is_unidirectional=False)
            # self._quic.send_stream_data(stream_id, b"", end_stream=False)  # TODO: nog nodig? (ensure frame exists)
            # asyncio.create_task(self.open_stream_up_0(quic_stream))

            self.stream_up_0 = self._quic.get_next_available_stream_id()

            final = encode_final(bytes.fromhex(self.wrapper.first_block_hash), self.wrapper.first_slot)
            leaves_enc = [encode_leaf(h, s) for h, s in []]
            #await self.stream.write(STREAM_UP0 + encode_handshake(final, leaves_enc))
            self._quic.send_stream_data(
                self.stream_up_0,
                encode_handshake(final, leaves_enc),
            )

        elif isinstance(event, StreamDataReceived):

            #TODO: for now we only support 1 stream (UP-0)
            #stream_id = event.stream_id
            #stream = self._get_or_create_stream(stream_id)

            byte_data = bytes(event.data)
            bytes_left = byte_data

            # Note: Parse bytes until stream data is empty: https://github.com/microsoft/msquic/discussions/2037
            while len(bytes_left) > 0:

                #TODO: do this per channel
                if not self._msg_buffer:
                    # Note: first message always contains expected message type & length
                    self._msg_type = int.from_bytes(byte_data[0:1], byteorder='little')
                    self._msg_offset = 5
                    self._msg_len = int.from_bytes(byte_data[1:5], byteorder='little') + self._msg_offset
                    logger.debug(f'ClientProtocol new message {self._msg_type} (received {len(bytes_left)-5} of {self._msg_len} bytes)')

                nr_bytes_remaining = self._msg_len-len(self._msg_buffer)
                self._msg_buffer += bytes_left[:nr_bytes_remaining]
                bytes_left = bytes_left[nr_bytes_remaining:]

                # If we assembled a new message, parse it
                if 0 < self._msg_len == len(self._msg_buffer):

                    try:
                        match self._msg_type:

                            case StreamType.UP0_BlockAnnouncement.value:
                                logger.debug(f'ClientProtocol RECEIVED_BLOCK: {self._msg_len}')
                                #await self.wrapper.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.RECEIVED_BLOCK, data=self._msg_buffer[self._msg_offset:self._msg_len]))
                                # TODO: asyncio.create_task(.....)

                            case StreamType.CE128_BlockRequest.value:
                                logger.debug(f'ClientProtocol RECEIVED REQUESTED BLOCKS: {self._msg_len}')
                                #await self.wrapper.pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.REQUESTED_BLOCKS, data=self._msg_buffer[self._msg_offset:self._msg_len]))
                                #TODO: asyncio.create_task(.....)

                            case _:
                                raise InvalidStreamType(f"Invalid JAMNPS message: {self._msg_type}")
                    finally:
                        self._reset_msg()

    # TODO: handle gracefully
    #     elif isinstance(event, ConnectionTerminated):
    #         # Handle connection termination

    async def open_stream_up_0(self, quic_stream):
        logger.debug(f'ClientProtocol Block announcement stream opened')
        up = StreamBlockAnnounce(quic_stream)

        # send our handshake in parallel with reading theirs             :contentReference[oaicite:2]{index=2}
        await up.send_handshake(self.wrapper.first_block_hash, self.wrapper.first_slot, [])

        async for msg in up.iter_messages():
            # first message we get is their Handshake, subsequent ones can
            # be either further handshakes (legal) or announcements
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!got remote handshake or announcement", len(msg), "bytes")
