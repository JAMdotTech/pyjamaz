import ed25519_zebra
from bip39 import bip39_to_mini_secret


class Keypair:
    def __init__(self, private_key: bytes, public_key: bytes):
        self.private_key = private_key
        self.public_key = public_key

    @classmethod
    def create_from_seed(cls, seed: bytes) -> 'Keypair':
        private_key, public_key = ed25519_zebra.ed_from_seed(seed)
        return cls(private_key, public_key)

    @classmethod
    def create_from_mnemonic(cls, mnemonic: str) -> 'Keypair':
        seed_array = bip39_to_mini_secret(mnemonic, "", 'en')
        return cls.create_from_seed(bytearray(seed_array))

    def sign(self, data: bytes) -> bytes:
        return ed25519_zebra.ed_sign(self.private_key, data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        return ed25519_zebra.ed_verify(signature, data, self.public_key)
