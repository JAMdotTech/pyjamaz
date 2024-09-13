import unittest

from jamcodec.base import JamBytes

from pyjamaz.pvm.types import PVMProgram
from pyjamaz.types.safrole import SafroleErrorCode, OutputMarks, SafroleOutput
from pyjamaz.types.common import ValidatorData


class TestProgramSerialization(unittest.TestCase):

    def test_from_bytes(self):
        program = PVMProgram.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        self.assertEqual(program.jump_table_entry_count, 0)
        self.assertEqual(bytes([8, 135, 9]), program.code)

    def test_serialize(self):
        program = PVMProgram.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        json_data = program.to_json()
        self.assertEqual([0, 0, 3, 8, 135, 9, 1], json_data)

    def test_to_bytes(self):
        program = PVMProgram.from_jam_bytes(JamBytes(bytes([0, 0, 3, 8, 135, 9, 249])))
        jam_bytes = program.to_jam_bytes()
        self.assertEqual('0x00000308870901', jam_bytes.to_hex())
        self.assertEqual(program, PVMProgram.from_jam_bytes(jam_bytes))


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
