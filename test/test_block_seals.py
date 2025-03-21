import json
import unittest
from os import path

from bandersnatch_vrfs import ietf_vrf_verify

from jamcodec.base import JamBytes
from pyjamaz.models.block import Header
from pyjamaz.signing import BandersnatchKeypair
from pyjamaz.utils import vrf_input_ticket_seal, vrf_input_fallback_seal


class TestBlockSeals(unittest.TestCase):
    def test_fallback_seal(self):

        for nr in [0,1,2,4,5]:

            with open(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'seals', f'0-{nr}.json')) as f:
                test_vector = json.load(f)

            header = Header.from_jam_bytes(JamBytes(bytes.fromhex(test_vector['header_bytes'])))
            author = BandersnatchKeypair(
                public_key=bytes.fromhex(test_vector['bandersnatch_pub']),
                private_key=bytes.fromhex(test_vector['bandersnatch_priv'])
            )

            eta3 = bytes.fromhex(test_vector['eta3'])

            self.assertEqual(bytes.fromhex(test_vector['m_for_H_s']), header.get_unsigned_payload())

            vr_input = vrf_input_fallback_seal(eta3)
            self.assertEqual(bytes.fromhex(test_vector['c_for_H_s']), vr_input)

            header_vrf_output = author.vrf_output(vr_input)

            entropy_source = author.ietf_vrf_sign(b"jam_entropy" + header_vrf_output, b'')

            eta0 = author.ietf_vrf_verify(b"jam_entropy" + header_vrf_output, b'', entropy_source)

            self.assertEqual(bytes.fromhex(test_vector['H_v']), entropy_source)
            self.assertEqual(header.entropy_source, entropy_source)

            block_seal = header.generate_fallback_seal(author.private_key, eta3)

            self.assertEqual(bytes.fromhex(test_vector['H_s']), block_seal)
            self.assertEqual(bytes.fromhex(test_vector['H_s']), header.seal)

    def test_ticket_seal(self):

        for nr in range(0, 5):

            with open(path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'seals', f'1-{nr}.json')) as f:
                test_vector = json.load(f)

            header = Header.from_jam_bytes(JamBytes(bytes.fromhex(test_vector['header_bytes'])))
            author = BandersnatchKeypair(
                public_key=bytes.fromhex(test_vector['bandersnatch_pub']),
                private_key=bytes.fromhex(test_vector['bandersnatch_priv'])
            )

            eta3 = bytes.fromhex(test_vector['eta3'])

            self.assertEqual(bytes.fromhex(test_vector['m_for_H_s']), header.get_unsigned_payload())

            vrf_input = vrf_input_ticket_seal(eta3, test_vector['attempt'])

            self.assertEqual(bytes.fromhex(test_vector['c_for_H_s']), vrf_input)

            header_vrf_output = author.vrf_output(vrf_input)

            self.assertEqual(bytes.fromhex(test_vector['ticket_id'][2:]), header_vrf_output)

            entropy_source = author.ietf_vrf_sign(b"jam_entropy" + header_vrf_output, b'')

            eta0 = author.ietf_vrf_verify(b"jam_entropy" + header_vrf_output, b'', entropy_source)

            self.assertEqual(bytes.fromhex(test_vector['H_v']), entropy_source)
            self.assertEqual(header.entropy_source, entropy_source)

            block_seal = header.generate_ticket_seal(author.private_key, eta3, test_vector['attempt'])

            header_vrf_output = author.ietf_vrf_verify(vrf_input, header.get_unsigned_payload(), block_seal)

            self.assertEqual(bytes.fromhex(test_vector['H_s']), block_seal)
            self.assertEqual(bytes.fromhex(test_vector['H_s']), header.seal)

if __name__ == '__main__':
    unittest.main()
