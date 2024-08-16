import unittest

from pyjamaz.types.scale import VarInt64
from scalecodec.base import ScaleBytes
from scalecodec.exceptions import ScaleEncodeException


class TestVarInt64(unittest.TestCase):
    def test_scale_encode(self):
        var_int = VarInt64().new()

        # self.assertEqual('0x01', var_int.encode(1).to_hex())
        # self.assertEqual('0x7f', var_int.encode(127).to_hex())
        self.assertEqual('0x8080', var_int.encode(128).to_hex())
        self.assertEqual('0xc00040', var_int.encode(2**14).to_hex())
        self.assertEqual('0xe0000020', var_int.encode(2**21).to_hex())
        self.assertEqual('0xf000000010', var_int.encode(2**28).to_hex())
        self.assertEqual('0xf80000000008', var_int.encode(2**35).to_hex())
        self.assertEqual('0xfc000000000004', var_int.encode(2**42).to_hex())
        self.assertEqual('0xfe00000000000002', var_int.encode(2**49).to_hex())
        self.assertEqual('0xff0000000000000001', var_int.encode(2**56).to_hex())
        self.assertEqual('0x83e8', var_int.encode(1000).to_hex())
        self.assertEqual('0xc4e093', var_int.encode(300000).to_hex())
        self.assertEqual('0xdfffff', var_int.encode(2 ** 21 - 1).to_hex())
        self.assertEqual('0xf0ffffff1f', var_int.encode(2**29-1).to_hex())
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
        self.assertEqual(128, var_int.decode(ScaleBytes('0x8080')))
        self.assertEqual(1000, var_int.decode(ScaleBytes('0x83e8')))
        self.assertEqual(300000, var_int.decode(ScaleBytes('0xc4e093')))
        self.assertEqual(2**14, var_int.decode(ScaleBytes('0xc00040')))
        self.assertEqual(2**21, var_int.decode(ScaleBytes('0xe0000020')))
        self.assertEqual(2**28, var_int.decode(ScaleBytes('0xf000000010')))
        self.assertEqual(2**35, var_int.decode(ScaleBytes('0xf80000000008')))
        self.assertEqual(2**42, var_int.decode(ScaleBytes('0xfc000000000004')))
        self.assertEqual(2**49, var_int.decode(ScaleBytes('0xfe00000000000002')))
        self.assertEqual(2**56, var_int.decode(ScaleBytes('0xff0000000000000001')))
        # self.assertEqual(2**21-1, var_int.decode(ScaleBytes('0xdfffff')))
        # self.assertEqual(2**29-1, var_int.decode(ScaleBytes('0xf0ffffff1f')))
        self.assertEqual(2**64-1, var_int.decode(ScaleBytes('0xffffffffffffffffff')))


if __name__ == '__main__':
    unittest.main()
