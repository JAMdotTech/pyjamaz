from dataclasses import dataclass, field
from typing import Type, TypeVar

import ed25519_zebra
import bandersnatch_vrfs
from bip39 import bip39_to_mini_secret

from jamcodec.mixins import Serializable
from jamcodec.types import H256


T = TypeVar('T')


class Keypair:

    private_key: bytes
    public_key: bytes

    @classmethod
    def from_seed(cls, seed: bytes) -> 'Keypair':
        raise NotImplementedError

    @classmethod
    def from_mnemonic(cls: Type[T], mnemonic: str) -> T:
        """
        Create a Keypair from given mnemonic

        Parameters
        ----------
        mnemonic: string containing 12 or 24 word mnemonic

        Returns
        -------
        Ed25519Keypair
        """
        seed_array = bip39_to_mini_secret(mnemonic, "", 'en')
        return cls.from_seed(bytearray(seed_array))

    @classmethod
    def from_public_key(cls: Type[T], public_key: bytes) -> T:
        return cls(private_key=bytes(32), public_key=bytes(public_key))

    @classmethod
    def from_private_key(cls: Type[T], private_key: bytes) -> T:
        raise NotImplementedError

    def sign(self, data: bytes) -> bytes:
        raise NotImplementedError

    def verify(self, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError


@dataclass
class BandersnatchKeypair(Serializable, Keypair):
    private_key: bytes = field(metadata={'codec': H256})
    public_key: bytes = field(metadata={'codec': H256})

    @classmethod
    def from_seed(cls: Type[T], seed: bytes) -> T:
        """
        Creates a Keypair from seed bytes.

        Parameters
        ----------
        seed

        Returns
        -------
        Ed25519Keypair
        """
        private_key = bandersnatch_vrfs.secret_from_seed(seed)
        public_key = bandersnatch_vrfs.public_from_secret(private_key)
        return cls(private_key=private_key, public_key=public_key)


@dataclass
class Ed25519Keypair(Serializable, Keypair):
    """
    Allows generation of Keypairs from a variety of input combination, such as a public/private key combination,
    mnemonic or URI containing soft and hard derivation paths. With these Keypairs data can be signed and verified

    Parameters
    ----------
    private_key
    public_key
    """
    private_key: bytes = field(metadata={'codec': H256})
    public_key: bytes = field(metadata={'codec': H256})

    @classmethod
    def from_seed(cls: Type[T], seed: bytes) -> T:
        """
        Creates a Keypair from seed bytes.

        Parameters
        ----------
        seed

        Returns
        -------
        Ed25519Keypair
        """
        private_key, public_key = ed25519_zebra.ed_from_seed(seed)
        return cls(private_key=private_key, public_key=public_key)

    @classmethod
    def from_private_key(cls: Type[T], private_key: bytes) -> T:
        public_key = ed25519_zebra.ed_public_from_secret(private_key)
        return cls(private_key=private_key, public_key=public_key)

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
        if self.private_key == bytes(32):
            raise ValueError("Cannot sign, private key is not set")

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
