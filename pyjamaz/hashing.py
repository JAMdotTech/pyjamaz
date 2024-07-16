from hashlib import blake2b, sha3_256
from typing import Union
from Crypto.Hash import keccak


def create_blake2b_256_hash(data: Union[str, bytes]) -> bytes:
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=32).digest()


def create_blake2b_128_hash(data: Union[str, bytes]) -> bytes:
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=16).digest()


def create_blake2b_64_hash(data: Union[str, bytes]) -> bytes:
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=8).digest()


def create_keccak_256_hash(data: Union[str, bytes]) -> bytes:
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    k = keccak.new(digest_bits=256)
    k.update(data)

    return k.digest()
