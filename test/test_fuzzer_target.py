import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from pyjamaz.app import PyjamazApp
from pyjamaz.exceptions import BlockValidationError, StateTransitionError
from pyjamaz.fuzzer.v1.target import FuzzerTarget
from pyjamaz.fuzzer.v1.types import AncestryItem, FuzzerMessage, InitializeMessage
from pyjamaz.models.block import AncestorReference, Block, Extrinsic, Header
from pyjamaz.models.context import AppContext
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


COUNTER = bytes([1]) * 31
REMOVED = bytes([2]) * 31
ADDED = bytes([3]) * 31


@pytest.fixture
def target(tmp_path):
    # Exercise the real application import/rollback boundary with a small
    # deterministic STF, without signatures, PVM execution, or a disk database.
    engine = InMemoryStorageEngine()
    app = PyjamazApp.__new__(PyjamazApp)
    app.state_db = engine.namespace(b"state")
    app.block_db = engine.namespace(b"block")
    app.state_storage = StateStorage(app.state_db)
    app.app_context = AppContext(state_storage=app.state_storage)
    app.pubsub = None
    app.working_state = None
    app.retrieve_jam_state = lambda: SimpleNamespace(state_root=app.state_storage.state_root())
    app.import_block = app._import_block

    async def transition(block, produce=False):
        await app.initialize(block.header)
        value = int.from_bytes(app.state_storage.get(COUNTER), "little")
        value += block.header.author_index
        app.state_storage.put(COUNTER, value.to_bytes(4, "little"))
        app.state_storage.commit()
        app.working_state = app.retrieve_jam_state()

    app.state_transition = transition
    return FuzzerTarget(str(tmp_path / "target.sock"), app)


async def initialize(target, *, header=None, ancestry=None):
    header = header or Header.default()
    response = await target.msg_initialize(FuzzerMessage(initialize=InitializeMessage(
        header=header,
        state=[(COUNTER, (10).to_bytes(4, "little")), (REMOVED, b"old")],
        ancestry=ancestry or [],
    )))
    assert response.error is None
    assert response.state_root == target.app.state_storage.state_root()
    return header


def child(parent, slot, increment=1):
    header = Header.default()
    header.parent = parent.hash
    header.timeslot = slot
    header.author_index = increment
    return Block(header=header, extrinsic=Extrinsic.default())


def test_get_state_returns_selected_overlay_including_deletions(target):
    async def run():
        genesis = await initialize(target)
        block = child(genesis, 1)
        storage = target.app.state_storage
        storage.set_header(block.header)
        storage.put(COUNTER, (11).to_bytes(4, "little"))
        storage.delete(REMOVED)
        storage.put(ADDED, b"new")
        storage.commit()

        response = target.msg_get_state()
        assert dict(response.state) == {COUNTER: (11).to_bytes(4, "little"), ADDED: b"new"}
        requested = await target._dispatch(FuzzerMessage(get_state=block.header.hash))
        assert requested.state == response.state
        assert dict(target.app.state_db.as_list()) == {
            COUNTER: (10).to_bytes(4, "little"), REMOVED: b"old"
        }

    asyncio.run(run())


def test_get_state_returns_requested_retained_branch_without_selecting_it(target):
    async def run():
        genesis = await initialize(target)
        parent = child(genesis, 1)
        left = child(parent.header, 2, increment=2)
        right = child(parent.header, 2, increment=3)
        left_child = child(left.header, 3, increment=4)

        for block in (parent, left, right, left_child):
            response = await target.msg_import_block(FuzzerMessage(import_block=block))
            assert response.error is None

        storage = target.app.state_storage
        selected_state = target.app.working_state
        selected_root = storage.state_root()
        for header, value in ((parent.header, 11), (left.header, 13),
                              (right.header, 14), (left_child.header, 17), (genesis, 10)):
            response = await target._dispatch(FuzzerMessage(get_state=header.hash))
            assert dict(response.state) == {
                COUNTER: value.to_bytes(4, "little"), REMOVED: b"old"
            }
            assert storage.block_hash == left_child.header.hash
            assert storage.state_root() == selected_root
            assert target.app.working_state is selected_state
        assert storage.finalized_block_hash == genesis.hash

    asyncio.run(run())


@pytest.mark.parametrize("known_ancestor", [False, True])
def test_get_state_rejects_unavailable_state_without_returning_selected(target, known_ancestor):
    async def run():
        missing_hash = bytes([29]) * 32
        genesis_header = Header.default()
        ancestry = []
        if known_ancestor:
            genesis_header.parent = missing_hash
            genesis_header.timeslot = 1
            ancestry = [AncestryItem(slot=0, header_hash=missing_hash)]
        genesis = await initialize(target, header=genesis_header, ancestry=ancestry)
        block = child(genesis, 2)
        response = await target.msg_import_block(FuzzerMessage(import_block=block))
        assert response.error is None
        storage = target.app.state_storage
        selected_state = target.app.working_state
        selected_root = storage.state_root()

        with pytest.raises(KeyError, match="state for block hash is unavailable"):
            await target._dispatch(FuzzerMessage(get_state=missing_hash))

        assert storage.block_hash == block.header.hash
        assert storage.state_root() == selected_root
        assert target.app.working_state is selected_state

    asyncio.run(run())


def test_initialize_preserves_supplied_ancestry_slots_without_inventing_commitments(target):
    async def run():
        older_hash, newer_hash = bytes([7]) * 32, bytes([17]) * 32
        header = Header.default()
        header.parent = newer_hash
        header.timeslot = 22
        await initialize(target, header=header, ancestry=[
            AncestryItem(slot=17, header_hash=newer_hash),
            AncestryItem(slot=7, header_hash=older_hash),
        ])

        ancestors = target.app.state_storage.ancestors
        assert ancestors[header.hash] == header
        assert isinstance(ancestors[newer_hash], AncestorReference)
        assert ancestors[newer_hash].timeslot == 17
        assert ancestors[newer_hash].parent == older_hash
        assert ancestors[older_hash].timeslot == 7
        assert ancestors[older_hash].parent == bytes(32)
        assert ancestors[newer_hash].parent_state_root is None
        assert ancestors[older_hash].parent_state_root is None

    asyncio.run(run())


def test_import_retains_same_slot_siblings_and_their_independent_state(target):
    async def run():
        genesis = await initialize(target)
        parent = child(genesis, 1)
        left = child(parent.header, 2, increment=2)
        right = child(parent.header, 2, increment=3)
        left_child = child(left.header, 3, increment=4)

        for block in (parent, left, right, left_child):
            response = await target.msg_import_block(FuzzerMessage(import_block=block))
            assert response.error is None
            assert response.state_root == target.app.state_storage.state_root()

        storage = target.app.state_storage
        assert storage.finalized_block_hash == genesis.hash
        assert genesis.hash in storage.ancestors
        for block, value in ((parent, 11), (left, 13), (right, 14), (left_child, 17)):
            assert storage.has_state_at(block.header.hash)
            assert storage.as_dict_at(block.header.hash)[COUNTER] == value.to_bytes(4, "little")
        assert target.app.state_db.get(COUNTER) == (10).to_bytes(4, "little")

    asyncio.run(run())


@pytest.mark.parametrize("error_type", [BlockValidationError, StateTransitionError])
def test_rejected_import_leaves_application_restored_parent_intact(target, error_type):
    async def run():
        genesis = await initialize(target)
        parent = child(genesis, 1)
        response = await target.msg_import_block(FuzzerMessage(import_block=parent))
        assert response.error is None
        storage = target.app.state_storage
        parent_changes = deepcopy(storage.change_sets[parent.header.hash])
        parent_root = storage.state_root()
        rejected = child(parent.header, 2, increment=2)
        ordinary_transition = target.app.state_transition

        async def reject(block, produce=False):
            await target.app.initialize(block.header)
            storage.put(COUNTER, b"uncommitted")
            target.app.app_context.post_commit_signals.append(object())
            raise error_type("rejected candidate")

        target.app.state_transition = reject
        response = await target.msg_import_block(FuzzerMessage(import_block=rejected))

        assert "rejected candidate" in response.error
        assert storage.block_hash == parent.header.hash
        assert storage.change_sets[parent.header.hash] == parent_changes
        assert storage.state_root() == parent_root
        assert target.app.working_state.state_root == parent_root
        assert rejected.header.hash not in storage.change_sets
        assert rejected.header.hash not in storage.parents
        assert rejected.header.hash not in storage.ancestors
        assert storage.transaction == {}
        assert target.app.app_context.post_commit_signals == []

        # A second adapter rollback would discard the restored parent's overlay
        # and prevent this sibling from executing against the original state.
        target.app.state_transition = ordinary_transition
        sibling = child(parent.header, 2, increment=3)
        response = await target.msg_import_block(FuzzerMessage(import_block=sibling))
        assert response.error is None
        assert storage.get(COUNTER) == (14).to_bytes(4, "little")
        assert storage.change_sets[parent.header.hash] == parent_changes

    asyncio.run(run())
