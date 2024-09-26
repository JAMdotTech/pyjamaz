from typing import List, Tuple, Optional
from pyjamaz.hashing import blake2b_256_hash, keccak_256_hash


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


class MerkleMountainRange:
    #       D
    #     /   \
    #    /     \
    #   A       B       C
    #  / \     / \     / \
    # 1   2   3   4   5   6  7

    def __init__(self, initial_peaks: List[Optional[bytes]]):
        self.peaks: List[Optional[bytes]] = initial_peaks

    def get_item_count(self) -> int:
        """
        Returns the number of totals values in the MMR.
        """
        return sum(int(v is not None) << i for i, v in enumerate(self.peaks))

    @staticmethod
    def merge_peaks(right: bytes, left: bytes) -> bytes:
        return keccak_256_hash(right + left)

    def insert(self, value: bytes):
        """
        Inserts a new value into the Merkle Mountain Range.
        Parameters
        ----------
        value: bytes

        Returns
        -------

        """

        item_count = self.get_item_count()

        # Check if new item fits in current binary array of peaks
        if (item_count + 1).bit_length() > item_count.bit_length():
            self.peaks.insert(0, None)

        if (item_count + 1) % 2 == 1:
            # Odd items always go on first position
            self.peaks[0] = value
        else:

            # Insert new value
            if self.peaks[0] is None:
                self.peaks[0] = value
            else:
                if self.peaks[1] is not None:
                    # Merge item with sibling
                    self.peaks[0] = self.merge_peaks(self.peaks[0], value)
                    self.peaks[1] = self.merge_peaks(self.peaks[1], self.peaks[0])
                else:
                    self.peaks[1] = self.merge_peaks(self.peaks[0], value)

                self.peaks[0] = None

            item_count += 1

            # Merge attempts
            for idx in range(0, len(self.peaks) - 1):
                # Check if item has sibling
                should_merge = item_count % 2**(idx+1) == 0
                if self.peaks[idx] is not None and should_merge:
                    if self.peaks[idx + 1] is not None:
                        # merge with sibling
                        self.peaks[idx + 1] = self.merge_peaks(self.peaks[idx + 1], self.peaks[idx])
                        self.peaks[idx] = None
                    else:
                        self.peaks[idx + 1] = self.peaks[idx]
                        self.peaks[idx] = None
