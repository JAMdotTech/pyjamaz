from copy import deepcopy

import pytest

from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


KEYS = [bytes([index]) * 31 for index in range(8)]
FINALIZED, PARENT, LEFT, RIGHT, CHILD = [bytes([index]) * 32 for index in range(1, 6)]


def commit(storage, block_hash, parent_hash, changes):
    storage.set_block_hash(block_hash, parent_hash)
    for key, value in changes.items():
        storage.put(key, value)
    storage.commit()


@pytest.fixture
def forked_state():
    a, b, c, d, e, f, g, _ = KEYS
    base = {d: b"base d", c: b"", b: b"b" * 33, a: b"base a"}
    storage = StateStorage(InMemoryStorageEngine(base.copy()))
    storage.set_finalized_block_hash(FINALIZED)
    commit(storage, PARENT, FINALIZED, {a: b"parent a", b: None, e: b"parent e"})
    commit(storage, LEFT, PARENT, {a: None, b: b"restored b", e: b"left e", f: b"left f"})
    commit(storage, RIGHT, PARENT, {a: b"right a", d: None, e: None, g: b"right g"})
    commit(storage, CHILD, LEFT, {b: None, e: b"child e"})
    expected = {
        FINALIZED: base,
        PARENT: {a: b"parent a", c: b"", d: b"base d", e: b"parent e"},
        LEFT: {b: b"restored b", c: b"", d: b"base d", e: b"left e", f: b"left f"},
        RIGHT: {a: b"right a", c: b"", g: b"right g"},
        CHILD: {c: b"", d: b"base d", e: b"child e", f: b"left f"},
    }
    return storage, expected


def assert_state(storage, block_hash, expected):
    ordered = sorted(expected.items())
    root = PatriciaMerkleTrie(ordered).root()
    storage.select_block_hash(block_hash)
    assert storage.as_dict() == expected
    assert storage.as_list() == ordered
    assert storage.state_root() == root
    assert storage.as_dict_at(block_hash) == expected
    assert storage.as_list_at(block_hash) == ordered
    assert storage.state_root_at(block_hash) == root


def test_newest_changes_and_deletions_win_on_each_branch(forked_state):
    storage, expected = forked_state
    changes = deepcopy(storage.change_sets)

    for block_hash in (CHILD, RIGHT, LEFT, PARENT, FINALIZED, CHILD):
        assert_state(storage, block_hash, expected[block_hash])

    assert storage.storage_engine.as_dict() == expected[FINALIZED]
    assert storage.change_sets == changes


def test_views_follow_rollback_and_finalization(forked_state):
    storage, expected = forked_state
    storage.select_block_hash(CHILD)
    storage.put(KEYS[7], b"pending")
    storage.rollback()
    assert_state(storage, LEFT, expected[LEFT])

    storage.finalize(PARENT)
    for block_hash in (PARENT, LEFT, RIGHT):
        assert_state(storage, block_hash, expected[block_hash])
    storage.finalize(LEFT)
    assert_state(storage, LEFT, expected[LEFT])
    assert RIGHT not in storage.change_sets


@pytest.mark.parametrize("method", ["as_dict", "as_list", "state_root"])
def test_materialization_rejects_pending_transactions(forked_state, method):
    storage, _ = forked_state
    storage.put(KEYS[7], b"pending")

    with pytest.raises(ValueError, match="Pending transaction"):
        getattr(storage, method)()


def test_retained_snapshots_exclude_pending_writes(forked_state):
    storage, expected = forked_state
    storage.put(KEYS[7], b"pending")
    ordered = sorted(expected[CHILD].items())

    assert storage.as_dict_at(CHILD) == expected[CHILD]
    assert storage.as_list_at(CHILD) == ordered
    assert storage.state_root_at(CHILD) == PatriciaMerkleTrie(ordered).root()
    assert storage.transaction == {KEYS[7]: b"pending"}


@pytest.mark.parametrize("method", ["as_dict", "as_list", "state_root"])
def test_materialization_still_rejects_parent_cycles(forked_state, method):
    storage, _ = forked_state
    storage.parents[PARENT] = CHILD

    with pytest.raises(ValueError, match="Cycle detected"):
        getattr(storage, method)()


@pytest.mark.parametrize("count", [0, 1, 8])
def test_root_is_independent_of_storage_iteration_order(count):
    items = [(key, bytes([index]) * (31 + index)) for index, key in enumerate(KEYS[:count])]
    expected_root = PatriciaMerkleTrie(items).root()

    for order in (items, items[::-1]):
        storage = StateStorage(InMemoryStorageEngine(dict(order)))
        storage.set_finalized_block_hash(FINALIZED)
        assert storage.state_root() == expected_root
        assert storage.state_root_at(FINALIZED) == expected_root
        assert storage.as_list() == sorted(items)
