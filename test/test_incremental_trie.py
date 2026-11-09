import random
from dataclasses import FrozenInstanceError

import pytest

from pyjamaz import merkle
from pyjamaz.incremental_trie import IncrementalMerkleTrie
from pyjamaz.merkle import PatriciaMerkleTrie


def reference_root(data):
    return PatriciaMerkleTrie(list(data.items())).root()


@pytest.fixture(autouse=True)
def clear_hash_caches():
    caches = (
        merkle._cached_trie_leaf_hash,
        merkle._cached_trie_large_leaf_hash,
        merkle._cached_trie_branch_hash,
    )
    for cache in caches:
        cache.cache_clear()
    yield
    for cache in caches:
        cache.cache_clear()


@pytest.mark.parametrize("key_length", [31, 32])
def test_random_update_batches_match_full_rebuild(key_length):
    rng = random.Random(1847)
    keys = [rng.randbytes(key_length) for _ in range(100)]
    data = {key: rng.randbytes(rng.randrange(80)) for key in keys[:40]}
    trie = IncrementalMerkleTrie(data.items())
    assert trie.root() == reference_root(data)

    for _ in range(150):
        changes = {
            rng.choice(keys): None if rng.randrange(3) == 0 else rng.randbytes(rng.randrange(80))
            for _ in range(rng.randrange(1, 10))
        }
        previous, previous_root = trie, trie.root()
        trie = trie.update(changes)
        for key, value in changes.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        assert trie.root() == reference_root(data)
        assert previous.root() == previous_root


@pytest.mark.parametrize("key_length", [31, 32])
def test_shared_prefix_branches_survive_until_only_one_leaf_remains(key_length):
    first = bytes(key_length)
    second = bytes(key_length - 1) + b"\x01"
    outside = b"\x80" + bytes(key_length - 1)
    data = {first: b"first", second: b"second", outside: b"outside"}
    trie = IncrementalMerkleTrie(data)

    # Removing the other half leaves unary branches above two deep leaves.
    trie = trie.update({outside: None})
    del data[outside]
    assert trie.root() == reference_root(data)
    assert trie._node.right is None
    assert trie._node.left is not None

    trie = trie.update({second: None})
    del data[second]
    assert trie.root() == reference_root(data)
    assert trie._node.key == first
    assert trie.update({first: None}).root() == bytes(32)


def test_empty_values_are_distinct_from_missing_entries():
    key = bytes(31)
    empty = IncrementalMerkleTrie()
    stored = empty.update({key: b""})
    assert stored.root() == reference_root({key: b""})
    assert stored.root() != empty.root()
    assert stored.update({key: None}).root() == empty.root()


def test_no_op_changes_preserve_snapshot_identity():
    key, absent = bytes(31), b"\x80" + bytes(30)
    trie = IncrementalMerkleTrie({key: b"value"})
    assert trie.update({}) is trie
    assert trie.update({key: b"value"}) is trie
    assert trie.update({absent: None}) is trie
    assert trie.update({key: b"value", absent: None}) is trie


def test_forks_and_constructor_inputs_are_isolated():
    left, right = bytes(31), b"\x80" + bytes(30)
    data = {left: b"left", right: b"right"}
    base = IncrementalMerkleTrie(data)
    base_root = base.root()
    first = base.update({left: b"first"})
    second = base.update({right: None})
    data.clear()

    assert base.root() == base_root
    assert first.root() == reference_root({left: b"first", right: b"right"})
    assert second.root() == reference_root({left: b"left"})
    with pytest.raises(FrozenInstanceError):
        base._node = None
    with pytest.raises(FrozenInstanceError):
        base._node.left.value = b"mutated"


def test_update_shares_untouched_subtrees_and_hashes_only_changed_path():
    keys = [bytes([head]) + bytes(30) for head in (0x00, 0x40, 0x80, 0xC0)]
    trie = IncrementalMerkleTrie({key: bytes([index]) for index, key in enumerate(keys)})
    leaf_before = merkle._cached_trie_leaf_hash.cache_info()
    branch_before = merkle._cached_trie_branch_hash.cache_info()

    changed = trie.update({keys[0]: b"changed"})

    assert changed._node is not trie._node
    assert changed._node.right is trie._node.right
    assert changed._node.left.right is trie._node.left.right
    leaf_after = merkle._cached_trie_leaf_hash.cache_info()
    branch_after = merkle._cached_trie_branch_hash.cache_info()
    assert leaf_after.misses - leaf_before.misses == 1
    assert branch_after.misses - branch_before.misses == 2
    assert leaf_after.hits == leaf_before.hits
    assert branch_after.hits == branch_before.hits

    for _ in range(3):
        changed.root()
        trie.root()
        assert changed.update({keys[0]: b"changed", bytes([0xE0]) + bytes(30): None}) is changed
    assert merkle._cached_trie_leaf_hash.cache_info() == leaf_after
    assert merkle._cached_trie_branch_hash.cache_info() == branch_after


@pytest.mark.parametrize("key", [b"", bytes(30), bytes(33), bytearray(31), "x" * 31])
def test_invalid_keys_are_rejected(key):
    with pytest.raises(ValueError, match="31- or 32-byte"):
        IncrementalMerkleTrie([(key, b"value")])
    if not isinstance(key, bytearray):
        with pytest.raises(ValueError, match="31- or 32-byte"):
            IncrementalMerkleTrie().update({key: b"value"})


@pytest.mark.parametrize("value", [bytearray(b"value"), memoryview(b"value"), "value", None])
def test_non_bytes_initial_values_are_rejected(value):
    with pytest.raises(TypeError, match="bytes"):
        IncrementalMerkleTrie([(bytes(31), value)])
    if value is not None:
        with pytest.raises(TypeError, match="bytes"):
            IncrementalMerkleTrie().update({bytes(31): value})


@pytest.mark.parametrize("reverse", [False, True])
def test_prefix_collisions_are_rejected_without_changing_the_snapshot(reverse):
    keys = [bytes(31), bytes(32)]
    if reverse:
        keys.reverse()
    with pytest.raises(ValueError, match="prefixes"):
        IncrementalMerkleTrie([(key, b"value") for key in keys])
    trie = IncrementalMerkleTrie({keys[0]: b"original"})
    root = trie.root()
    with pytest.raises(ValueError, match="prefixes"):
        trie.update({keys[1]: b"new"})
    assert trie.root() == root
    assert trie.update({keys[1]: None}) is trie


def test_short_key_collision_with_an_existing_branch_is_rejected():
    trie = IncrementalMerkleTrie({bytes(32): b"first", bytes(31) + b"\x01": b"second"})
    with pytest.raises(ValueError, match="prefixes"):
        trie.update({bytes(31): b"new"})
    assert trie.update({bytes(31): None}) is trie


@pytest.mark.parametrize("reverse", [False, True])
def test_replacing_key_lengths_in_a_batch_ignores_mapping_order(reverse):
    previous, replacement = bytes(31), bytes(32)
    if reverse:
        previous, replacement = replacement, previous
    trie = IncrementalMerkleTrie({previous: b"old"})
    changed = trie.update({replacement: b"new", previous: None})
    assert changed.root() == reference_root({replacement: b"new"})
    assert trie.root() == reference_root({previous: b"old"})


def test_mixed_key_lengths_work_when_no_key_prefixes_another():
    data = {bytes(31): b"short", b"\x80" + bytes(31): b"long"}
    trie = IncrementalMerkleTrie(data)
    assert trie.root() == reference_root(data)
    data[bytes(31)] = b"changed"
    assert trie.update({bytes(31): b"changed"}).root() == reference_root(data)


@pytest.mark.parametrize("size", [32, 33, 8192, 256 * 1024])
def test_value_sizes_use_existing_bounded_leaf_caches(size):
    key, value = bytes(31), b"v" * size
    trie = IncrementalMerkleTrie({key: value})
    assert trie.root() == reference_root({key: value})
    small = merkle._cached_trie_leaf_hash.cache_info()
    large = merkle._cached_trie_large_leaf_hash.cache_info()
    assert small.currsize == (1 if len(key) + size <= 4096 else 0)
    assert large.currsize == (1 if 4096 < len(key) + size <= 256 * 1024 else 0)
