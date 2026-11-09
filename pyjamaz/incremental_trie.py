"""Persistent Appendix D trie snapshots with cached hashes on immutable nodes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pyjamaz.merkle import PatriciaMerkleTrie, _cached_trie_branch_hash


_EMPTY_HASH = bytes(32)


@dataclass(frozen=True, slots=True)
class _Leaf:
    key: bytes
    value: bytes
    digest: bytes


@dataclass(frozen=True, slots=True)
class _Branch:
    left: _Node
    right: _Node
    digest: bytes


_Node = _Leaf | _Branch | None


def _digest(node: _Node) -> bytes:
    return _EMPTY_HASH if node is None else node.digest


def _leaf(key: bytes, value: bytes) -> _Leaf:
    # Reuse the existing bounded leaf caches, including their admission limits.
    return _Leaf(key, value, PatriciaMerkleTrie([(key, value)]).root())


def _branch(left: _Node, right: _Node) -> _Node:
    if left is None and (right is None or isinstance(right, _Leaf)):
        return right
    if right is None and isinstance(left, _Leaf):
        return left
    # A unary branch containing multiple leaves must retain its bit position.
    return _Branch(left, right, _cached_trie_branch_hash(_digest(left), _digest(right)))


def _build(data: list[tuple[bytes, bytes]], index: int = 0) -> _Node:
    if not data:
        return None
    if len(data) == 1:
        return _leaf(*data[0])
    left, right = [], []
    for key, value in data:
        if index >= len(key) * 8:
            raise ValueError("Trie keys must not be prefixes of one another")
        (right if PatriciaMerkleTrie._bit(key, index) else left).append((key, value))
    return _branch(_build(left, index + 1), _build(right, index + 1))


def _replace(node: _Node, key: bytes, value: bytes | None, index: int) -> _Node:
    if node is None:
        return None if value is None else _leaf(key, value)
    if isinstance(node, _Leaf):
        if key == node.key:
            if value is None:
                return None
            return node if value == node.value else _leaf(key, value)
        if value is None:
            return node
        if key.startswith(node.key) or node.key.startswith(key):
            raise ValueError("Trie keys must not be prefixes of one another")
        old_right = PatriciaMerkleTrie._bit(node.key, index)
        new_right = PatriciaMerkleTrie._bit(key, index)
        if old_right != new_right:
            other = _leaf(key, value)
            return _branch(node, other) if new_right else _branch(other, node)
        child = _replace(node, key, value, index + 1)
        return _branch(None, child) if old_right else _branch(child, None)
    if index >= len(key) * 8:
        if value is None:
            return node
        raise ValueError("Trie keys must not be prefixes of one another")
    if PatriciaMerkleTrie._bit(key, index):
        right = _replace(node.right, key, value, index + 1)
        return node if right is node.right else _branch(node.left, right)
    left = _replace(node.left, key, value, index + 1)
    return node if left is node.left else _branch(left, node.right)


def _validate(key: bytes, value: bytes | None) -> None:
    if type(key) is not bytes or len(key) not in (31, 32):
        raise ValueError("Trie keys must be immutable 31- or 32-byte bytes")
    if value is not None and type(value) is not bytes:
        raise TypeError("Trie values must be immutable bytes or None for deletion")


@dataclass(frozen=True, slots=True, init=False)
class IncrementalMerkleTrie:
    """An immutable trie; updates share unchanged nodes with earlier snapshots.

    ``None`` deletes a key, while ``b\"\"`` is a stored value. Keys may be 31 or
    32 bytes, but a shorter key cannot prefix another key in the same snapshot.
    """

    _node: _Node

    def __init__(self, data: Iterable[tuple[bytes, bytes]] | Mapping[bytes, bytes] = ()):
        values = {}
        entries = data.items() if isinstance(data, Mapping) else data
        for key, value in entries:
            _validate(key, value)
            if value is None:
                raise TypeError("Initial trie values must be immutable bytes")
            values[key] = value
        object.__setattr__(self, "_node", _build(list(values.items())))

    def root(self) -> bytes:
        return _digest(self._node)

    def update(self, changes: Mapping[bytes, bytes | None]) -> IncrementalMerkleTrie:
        node = self._node
        for key, value in changes.items():
            _validate(key, value)
            if value is None:
                node = _replace(node, key, None, 0)
        # Remove obsolete keys first so replacing a short key with a prefixed
        # long key (or vice versa) does not create a transient prefix collision.
        for key, value in changes.items():
            if value is not None:
                node = _replace(node, key, value, 0)
        if node is self._node:
            return self
        snapshot = object.__new__(type(self))
        object.__setattr__(snapshot, "_node", node)
        return snapshot
