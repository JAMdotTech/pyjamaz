import hashlib
from typing import List, Tuple, Optional

from pyjamaz.hashing import blake2b_256_hash


class MerkleTree:
    def __init__(self, tree_data: List[Tuple[bytes, bytes]]):
        self.tree_data = tree_data

    @staticmethod
    def _branch(left: bytes, right: bytes) -> bytes:
        """Creates a branch node from two 32-byte hashes."""
        assert len(left) == 32 and len(right) == 32, "Branch inputs must be 32 bytes each."
        return bytes([left[0] & 0xfe]) + left[1:] + right

    @staticmethod
    def _leaf(key: bytes, value: bytes) -> bytes:
        """Creates a leaf node encoding the key-value pair."""
        if len(value) <= 32:
            head = 0b01 | (len(value) << 2)
            return bytes([head]) + key[:-1] + value.ljust(32, b'\0')
        else:
            head = 0b11
            return bytes([head]) + key[:-1] + blake2b_256_hash(value)

    @staticmethod
    def _bit(key: bytes, index: int) -> bool:
        """Returns the bit value at a specific index in the key."""
        return (key[index >> 3] & (1 << (index & 7))) != 0

    def merkle(self, tree_data: List[Tuple[bytes, bytes]], index: int = 0) -> bytes:
        """Constructs a Merkle tree root hash from the key-value pairs."""
        if len(tree_data) == 0:
            return b'\0' * 32
        if len(tree_data) == 1:
            encoded = self._leaf(*tree_data[0])
        else:
            left, right = [], []
            for key, value in tree_data:
                (right if self._bit(key, index) else left).append((key, value))
            encoded = self._branch(self.merkle(left, index + 1), self.merkle(right, index + 1))

        assert len(encoded) == 64, "Encoded node length must be 64 bytes."

        return blake2b_256_hash(encoded)

    def root(self, index=0) -> bytes:
        return self.merkle(self.tree_data, index=index)
