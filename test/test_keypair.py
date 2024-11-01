import unittest

from pyjamaz.signing import Ed25519Keypair


class TestEd25519Keypair(unittest.TestCase):
    def test_sign_verify(self):

        keypair = Ed25519Keypair(
            private_key=bytes.fromhex('da3cf5b1e9144931a0f0db65664aab662673b099415a7f8121b7245fb0be4143'),
            public_key=bytes.fromhex('f90bc712b5f2864051353177a9d627605d4bf7ec36c7df568cfdcea9f237c185')
        )
        data = b"test"
        signature = keypair.sign(data)

        self.assertTrue(keypair.verify(data, signature))

    def test_verify_invalid_signature(self):
        keypair = Ed25519Keypair(
            private_key=bytes.fromhex('da3cf5b1e9144931a0f0db65664aab662673b099415a7f8121b7245fb0be4143'),
            public_key=bytes.fromhex('f90bc712b5f2864051353177a9d627605d4bf7ec36c7df568cfdcea9f237c185')
        )
        data = b"test"

        signature = bytes.fromhex("4c291bfb0bb9c1274e86d4b666d13b2ac99a0bacc04a4846fb8ea50bda114677f83c1f164af58fc184451e5140cc8160c4de626163b11451d3bbb208a1889f8a")
        self.assertFalse(keypair.verify(data, signature))


if __name__ == '__main__':
    unittest.main()
