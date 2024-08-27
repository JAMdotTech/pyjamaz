import unittest
from dataclasses import dataclass, field
from typing import List

from pyjamaz.serialization import Serializable, ScaleBytes
from pyjamaz.types.safrole import CustomErrorCode, ValidatorData, OutputMarks, Output


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
        program = Program.from_scale_bytes(ScaleBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
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
        scale_bytes = program.to_scale_bytes()
        self.assertEqual('0x030203010002000300088709f9', scale_bytes.to_hex())
        self.assertEqual(program, Program.from_scale_bytes(scale_bytes))


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
        output = Output(ok=OutputMarks(epoch_mark=None, tickets_mark=None))
        value = output.to_json()
        self.assertEqual({'ok': {'epoch_mark': None, 'tickets_mark': None}}, value)

        output = Output(err=CustomErrorCode.duplicate_ticket)
        value = output.to_json()

        self.assertEqual({'err': 'duplicate_ticket'}, value)

        data = output.to_scale_bytes()
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

        scale_data = self.test_obj.to_scale_bytes()

        validator_obj = ValidatorData.from_scale_bytes(scale_data)

        self.assertEqual(self.test_obj, validator_obj)


if __name__ == '__main__':
    unittest.main()
