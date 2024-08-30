import unittest
from dataclasses import dataclass, field
from typing import List

from pyjamaz.serialization import Serializable, JamBytes, VarInt64, SerializationException
from pyjamaz.types.safrole import SafroleErrorCode, SafroleOutput
from pyjamaz.types.block import OutputMarks
from pyjamaz.types.common import ValidatorData


@dataclass
class Program(Serializable):
    jump_table_entry_count: int = field(metadata={'length': 'varint'})
    jump_table_entry_size: int = field(metadata={'length': 1})
    code_length: int = field(metadata={'length': 'varint'})
    jump_table: List[int] = field(metadata={'size': jump_table_entry_count, 'length': jump_table_entry_size})
    code: bytes = field(metadata={'length': code_length})
    checksum: int = field(metadata={'length': 1})


class TestProgramSerialization(unittest.TestCase):

    def test_from_bytes(self):
        program = Program.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        self.assertEqual(program.jump_table_entry_count, 0)
        self.assertEqual(bytes([8, 135, 9]), program.code)

    def test_dynamic_length_size(self):
        program = Program.from_json({
            'checksum': 249,
            'code': '0x088709',
            'code_length': 3,
            'jump_table': [1, 2, 3],
            'jump_table_entry_count': 3,
            'jump_table_entry_size': 2
        })
        scale_bytes = program.to_jam_bytes()
        self.assertEqual('0x030203010002000300088709f9', scale_bytes.to_hex())
        self.assertEqual(program, Program.from_jam_bytes(scale_bytes))


class TestSerialization(unittest.TestCase):

    def setUp(self):
        data = {
            'bandersnatch': '0x5e465beb01dbafe160ce8216047f2155dd0569f058afd52dcea601025a8d161d',
            'ed25519': '0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29',
            'bls': '0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
            'metadata': '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        }

        self.test_obj = ValidatorData.from_json(data)

    def test_dataclass_serialization(self):
        output = SafroleOutput(ok=OutputMarks(epoch_mark=None, tickets_mark=None))
        value = output.to_json()
        self.assertEqual({'ok': {'epoch_mark': None, 'tickets_mark': None}}, value)

        output = SafroleOutput(err=SafroleErrorCode.duplicate_ticket)
        value = output.to_json()

        self.assertEqual({'err': 'duplicate_ticket'}, value)

        data = output.to_jam_bytes()
        self.assertEqual('0x000106', data.to_hex())

    def test_deserialize(self):

        data = {
            'bandersnatch': '0x5e465beb01dbafe160ce8216047f2155dd0569f058afd52dcea601025a8d161d',
            'ed25519': '0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29',
            'bls': '0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
            'metadata': '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        }

        validator_obj = ValidatorData.from_json(data)

        self.assertEqual(self.test_obj, validator_obj)
        self.assertEqual(data, validator_obj.to_json())

    def test_from_to_scale_bytes(self):

        scale_data = self.test_obj.to_jam_bytes()

        validator_obj = ValidatorData.from_jam_bytes(scale_data)

        self.assertEqual(self.test_obj, validator_obj)


class TestVarInt64(unittest.TestCase):
    def test_scale_encode(self):

        # self.assertEqual('0x01', VarInt64.to_scale_bytes(1).to_hex())
        # self.assertEqual('0x7f', VarInt64.to_scale_bytes(127).to_hex())
        self.assertEqual('0x8080', VarInt64.to_scale_bytes(128).to_hex())
        self.assertEqual('0xc00040', VarInt64.to_scale_bytes(2**14).to_hex())
        self.assertEqual('0xe0000020', VarInt64.to_scale_bytes(2**21).to_hex())
        self.assertEqual('0xf000000010', VarInt64.to_scale_bytes(2**28).to_hex())
        self.assertEqual('0xf80000000008', VarInt64.to_scale_bytes(2**35).to_hex())
        self.assertEqual('0xfc000000000004', VarInt64.to_scale_bytes(2**42).to_hex())
        self.assertEqual('0xfe00000000000002', VarInt64.to_scale_bytes(2**49).to_hex())
        self.assertEqual('0xff0000000000000001', VarInt64.to_scale_bytes(2**56).to_hex())
        self.assertEqual('0x83e8', VarInt64.to_scale_bytes(1000).to_hex())
        self.assertEqual('0xc4e093', VarInt64.to_scale_bytes(300000).to_hex())
        self.assertEqual('0xdfffff', VarInt64.to_scale_bytes(2 ** 21 - 1).to_hex())
        self.assertEqual('0xf0ffffff1f', VarInt64.to_scale_bytes(2**29-1).to_hex())
        self.assertEqual('0xffffffffffffffffff', VarInt64.to_scale_bytes(2**64 - 1).to_hex())

    def test_encode_overflow(self):
        with self.assertRaises(SerializationException) as context:
            VarInt64.to_scale_bytes(2**64)

        with self.assertRaises(SerializationException) as context:
            VarInt64.to_scale_bytes(-1)

    def test_scale_decode(self):

        self.assertEqual(1, VarInt64.from_scale_bytes(JamBytes('0x01')))
        self.assertEqual(128, VarInt64.from_scale_bytes(JamBytes('0x8080')))
        self.assertEqual(1000, VarInt64.from_scale_bytes(JamBytes('0x83e8')))
        self.assertEqual(300000, VarInt64.from_scale_bytes(JamBytes('0xc4e093')))
        self.assertEqual(2 ** 14, VarInt64.from_scale_bytes(JamBytes('0xc00040')))
        self.assertEqual(2 ** 21, VarInt64.from_scale_bytes(JamBytes('0xe0000020')))
        self.assertEqual(2 ** 28, VarInt64.from_scale_bytes(JamBytes('0xf000000010')))
        self.assertEqual(2 ** 35, VarInt64.from_scale_bytes(JamBytes('0xf80000000008')))
        self.assertEqual(2 ** 42, VarInt64.from_scale_bytes(JamBytes('0xfc000000000004')))
        self.assertEqual(2 ** 49, VarInt64.from_scale_bytes(JamBytes('0xfe00000000000002')))
        self.assertEqual(2 ** 56, VarInt64.from_scale_bytes(JamBytes('0xff0000000000000001')))
        # self.assertEqual(2**21-1, VarInt64.from_scale_bytes(ScaleBytes('0xdfffff')))
        # self.assertEqual(2**29-1, VarInt64.from_scale_bytes(ScaleBytes('0xf0ffffff1f')))
        self.assertEqual(2 ** 64 - 1, VarInt64.from_scale_bytes(JamBytes('0xffffffffffffffffff')))


if __name__ == '__main__':
    unittest.main()
