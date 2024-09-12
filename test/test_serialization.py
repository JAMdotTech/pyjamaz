import unittest
from dataclasses import dataclass, field
from typing import List, Type, Union

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.mixins import Serializable, T
from jamcodec.types import VarInt64, U8, Array, BitArray, UnsignedInteger
from pyjamaz.types.safrole import SafroleErrorCode, OutputMarks, SafroleOutput
from pyjamaz.types.common import ValidatorData


@dataclass
class Program(Serializable):
    jump_table_entry_count: int = field(metadata={'codec': VarInt64})
    jump_table_entry_size: int = field(metadata={'codec': U8})
    code_length: int = field(metadata={'codec': VarInt64})
    jump_table: List[int] = field(metadata={'codec': Array(U8, 0)})
    code: bytes = field(metadata={'codec': Array(U8, 0)})
    opcode_bitmask: List[bool] = field(metadata={'codec': BitArray(0)})

    @classmethod
    def from_jam_bytes(cls, scale_bytes: JamBytes) -> 'Program':
        jump_table_entry_count = VarInt64.decode(scale_bytes)
        jump_table_entry_size = U8.decode(scale_bytes)
        code_length = VarInt64.decode(scale_bytes)

        jump_table = Array(UnsignedInteger(jump_table_entry_size * 8), jump_table_entry_count).decode(scale_bytes)
        code = Array(U8, code_length).decode(scale_bytes)
        opcode_bitmask = BitArray(code_length).decode(scale_bytes)

        return cls(
            jump_table_entry_count=jump_table_entry_count,
            jump_table_entry_size=jump_table_entry_size,
            code_length=code_length,
            jump_table=jump_table,
            code=code,
            opcode_bitmask=opcode_bitmask,
        )

    def to_codec_type(self) -> JamCodecType:
        codec_def = self.to_codec_def()
        # Change definition according to data
        codec_def.arguments['jump_table'] = Array(
            UnsignedInteger(self.jump_table_entry_size * 8), self.jump_table_entry_count
        )
        codec_def.arguments['code'] = Array(U8, self.code_length)
        codec_def.arguments['opcode_bitmask'] = BitArray(self.code_length)

        scale_type = codec_def.new()
        scale_type.deserialize(self)

        return scale_type

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:
        return cls.from_jam_bytes(JamBytes(bytes(data)))

    def serialize(self) -> List[int]:
        return [b for b in self.to_jam_bytes().to_bytes()]


class TestProgramSerialization(unittest.TestCase):

    def test_from_bytes(self):
        program = Program.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        self.assertEqual(program.jump_table_entry_count, 0)
        self.assertEqual(bytes([8, 135, 9]), program.code)

    def test_serialize(self):
        program = Program.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        json_data = program.to_json()
        self.assertEqual([0, 0, 3, 8, 135, 9, 1], json_data)

    def test_to_bytes(self):
        program = Program.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        jam_bytes = program.to_jam_bytes()
        self.assertEqual('0x00000308870901', jam_bytes.to_hex())
        self.assertEqual(program, Program.from_jam_bytes(jam_bytes))


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
        self.assertEqual('0x0106', data.to_hex())

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


if __name__ == '__main__':
    unittest.main()
