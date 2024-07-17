import ed25519_zebra
from bip39 import bip39_to_mini_secret


class Keypair:
    def __init__(self, private_key: bytes, public_key: bytes):
        """
        Allows generation of Keypairs from a variety of input combination, such as a public/private key combination,
        mnemonic or URI containing soft and hard derivation paths. With these Keypairs data can be signed and verified

        Parameters
        ----------
        private_key
        public_key
        """
        self.private_key = private_key
        self.public_key = public_key

    @classmethod
    def create_from_seed(cls, seed: bytes) -> 'Keypair':
        """
        Creates a Keypair from seed bytes.

        Parameters
        ----------
        seed

        Returns
        -------
        Keypair
        """
        private_key, public_key = ed25519_zebra.ed_from_seed(seed)
        return cls(private_key, public_key)

    @classmethod
    def create_from_mnemonic(cls, mnemonic: str) -> 'Keypair':
        """
        Create a Keypair from given mnemonic

        Parameters
        ----------
        mnemonic: string containing 12 or 24 word mnemonic

        Returns
        -------
        Keypair
        """
        seed_array = bip39_to_mini_secret(mnemonic, "", 'en')
        return cls.create_from_seed(bytearray(seed_array))

    def sign(self, data: bytes) -> bytes:
        """
        Creates a signature for given data

        Parameters
        ----------
        data

        Returns
        -------
        bytes
        """
        return ed25519_zebra.ed_sign(self.private_key, data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """
        Verifies data with specified signature

        Parameters
        ----------
        data
        signature

        Returns
        -------
        bool
        """
        return ed25519_zebra.ed_verify(signature, data, self.public_key)
