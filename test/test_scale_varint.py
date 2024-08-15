import unittest

from pyjamaz.types.scale import VarInt29, VarInt64
from scalecodec.base import ScaleBytes
from scalecodec.exceptions import ScaleEncodeException


class TestVarInt29(unittest.TestCase):
    def test_scale_encode(self):
        var_int = VarInt29().new()

        self.assertEqual('0x01', var_int.encode(1).to_hex())
        self.assertEqual('0xc080', var_int.encode(128).to_hex())
        self.assertEqual('0xc0e8', var_int.encode(1000).to_hex())
        self.assertEqual('0xe0e093', var_int.encode(300000).to_hex())
        self.assertEqual('0xe0ffff', var_int.encode(2**21-1).to_hex())
        self.assertEqual('0xffffffff', var_int.encode(2**29 - 1).to_hex())

    def test_encode_overflow(self):
        var_int = VarInt29().new()

        with self.assertRaises(ScaleEncodeException) as context:
            var_int.encode(2**29)

        with self.assertRaises(ScaleEncodeException) as context:
            var_int.encode(-1)

    def test_scale_decode(self):
        var_int = VarInt29().new()

        self.assertEqual(1, var_int.decode(ScaleBytes('0x01')))
        self.assertEqual(128, var_int.decode(ScaleBytes('0xc080')))
        self.assertEqual(1000, var_int.decode(ScaleBytes('0xc3e8')))
        self.assertEqual(300000, var_int.decode(ScaleBytes('0xe4e093')))
        self.assertEqual(2**21-1, var_int.decode(ScaleBytes('0xe0ffff')))
        self.assertEqual(2**29-2, var_int.decode(ScaleBytes('0xffffffff')))


class TestVarInt64(unittest.TestCase):
    def test_scale_encode(self):
        var_int = VarInt64().new()

        self.assertEqual('0x01', var_int.encode(1).to_hex())
        self.assertEqual('0xc0e8', var_int.encode(1000).to_hex())
        self.assertEqual('0xe0e093', var_int.encode(300000).to_hex())
        self.assertEqual('0xe0ffff', var_int.encode(2 ** 21 - 1).to_hex())
        self.assertEqual('0xffffffff1f00000000', var_int.encode(2**29-1).to_hex())
        self.assertEqual('0xffffffffffffffffff', var_int.encode(2**64 - 1).to_hex())

    def test_encode_overflow(self):
        var_int = VarInt64().new()

        with self.assertRaises(ScaleEncodeException) as context:
            var_int.encode(2**64)

        with self.assertRaises(ScaleEncodeException) as context:
            var_int.encode(-1)

    def test_scale_decode(self):
        var_int = VarInt64().new()

        self.assertEqual(1, var_int.decode(ScaleBytes('0x01')))
        self.assertEqual(1000, var_int.decode(ScaleBytes('0xc0e8')))
        # self.assertEqual(300000, var_int.decode(ScaleBytes('0xe4e093')))
        # self.assertEqual(2**21-1, var_int.decode(ScaleBytes('0xffffff')))
        self.assertEqual(2**29-1, var_int.decode(ScaleBytes('0xffffffff1f00000000')))
        self.assertEqual(2**64-1, var_int.decode(ScaleBytes('0xffffffffffffffffff')))


if __name__ == '__main__':
    unittest.main()
