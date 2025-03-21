from hashlib import blake2b, sha3_256
from typing import Union
from Crypto.Hash import keccak


def blake2b_256_hash(data: Union[str, bytes]) -> bytes:
    """
    GP-0.5.3-section:I.3 (H) | Creates a Blake-SHA256 hash using the given data.

    Parameters
    ----------
    data: data to be hashed

    Returns
    -------
    bytes hash
    """
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=32).digest()


def blake2b_128_hash(data: Union[str, bytes]) -> bytes:
    """
    Creates a Blake-SHA128 hash using the given data.

    Parameters
    ----------
    data: data to be hashed

    Returns
    -------
    bytes hash
    """
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=16).digest()


def blake2b_64_hash(data: Union[str, bytes]) -> bytes:
    """
    Creates a Blake-SHA64 hash using the given data.
    Parameters
    ----------
    data: data to be hashed

    Returns
    -------
    bytes hash
    """
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=8).digest()


def keccak_256_hash(data: Union[str, bytes]) -> bytes:
    """
    GP-0.5.3-section:I.3 (H_K) | Creates a Keccak-SHA256 hash using the given data.

    Parameters
    ----------
    data: data to be hashed

    Returns
    -------
    bytes hash
    """
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    k = keccak.new(digest_bits=256)
    k.update(data)

    return k.digest()
