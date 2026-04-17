MESSAGE_HEADER_SIZE = 5


class InvalidJAMNPSMessage(Exception):
    pass


def encode_frame(msg_type: int, payload: bytes) -> bytes:
    return (
        int(msg_type).to_bytes(length=1, byteorder="little") +
        len(payload).to_bytes(length=MESSAGE_HEADER_SIZE - 1, byteorder="little") +
        payload
    )


class JAMNPSFrameParser:
    def __init__(self, max_payload_size: int):
        self.max_payload_size = max_payload_size
        self._buffer = bytearray()

    @property
    def pending_bytes(self) -> int:
        return len(self._buffer)

    def feed_data(self, data: bytes) -> list[tuple[int, bytes]]:
        self._buffer.extend(data)
        frames: list[tuple[int, bytes]] = []

        while True:
            if len(self._buffer) < MESSAGE_HEADER_SIZE:
                break

            msg_type = self._buffer[0]
            payload_len = int.from_bytes(self._buffer[1:MESSAGE_HEADER_SIZE], byteorder="little")
            if payload_len > self.max_payload_size:
                raise InvalidJAMNPSMessage(
                    f"Frame payload {payload_len} exceeds max size {self.max_payload_size}"
                )

            frame_len = MESSAGE_HEADER_SIZE + payload_len
            if len(self._buffer) < frame_len:
                break

            payload = bytes(self._buffer[MESSAGE_HEADER_SIZE:frame_len])
            del self._buffer[:frame_len]
            frames.append((msg_type, payload))

        return frames
