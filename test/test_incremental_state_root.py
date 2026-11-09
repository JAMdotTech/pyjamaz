"""State-root reuse must observe every materialized state and storage mutation."""

from contextlib import contextmanager
from copy import deepcopy

import pytest

from pyjamaz import merkle
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.state import storage as state_storage_module
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


KEYS = [bytes([index]) * 31 for index in range(8)]
FINALIZED, PARENT, LEFT, RIGHT, CHILD = [bytes([index]) * 32 for index in range(1, 6)]


def reference_root(items):
    # Freeze buffers independently of any snapshot retained by StateStorage.
    return PatriciaMerkleTrie([(bytes(key), bytes(value)) for key, value in items.items()]).root()


def commit(storage, block_hash, parent_hash, changes):
    storage.set_block_hash(block_hash, parent_hash)
    for key, value in changes.items():
        storage.put(key, value)
    storage.commit()


def assert_root(storage, expected):
    root = reference_root(expected)
    assert storage.as_dict() == expected
    assert storage.state_root() == root
    assert storage.state_root() == root


def assert_retained_root(storage, block_hash, expected):
    selected = storage.block_hash
    assert storage.state_root_at(block_hash) == reference_root(expected)
    assert storage.block_hash == selected


@pytest.fixture
def forked_state():
    a, b, c, d, e, f, _, _ = KEYS
    base = {a: b"base a", b: b"b" * 33, c: b""}
    engine = InMemoryStorageEngine()
    state_engine = engine.namespace(b"state")
    for key, value in base.items():
        state_engine.put(key, value)
    storage = StateStorage(state_engine)
    storage.set_finalized_block_hash(FINALIZED)
    commit(storage, PARENT, FINALIZED, {a: b"parent a", d: b"parent d"})
    commit(storage, LEFT, PARENT, {b: None, e: b"left e"})
    commit(storage, RIGHT, PARENT, {c: b"right c", f: b"right f"})
    commit(storage, CHILD, LEFT, {a: b"child a", d: None})
    expected = {
        FINALIZED: base,
        PARENT: {**base, a: b"parent a", d: b"parent d"},
        LEFT: {a: b"parent a", c: b"", d: b"parent d", e: b"left e"},
        RIGHT: {**base, a: b"parent a", c: b"right c", d: b"parent d", f: b"right f"},
        CHILD: {a: b"child a", c: b"", e: b"left e"},
    }
    return storage, engine, expected


def test_switching_forks_and_historical_reads_keeps_the_selected_state(forked_state):
    storage, _, expected = forked_state
    for selected_hash in (CHILD, RIGHT, LEFT, PARENT, FINALIZED, CHILD):
        storage.select_block_hash(selected_hash)
        assert_root(storage, expected[selected_hash])
        for historical_hash in (RIGHT, FINALIZED, LEFT, CHILD):
            assert_retained_root(storage, historical_hash, expected[historical_hash])
        assert_root(storage, expected[selected_hash])


@pytest.mark.parametrize("mutation", ["engine", "alias", "transaction", "raw_dict"])
def test_external_base_writes_are_observed_with_overlays(forked_state, mutation):
    storage, engine, expected = forked_state
    a, b, c, _, _, _, g, _ = KEYS
    storage.select_block_hash(CHILD)
    assert_root(storage, expected[CHILD])
    changes = {a: b"new base a", b: b"new base b", c: None, g: b"new base g"}
    target = engine.namespace(b"state") if mutation == "alias" else storage.storage_engine
    if mutation == "transaction":
        with target.transaction() as tx:
            for key, value in changes.items():
                tx.delete(key) if value is None else tx.put(key, value)
    elif mutation == "raw_dict":
        for key, value in changes.items():
            if value is None:
                engine.storage.pop(b"state-" + key)
            else:
                engine.storage[b"state-" + key] = value
    else:
        for key, value in changes.items():
            target.delete(key) if value is None else target.put(key, value)

    updated_base = {a: b"new base a", b: b"new base b", g: b"new base g"}
    updated_child = {a: b"child a", KEYS[4]: b"left e", g: b"new base g"}
    assert_root(storage, updated_child)
    assert_retained_root(storage, FINALIZED, updated_base)
    assert_root(storage, updated_child)


@pytest.mark.parametrize("length", [0, 32, 33, 8192])
def test_mutating_a_stored_buffer_cannot_alias_the_previous_snapshot(length):
    value = bytearray(b"v" * length)
    engine = InMemoryStorageEngine({KEYS[0]: value, KEYS[1]: b"unchanged"})
    storage = StateStorage(engine)
    storage.set_finalized_block_hash(FINALIZED)
    first = storage.state_root()

    value[:] = b"w" * max(1, length)
    changed = reference_root(engine.as_dict())
    assert changed != first
    assert_root(storage, engine.as_dict())
    assert_retained_root(storage, FINALIZED, engine.as_dict())

    value[:] = b"v" * length
    assert storage.state_root() == first


@pytest.mark.parametrize("reset_overlay", [False, True])
def test_replacing_an_ancestor_overlay_updates_cached_descendant_views(forked_state, reset_overlay):
    storage, _, expected = forked_state
    for block_hash in (PARENT, LEFT, RIGHT, CHILD):
        assert_retained_root(storage, block_hash, expected[block_hash])
    storage.select_block_hash(PARENT)
    if reset_overlay:
        storage.set_block_hash(PARENT, FINALIZED)
    storage.put(KEYS[6], b"replacement")
    storage.commit()

    base = expected[FINALIZED]
    replacement_parent = {**base, KEYS[6]: b"replacement"}
    replacement_left = {**replacement_parent, KEYS[4]: b"left e"}
    replacement_left.pop(KEYS[1])
    replacement_right = {**replacement_parent, KEYS[2]: b"right c", KEYS[5]: b"right f"}
    replacement_child = {**replacement_left, KEYS[0]: b"child a"}
    for block_hash, items in (
        (PARENT, replacement_parent), (LEFT, replacement_left),
        (RIGHT, replacement_right), (CHILD, replacement_child),
    ):
        storage.select_block_hash(block_hash)
        assert_root(storage, items)
        assert_retained_root(storage, block_hash, items)


def test_rollback_observes_the_parent_and_drops_the_retained_overlay(forked_state):
    storage, _, expected = forked_state
    storage.select_block_hash(CHILD)
    assert_root(storage, expected[CHILD])
    storage.put(KEYS[7], b"pending")
    storage.rollback()

    # The legacy rollback operation keeps the selection but removes its writes.
    assert storage.block_hash == CHILD
    assert_root(storage, expected[LEFT])
    with pytest.raises(KeyError, match="unavailable"):
        storage.state_root_at(CHILD)
    assert_retained_root(storage, LEFT, expected[LEFT])


def test_discard_reselects_the_predecessor_after_a_warm_root(forked_state):
    storage, _, expected = forked_state
    storage.select_block_hash(CHILD)
    assert_root(storage, expected[CHILD])
    storage.put(KEYS[7], b"pending")
    storage.discard_candidate(CHILD, LEFT)

    assert storage.block_hash == LEFT
    assert storage.transaction == {}
    assert_root(storage, expected[LEFT])
    with pytest.raises(KeyError, match="unavailable"):
        storage.state_root_at(CHILD)


def test_finalization_preserves_descendants_and_prunes_the_other_fork(forked_state):
    storage, _, expected = forked_state
    for block_hash, items in expected.items():
        assert_retained_root(storage, block_hash, items)
    storage.select_block_hash(RIGHT)
    storage.finalize(PARENT)
    assert storage.block_hash == RIGHT
    assert storage.storage_engine.as_dict() == expected[PARENT]
    assert_root(storage, expected[RIGHT])
    for block_hash in (PARENT, LEFT, RIGHT, CHILD):
        assert_retained_root(storage, block_hash, expected[block_hash])

    storage.finalize(LEFT)
    assert storage.block_hash == LEFT
    assert storage.storage_engine.as_dict() == expected[LEFT]
    assert_root(storage, expected[LEFT])
    assert_retained_root(storage, CHILD, expected[CHILD])
    for pruned_hash in (FINALIZED, PARENT, RIGHT):
        with pytest.raises(KeyError, match="unavailable"):
            storage.state_root_at(pruned_hash)


def test_failed_finalization_keeps_the_previous_root_and_storage(forked_state, monkeypatch):
    storage, _, expected = forked_state
    storage.select_block_hash(CHILD)
    assert_root(storage, expected[CHILD])
    previous_changes = deepcopy(storage.change_sets)
    previous_parents = dict(storage.parents)
    transaction = storage.storage_engine.transaction

    @contextmanager
    def failing_transaction():
        with transaction() as tx:
            yield tx
            raise RuntimeError("simulated base write failure")

    with monkeypatch.context() as patch:
        patch.setattr(storage.storage_engine, "transaction", failing_transaction)
        with pytest.raises(RuntimeError, match="simulated base write failure"):
            storage.finalize(LEFT)

    assert storage.finalized_block_hash == FINALIZED
    assert storage.block_hash == CHILD
    assert storage.change_sets == previous_changes
    assert storage.parents == previous_parents
    assert storage.storage_engine.as_dict() == expected[FINALIZED]
    assert_root(storage, expected[CHILD])
    storage.finalize(LEFT)
    assert_root(storage, expected[CHILD])


@pytest.mark.parametrize("clear_before_reload", [False, True])
def test_clear_and_reload_can_reuse_hashes_with_independent_contents(forked_state, clear_before_reload):
    storage, engine, expected = forked_state
    assert_root(storage, expected[CHILD])
    if clear_before_reload:
        storage.clear(keep_ancestors=True)
    engine.storage.clear()
    replacement = {KEYS[6]: b"independent pre-state", KEYS[7]: b""}
    for key, value in replacement.items():
        engine.namespace(b"state").put(key, value)
    if not clear_before_reload:
        storage.clear()
    storage.set_finalized_block_hash(FINALIZED)
    assert_root(storage, replacement)
    assert_retained_root(storage, FINALIZED, replacement)
    commit(storage, CHILD, FINALIZED, {KEYS[6]: None})
    assert_root(storage, {KEYS[7]: b""})

    storage.clear()
    engine.storage.clear()
    assert storage.state_root() == bytes(32)


def test_pending_writes_reject_current_roots_but_allow_historical_roots(forked_state):
    storage, _, expected = forked_state
    storage.select_block_hash(CHILD)
    assert_root(storage, expected[CHILD])
    storage.put(KEYS[7], b"pending")

    for block_hash in (CHILD, LEFT, RIGHT, FINALIZED):
        assert_retained_root(storage, block_hash, expected[block_hash])
    with pytest.raises(ValueError, match="Pending transaction"):
        storage.state_root()
    assert storage.transaction == {KEYS[7]: b"pending"}
    storage.start_tx()
    assert_root(storage, expected[CHILD])


def test_warm_roots_do_not_hide_ancestry_cycles(forked_state):
    storage, _, expected = forked_state
    assert_root(storage, expected[CHILD])
    assert_retained_root(storage, CHILD, expected[CHILD])
    storage.parents[PARENT] = CHILD

    with pytest.raises(ValueError, match="Cycle detected"):
        storage.state_root()
    with pytest.raises(KeyError, match="cycle"):
        storage.state_root_at(CHILD)
    assert_retained_root(storage, FINALIZED, expected[FINALIZED])
    storage.parents[PARENT] = FINALIZED
    assert_root(storage, expected[CHILD])


@pytest.mark.parametrize("missing", ["overlay", "parent"])
def test_warm_historical_roots_still_validate_retained_ancestry(forked_state, missing):
    storage, _, expected = forked_state
    assert_retained_root(storage, CHILD, expected[CHILD])
    if missing == "overlay":
        storage.change_sets.pop(PARENT)
    else:
        storage.parents.pop(PARENT)
    with pytest.raises(KeyError, match="unavailable"):
        storage.state_root_at(CHILD)
    # The current view historically permits missing overlays/parent links.
    assert_root(storage, storage.as_dict())


@pytest.mark.parametrize("invalid_hash", [bytes(32), bytes(31), bytes(33), b"z" * 32])
def test_warm_historical_roots_do_not_accept_unavailable_hashes(forked_state, invalid_hash):
    storage, _, expected = forked_state
    assert_root(storage, expected[CHILD])
    with pytest.raises(KeyError):
        storage.state_root_at(invalid_hash)
    assert_root(storage, expected[CHILD])


def test_legacy_short_keys_keep_the_existing_state_root_behavior():
    engine = InMemoryStorageEngine({b"timeslot": b"0", b"nochange": b"test"})
    storage = StateStorage(engine)
    assert_root(storage, engine.as_dict())
    engine.put(b"timeslot", b"1")
    assert_root(storage, engine.as_dict())
    engine.delete(b"nochange")
    assert_root(storage, engine.as_dict())


@pytest.mark.parametrize("hook", ["_leaf", "_branch", "_bit", "merkle", "root", "hash", "type"])
def test_warm_roots_preserve_custom_trie_hooks_and_recover_afterward(monkeypatch, hook):
    engine = InMemoryStorageEngine({KEYS[0]: b"first", KEYS[1]: b"second" * 8})
    storage = StateStorage(engine)
    storage.set_finalized_block_hash(FINALIZED)
    ordinary_root = storage.state_root()
    original_hash = merkle.blake2b_256_hash
    legacy_type = PatriciaMerkleTrie

    with monkeypatch.context() as patch:
        if hook == "hash":
            patch.setattr(merkle, "blake2b_256_hash", lambda data: original_hash(b"custom" + data))
        elif hook == "type":
            original_leaf = PatriciaMerkleTrie._leaf

            class CustomTrie(PatriciaMerkleTrie):
                @staticmethod
                def _leaf(key, value):
                    return b"custom" + original_leaf(key, value)

            legacy_type = CustomTrie
            patch.setattr(state_storage_module, "PatriciaMerkleTrie", CustomTrie)
        else:
            original = getattr(PatriciaMerkleTrie, hook)
            if hook == "_bit":
                replacement = staticmethod(lambda key, index: not original(key, index))
            elif hook.startswith("_"):
                replacement = staticmethod(lambda *args: b"custom" + original(*args))
            else:
                replacement = lambda *args, **kwargs: original_hash(b"custom" + original(*args, **kwargs))
            patch.setattr(PatriciaMerkleTrie, hook, replacement)

        expected = legacy_type(list(engine.as_dict().items())).root()
        assert expected != ordinary_root
        assert storage.state_root() == expected
        assert storage.state_root_at(FINALIZED) == expected
        engine.put(KEYS[0], b"changed while customized")
        expected = legacy_type(list(engine.as_dict().items())).root()
        assert storage.state_root() == expected

    assert_root(storage, engine.as_dict())
    assert_retained_root(storage, FINALIZED, engine.as_dict())


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("key_length", [31, 32])
def test_malformed_key_prefixes_preserve_legacy_errors_without_poisoning_roots(warm, key_length):
    original, collision = bytes(key_length), bytes(63 - key_length)
    engine = InMemoryStorageEngine({original: b"original", KEYS[1]: b"other"})
    storage = StateStorage(engine)
    storage.set_finalized_block_hash(FINALIZED)
    expected = reference_root(engine.as_dict())
    if warm:
        assert storage.state_root() == expected
    engine.put(collision, b"malformed")

    with pytest.raises(IndexError):
        PatriciaMerkleTrie(list(engine.as_dict().items())).root()
    with pytest.raises(IndexError):
        storage.state_root()
    with pytest.raises(IndexError):
        storage.state_root_at(FINALIZED)

    engine.delete(collision)
    assert storage.state_root() == expected
    engine.put(original, b"recovered and changed")
    assert_root(storage, engine.as_dict())
