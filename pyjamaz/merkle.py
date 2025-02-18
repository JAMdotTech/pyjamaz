from math import ceil
from typing import List, Tuple, Optional
from pyjamaz.hashing import blake2b_256_hash, keccak_256_hash


class PatriciaMerkleTrie:
    def __init__(self, data: List[Tuple[bytes, bytes]]):
        self.data = data

    @staticmethod
    def _branch(left: bytes, right: bytes) -> bytes:
        """
        GP-0.5.0-eq:D.3 | Creates a branch node from two 32-byte hashes
        """
        assert len(left) == 32 and len(right) == 32, "Branch inputs must be 32 bytes each."
        return bytes([left[0] & 0x7f]) + left[1:] + right

    @staticmethod
    def _leaf(key: bytes, value: bytes) -> bytes:
        """
        GP-0.5.0-eq:D.4 | Creates a leaf node encoding the key-value pair.
        """
        if len(value) <= 32:
            head = 0b10000000 | len(value)
            return bytes([head]) + key[:-1] + value.ljust(32, b'\0')
        else:
            head = 0b11000000
            return bytes([head]) + key[:-1] + blake2b_256_hash(value)

    @staticmethod
    def _bit(key: bytes, index: int) -> bool:
        """
        Returns the bit value at a specific index in the key.
        """
        return (key[index >> 3] & (1 << (7 - index & 7))) != 0

    def merkle(self, data: List[Tuple[bytes, bytes]], index: int = 0) -> bytes:
        """
        GP-0.5.0-eq:D.6 |
        """
        if len(data) == 0:
            return b'\0' * 32
        if len(data) == 1:
            encoded = self._leaf(*data[0])
        else:
            left, right = [], []
            for key, value in data:
                (right if self._bit(key, index) else left).append((key, value))
            encoded = self._branch(self.merkle(left, index + 1), self.merkle(right, index + 1))

        assert len(encoded) == 64, "Encoded node length must be 64 bytes."

        return blake2b_256_hash(encoded)

    def root(self, index=0) -> bytes:
        """
        GP-0.5.0-eq:D.5 | Constructs a Patricia Merkle trie root hash from the key-value pairs
        """
        return self.merkle(self.data, index=index)


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

    def super_peak(self, peaks: Optional[List[bytes]] = None) -> bytes:
        """
        GP-0.6.1-eq:E.10 (M_R) | Calculate the MMR super peak

        Returns
        -------
        bytes
        """
        if peaks is None:
            peaks = [peak for peak in self.peaks if peak is not None]

        if len(peaks) == 0:
            return bytes(32)
        elif len(peaks) == 1:
            return peaks[0]
        else:
            return keccak_256_hash(b'peak' + self.super_peak(peaks[:-1]) + peaks[-1])


class BinaryMerkleTree:
    def __init__(self, data: List[bytes], hash_function=keccak_256_hash):
        self.data: List[bytes] = data
        self.hash_function = hash_function

    def node(self, nodes: List[bytes]) -> bytes:
        """
        GP-0.5.3-eq:E.1 | Node function

        Parameters
        ----------
        nodes

        Returns
        -------
        bytes
        """
        if len(nodes) == 0:
            return bytes(32)
        elif len(nodes) == 1:
            return nodes[0]
        else:
            node_limit = ceil(len(nodes)/2)
            return self.hash_function(b'node' + self.node(nodes[:node_limit]) + self.node(nodes[node_limit:]))


class WellBalancedMerkleTree(BinaryMerkleTree):
    def root(self):
        """
        GP-0.5.3-eq:E.3 | well-balanced merkle tree root hash

        Returns
        -------
        bytes
        """
        if len(self.data) == 1:
            return self.hash_function(self.data[0])
        else:
            return self.node(self.data)
