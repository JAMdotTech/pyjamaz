import hashlib
import unittest

from hashing import create_blake2b_256_hash, create_blake2b_128_hash, create_blake2b_64_hash, create_keccak_256_hash


class TestHashingFunction(unittest.TestCase):
    def test_blake_2b_256(self):
        data = b"test"
        expected_hash = '928b20366943e2afd11ebc0eae2e53a93bf177a4fcf35bcc64d503704e65e202'

        digest_hex = create_blake2b_256_hash(data).hex()

        self.assertEqual(digest_hex, expected_hash)

    def test_blake_2b_128(self):
        data = b"test"
        expected_hash = '44a8995dd50b6657a037a7839304535b'

        digest_hex = create_blake2b_128_hash(data).hex()

        self.assertEqual(digest_hex, expected_hash)

    def test_blake_2b_64(self):
        data = b"test"
        expected_hash = '96ad3bb4a2d666d3'

        digest_hex = create_blake2b_64_hash(data).hex()

        self.assertEqual(digest_hex, expected_hash)

    def test_keccak_256(self):
        data = b"test"
        expected_hash = '9c22ff5f21f0b81b113e63f7db6da94fedef11b2119b4088b89664fb9a3cb658'

        digest_hex = create_keccak_256_hash(data).hex()

        self.assertEqual(expected_hash, digest_hex)


if __name__ == '__main__':
    unittest.main()
