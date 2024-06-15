from hashlib import blake2b
from typing import Union


def create_blake2b_hash(data: Union[str, bytes]) -> bytes:
    if type(data) is str:
        data = bytes.fromhex(data[2:])
    return blake2b(data, digest_size=32).digest()
