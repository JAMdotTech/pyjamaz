from hashlib import blake2b

import pytest

from pyjamaz import merkle
from pyjamaz.merkle import PatriciaMerkleTrie


def digest(data):
    return blake2b(data, digest_size=32).digest()


def reference_root(entries, index=0, hash_function=digest):
    """Uncached reference that does not call the production node encoders."""
    if not entries:
        return bytes(32)
    if len(entries) == 1:
        key, value = entries[0]
        if len(value) <= 32:
            encoded = bytes([0x80 | len(value)]) + key + value.ljust(32, b"\0")
        else:
            encoded = b"\xc0" + key + hash_function(value)
    else:
        left, right = [], []
        for key, value in entries:
            side = right if key[index // 8] & (0x80 >> (index % 8)) else left
            side.append((key, value))
        left_hash = reference_root(left, index + 1, hash_function)
        right_hash = reference_root(right, index + 1, hash_function)
        encoded = bytes([left_hash[0] & 0x7F]) + left_hash[1:] + right_hash
    return hash_function(encoded)


KEYS = [blake2b(bytes([i]), digest_size=31).digest() for i in range(8)]


@pytest.fixture(autouse=True)
def clear_trie_hash_caches():
    merkle._cached_trie_leaf_hash.cache_clear()
    merkle._cached_trie_large_leaf_hash.cache_clear()
    merkle._cached_trie_branch_hash.cache_clear()
    yield
    merkle._cached_trie_leaf_hash.cache_clear()
    merkle._cached_trie_large_leaf_hash.cache_clear()
    merkle._cached_trie_branch_hash.cache_clear()


@pytest.mark.parametrize("length", [0, 1, 31, 32, 33, 4096])
def test_leaf_hash_matches_reference_at_value_boundaries(length):
    entries = [(KEYS[0], bytes(range(256)) * (length // 256) + bytes(range(length % 256)))]

    assert PatriciaMerkleTrie(entries).root() == reference_root(entries)
    assert PatriciaMerkleTrie(entries).root() == reference_root(entries)


def test_roots_follow_changed_entries_and_forks_in_any_order():
    base = list(zip(KEYS, [b"", b"a", b"b" * 31, b"c" * 32, b"d" * 33,
                           b"e" * 256, b"f", b"g"]))
    changed_value = [(key, b"changed" if key == KEYS[2] else value) for key, value in base]
    changed_key = [(blake2b(b"replacement", digest_size=31).digest(), base[0][1]), *base[1:]]
    removed = base[1:]

    for entries in (base, changed_value, changed_key, removed, base, changed_value, base):
        expected = reference_root(entries)
        assert PatriciaMerkleTrie(entries).root() == expected
        assert PatriciaMerkleTrie(list(reversed(entries))).root() == expected


@pytest.mark.parametrize("index", [0, 1, 8, 17])
def test_root_respects_starting_bit_index(index):
    entries = list(zip(KEYS, [bytes([i]) * (i + 31) for i in range(len(KEYS))]))

    assert PatriciaMerkleTrie(entries).root(index=index) == reference_root(entries, index=index)


def test_mutating_source_entries_does_not_return_a_stale_root():
    entries = [(KEYS[0], b"initial"), (KEYS[1], b"unchanged" * 8)]
    trie = PatriciaMerkleTrie(entries)
    original = trie.root()

    entries[0] = (KEYS[0], b"changed")
    assert trie.root() == reference_root(entries)
    assert trie.root() != original

    entries.append((KEYS[2], b"added"))
    assert trie.root() == reference_root(entries)
    entries.pop()
    entries[0] = (KEYS[0], b"initial")
    assert trie.root() == original


@pytest.mark.parametrize("length", [32, 33, 8192])
def test_mutating_input_buffers_does_not_return_a_stale_hash(length):
    key = bytearray(KEYS[0])
    value = bytearray(b"v" * length)
    entries = [(key, value)]
    trie = PatriciaMerkleTrie(entries)
    original = trie.root()

    value[0] = ord("w")
    assert trie.root() == reference_root(entries)
    assert trie.root() != original
    key[0] ^= 0x80
    assert trie.root() == reference_root(entries)

    # Earlier cache entries must retain their original content if the cache
    # accepts mutable buffers, rather than retaining references to the buffers.
    assert PatriciaMerkleTrie([(KEYS[0], b"v" * length)]).root() == original


def test_empty_root_remains_zero():
    assert PatriciaMerkleTrie([]).root() == bytes(32)


def test_repeated_roots_reuse_hashes_across_instances_and_input_order():
    entries = list(zip(KEYS, [bytes([i]) * (i + 31) for i in range(len(KEYS))]))
    expected = reference_root(entries)
    assert PatriciaMerkleTrie(entries).root() == expected
    initial_leaf = merkle._cached_trie_leaf_hash.cache_info()
    initial_branch = merkle._cached_trie_branch_hash.cache_info()

    assert PatriciaMerkleTrie(list(reversed(entries))).root() == expected
    leaf = merkle._cached_trie_leaf_hash.cache_info()
    branch = merkle._cached_trie_branch_hash.cache_info()
    assert leaf.misses == initial_leaf.misses
    assert branch.misses == initial_branch.misses
    assert leaf.hits > initial_leaf.hits
    assert branch.hits > initial_branch.hits


def test_small_leaf_cache_routes_larger_inputs_to_the_large_cache():
    limit = merkle._TRIE_LEAF_CACHE_MAX_INPUT_BYTES
    key = KEYS[0]
    accepted = [(key, b"a" * (limit - len(key)))]
    oversized = [(key, b"b" * (limit - len(key) + 1))]

    for _ in range(2):
        assert PatriciaMerkleTrie(accepted).root() == reference_root(accepted)
    cached = merkle._cached_trie_leaf_hash.cache_info()
    assert cached.currsize == 1
    assert cached.hits == 1

    for _ in range(2):
        assert PatriciaMerkleTrie(oversized).root() == reference_root(oversized)
    assert merkle._cached_trie_leaf_hash.cache_info() == cached
    large = merkle._cached_trie_large_leaf_hash.cache_info()
    assert large.currsize == 1
    assert large.hits == 1


def test_large_leaf_cache_admits_only_inputs_within_its_byte_limit():
    limit = merkle._TRIE_LARGE_LEAF_CACHE_MAX_INPUT_BYTES
    key = KEYS[0]
    accepted = [(key, b"a" * (limit - len(key)))]
    oversized = [(key, b"b" * (limit - len(key) + 1))]

    for _ in range(2):
        assert PatriciaMerkleTrie(accepted).root() == reference_root(accepted)
    cached = merkle._cached_trie_large_leaf_hash.cache_info()
    assert cached.currsize == 1
    assert cached.hits == 1

    for _ in range(2):
        assert PatriciaMerkleTrie(oversized).root() == reference_root(oversized)
    assert merkle._cached_trie_large_leaf_hash.cache_info() == cached
    assert merkle._cached_trie_leaf_hash.cache_info().currsize == 0


def test_large_leaf_reuse_depends_on_content_across_independent_buffers():
    key = KEYS[0]
    value = b"program" * 20000
    expected = reference_root([(key, value)])
    assert PatriciaMerkleTrie([(key, value)]).root() == expected
    copied_value = bytes(bytearray(value))
    assert copied_value is not value

    assert PatriciaMerkleTrie([(key, copied_value)]).root() == expected
    cached = merkle._cached_trie_large_leaf_hash.cache_info()
    assert cached.currsize == 1
    assert cached.misses == 1
    assert cached.hits == 1


def test_mutable_inputs_bypass_the_leaf_cache():
    for key, value in (
        (bytearray(KEYS[0]), b"a"),
        (KEYS[0], bytearray(b"a" * 33)),
        (KEYS[0], bytearray(b"a" * 8192)),
    ):
        entries = [(key, value)]
        assert PatriciaMerkleTrie(entries).root() == reference_root(entries)
        assert PatriciaMerkleTrie(entries).root() == reference_root(entries)
    assert merkle._cached_trie_leaf_hash.cache_info().currsize == 0
    assert merkle._cached_trie_large_leaf_hash.cache_info().currsize == 0


def test_leaf_cache_has_bounded_retention_and_evicts_old_entries():
    cache = merkle._cached_trie_leaf_hash
    limit = cache.cache_info().maxsize
    assert limit == 4096
    for index in range(limit + 1):
        key = index.to_bytes(31, "little")
        assert cache(key, b"value") == reference_root([(key, b"value")])
    assert cache.cache_info().currsize == limit

    before = cache.cache_info()
    cache(bytes(31), b"value")
    assert cache.cache_info().misses == before.misses + 1
    assert cache.cache_info().currsize == limit


def test_large_leaf_cache_has_bounded_retention_and_evicts_old_entries():
    cache = merkle._cached_trie_large_leaf_hash
    limit = cache.cache_info().maxsize
    assert limit == 32
    value = b"v" * 8192
    for index in range(limit + 1):
        key = index.to_bytes(31, "little")
        assert cache(key, value) == reference_root([(key, value)])
    assert cache.cache_info().currsize == limit

    before = cache.cache_info()
    cache(bytes(31), value)
    assert cache.cache_info().misses == before.misses + 1
    assert cache.cache_info().currsize == limit


def test_branch_cache_has_bounded_retention_and_evicts_old_entries():
    cache = merkle._cached_trie_branch_hash
    limit = cache.cache_info().maxsize
    assert limit == 8192
    right = bytes(32)
    for index in range(limit + 1):
        left = index.to_bytes(32, "little")
        encoded = bytes([left[0] & 0x7F]) + left[1:] + right
        assert cache(left, right) == digest(encoded)
    assert cache.cache_info().currsize == limit

    before = cache.cache_info()
    cache(bytes(32), right)
    assert cache.cache_info().misses == before.misses + 1
    assert cache.cache_info().currsize == limit


def test_subclass_leaf_encoder_is_preserved():
    class TaggedLeafTrie(PatriciaMerkleTrie):
        @staticmethod
        def _leaf(key, value):
            return b"custom" + PatriciaMerkleTrie._leaf(key, value)

    key, value = KEYS[0], b"value"
    PatriciaMerkleTrie([(key, value)]).root()
    expected = digest(b"custom" + bytes([0x80 | len(value)]) + key + value.ljust(32, b"\0"))
    before = merkle._cached_trie_leaf_hash.cache_info()
    assert TaggedLeafTrie([(key, value)]).root() == expected
    assert merkle._cached_trie_leaf_hash.cache_info() == before


def test_subclass_branch_encoder_is_preserved():
    class TaggedBranchTrie(PatriciaMerkleTrie):
        @staticmethod
        def _branch(left, right):
            return b"custom" + PatriciaMerkleTrie._branch(left, right)

    entries = [(bytes(31), b"left"), (b"\x80" + bytes(30), b"right")]
    PatriciaMerkleTrie(entries).root()
    left, right = (reference_root([entry]) for entry in entries)
    expected = digest(b"custom" + bytes([left[0] & 0x7F]) + left[1:] + right)
    before = merkle._cached_trie_branch_hash.cache_info()
    assert TaggedBranchTrie(entries).root() == expected
    assert merkle._cached_trie_branch_hash.cache_info() == before


def test_mutable_child_hashes_bypass_the_branch_cache():
    class MutableChildHashTrie(PatriciaMerkleTrie):
        def merkle(self, data, index=0):
            result = super().merkle(data, index)
            return bytearray(result) if len(data) == 1 else result

    entries = [(bytes(31), b"left"), (b"\x80" + bytes(30), b"right")]
    PatriciaMerkleTrie(entries).root()
    before = merkle._cached_trie_branch_hash.cache_info()

    assert MutableChildHashTrie(entries).root() == reference_root(entries)
    assert merkle._cached_trie_branch_hash.cache_info() == before


def test_oversized_child_hashes_preserve_validation_without_cache_admission():
    class OversizedChildHashTrie(PatriciaMerkleTrie):
        def merkle(self, data, index=0):
            if len(data) == 1:
                return b"x" * 33
            return super().merkle(data, index)

    entries = [(bytes(31), b"left"), (b"\x80" + bytes(30), b"right")]
    PatriciaMerkleTrie(entries).root()
    before = merkle._cached_trie_branch_hash.cache_info()

    with pytest.raises(AssertionError, match="Branch inputs must be 32 bytes each"):
        OversizedChildHashTrie(entries).root()
    assert merkle._cached_trie_branch_hash.cache_info() == before


@pytest.mark.parametrize("length", [80, 8192])
def test_overridden_hash_function_is_preserved_after_cache_warmup(monkeypatch, length):
    entries = [(KEYS[0], b"v" * length), (KEYS[1], b"short")]
    PatriciaMerkleTrie(entries).root()
    before_leaf = merkle._cached_trie_leaf_hash.cache_info()
    before_large_leaf = merkle._cached_trie_large_leaf_hash.cache_info()
    before_branch = merkle._cached_trie_branch_hash.cache_info()

    def custom_hash(data):
        return digest(b"custom" + data)

    monkeypatch.setattr(merkle, "blake2b_256_hash", custom_hash)
    assert PatriciaMerkleTrie(entries).root() == reference_root(entries, hash_function=custom_hash)
    assert merkle._cached_trie_leaf_hash.cache_info() == before_leaf
    assert merkle._cached_trie_large_leaf_hash.cache_info() == before_large_leaf
    assert merkle._cached_trie_branch_hash.cache_info() == before_branch
