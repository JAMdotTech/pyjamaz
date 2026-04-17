import unittest

from pyjamaz.transport.framing import JAMNPSFrameParser, InvalidJAMNPSMessage


class TestJAMNPSFrameParser(unittest.TestCase):
    UP0_OPEN = 66
    BLOCK_ANNOUNCEMENT = 0
    BLOCK_REQUEST = 128

    @staticmethod
    def frame(msg_type: int, payload: bytes = b"") -> bytes:
        return bytes([msg_type]) + len(payload).to_bytes(4, byteorder="little") + payload

    def test_handles_fragmented_header_and_payload(self):
        parser = JAMNPSFrameParser(max_payload_size=64)
        payload = b"fragmented-block"
        frame = self.frame(self.BLOCK_ANNOUNCEMENT, payload)

        self.assertEqual([], parser.feed_data(frame[:2]))
        self.assertEqual([], parser.feed_data(frame[2:7]))
        self.assertEqual(
            [(self.BLOCK_ANNOUNCEMENT, payload)],
            parser.feed_data(frame[7:]),
        )
        self.assertEqual(0, parser.pending_bytes)

    def test_handles_multiple_frames_in_one_chunk(self):
        parser = JAMNPSFrameParser(max_payload_size=64)
        first = self.frame(self.UP0_OPEN)
        second = self.frame(self.BLOCK_REQUEST, b"blocks")

        self.assertEqual(
            [
                (self.UP0_OPEN, b""),
                (self.BLOCK_REQUEST, b"blocks"),
            ],
            parser.feed_data(first + second),
        )
        self.assertEqual(0, parser.pending_bytes)

    def test_rejects_oversized_frames(self):
        parser = JAMNPSFrameParser(max_payload_size=4)

        with self.assertRaises(InvalidJAMNPSMessage):
            parser.feed_data(bytes([self.BLOCK_REQUEST]) + (5).to_bytes(4, byteorder="little"))


if __name__ == "__main__":
    unittest.main()
