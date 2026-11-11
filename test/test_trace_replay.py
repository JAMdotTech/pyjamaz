import asyncio

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.exceptions import (
    BlockValidationError, BlockValidationErrorCode, StateTransitionError,
)
from pyjamaz.graypaper_constants import COMMON_ERA
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.models.state import JamState
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.storage import InMemoryStorageEngine


@pytest.fixture
def replay_app(monkeypatch):
    app = PyjamazApp(AppConfig(
        ring_data=b"", storage_engine=InMemoryStorageEngine(), common_era=COMMON_ERA,
    ))
    app.working_state = JamState.create_genesis_state()
    asyncio.run(app.store_jam_state())
    state = StateDump(app.state_storage.state_root(), app.state_db.as_list())

    async def initialize_app(**kwargs):
        return app

    async def unchanged_state(block, produce=False):
        # Synthetic headers have no valid seal. Keep real import/rollback,
        # storage, ancestry and codecs, replacing only the consensus transition.
        return None

    monkeypatch.setattr(cli, "initialize_app", initialize_app)
    monkeypatch.setattr(cli, "setup_logging", lambda *args: None)
    monkeypatch.setattr(cli.settings, "SOLO_MODE", False)
    monkeypatch.setattr(cli.settings, "SKIP_TIMESLOT_WALL_CLOCK_CHECK", False)
    monkeypatch.setattr(app, "state_transition", unchanged_state)
    return app, state


def header_at(slot, parent=None, state_root=bytes(32)):
    header = Header.default()
    header.timeslot = slot
    header.parent = parent.hash if parent is not None else bytes(32)
    header.parent_state_root = state_root
    return header


def write_genesis(folder, state):
    header = header_at(0)
    (folder / "genesis.bin").write_bytes(TraceGenesis(header, state).to_jam_bytes().to_bytes())
    return header


def write_trace(folder, name, header, pre_state, post_state=None):
    trace = Trace(pre_state, Block(header, Extrinsic.default()), post_state or pre_state)
    (folder / name).write_bytes(trace.to_jam_bytes().to_bytes())


def replay(folder):
    return asyncio.run(CliRunner().invoke(cli.main, ["traces", str(folder)]))


def test_replay_uses_genesis_and_actual_branch_ancestry(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    genesis = write_genesis(tmp_path, state)
    first = header_at(7, genesis, state.state_root)
    sibling = header_at(13, genesis, state.state_root)
    child = header_at(20, first, state.state_root)
    for name, header in [("001.bin", first), ("002.bin", sibling), ("003.bin", child)]:
        write_trace(tmp_path, name, header, state)
    observed_ancestry = {}

    async def inspect_ancestry(block, produce=False):
        observed_ancestry[block.header.hash] = {
            ancestor.hash: ancestor.to_jam_bytes().to_bytes()
            for ancestor in app.state_storage.ancestors.values()
        }

    monkeypatch.setattr(app, "state_transition", inspect_ancestry)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    for block, ancestors in [
        (first, [genesis, first]),
        (sibling, [genesis, sibling]),
        (child, [genesis, first, child]),
    ]:
        assert observed_ancestry[block.hash] == {
            ancestor.hash: ancestor.to_jam_bytes().to_bytes() for ancestor in ancestors
        }
    assert app.retrieve_block_header(genesis.hash) == genesis
    assert app.retrieve_block_header(first.hash).timeslot == 7


def test_replay_missing_parent_is_an_error(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    missing_parent = header_at(0)
    write_trace(tmp_path, "001.bin", header_at(7, missing_parent, state.state_root), state)
    imported = []

    async def record_import(block, produce=False):
        imported.append(block.header.hash)

    monkeypatch.setattr(app, "state_transition", record_import)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "missing its parent header" in result.output
    assert imported == []


def test_replay_pre_state_root_mismatch_is_an_error(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    genesis = write_genesis(tmp_path, state)
    invalid_pre_state = StateDump(b"!" * 32, state.keyvals)
    write_trace(tmp_path, "001.bin", header_at(7, genesis, invalid_pre_state.state_root), invalid_pre_state)
    imported = []

    async def record_import(block, produce=False):
        imported.append(block.header.hash)

    monkeypatch.setattr(app, "state_transition", record_import)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "Pre-state root mismatch" in result.output
    assert imported == []


def test_replay_post_state_root_mismatch_is_an_error(tmp_path, replay_app):
    _, state = replay_app
    genesis = write_genesis(tmp_path, state)
    invalid_post_state = StateDump(b"!" * 32, state.keyvals)
    write_trace(tmp_path, "001.bin", header_at(7, genesis, state.state_root), state, invalid_post_state)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "1 trace state-root mismatch" in result.output


def test_replay_pre_state_validation_does_not_reuse_cached_state(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    genesis = write_genesis(tmp_path, state)
    first = header_at(7, genesis, state.state_root)
    child = header_at(20, first, state.state_root)
    write_trace(tmp_path, "001.bin", first, state)
    # The claimed root matches the previously loaded state, but these keyvals
    # do not. The new dump must be checked against its own trie.
    corrupt_state = StateDump(state.state_root, state.keyvals + [(b"\xfe" * 31, b"unexpected")])
    write_trace(tmp_path, "002.bin", child, corrupt_state)
    imported = []

    async def record_import(block, produce=False):
        imported.append(block.header.hash)

    monkeypatch.setattr(app, "state_transition", record_import)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "Pre-state root mismatch" in result.output
    assert "002.bin" in result.output
    assert imported == [first.hash]


@pytest.mark.parametrize("error_type,error_code", [
    (BlockValidationError, BlockValidationErrorCode.invalid_seal_key),
    (StateTransitionError, SafroleErrorCode.bad_ticket_attempt),
])
def test_replay_expected_rejection_uses_restored_state(tmp_path, replay_app, monkeypatch, error_type, error_code):
    app, state = replay_app
    genesis = write_genesis(tmp_path, state)
    rejected = header_at(7, genesis, state.state_root)
    write_trace(tmp_path, "001.bin", rejected, state)
    rejected_imports = []

    async def reject_after_write(block, produce=False):
        rejected_imports.append(block.header.hash)
        app.working_state.timeslot.number = block.header.timeslot
        await app.components.timeslot.store_state(app.working_state.timeslot)
        raise error_type(error_code)

    monkeypatch.setattr(app, "state_transition", reject_after_write)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert rejected_imports == [rejected.hash]
    assert app.working_state.timeslot.number == 0
    assert app.working_state.state_root == state.state_root
    assert app.state_storage.state_root() == state.state_root
    assert app.state_storage.transaction == {}
    assert rejected.hash not in app.state_storage.change_sets


def test_replay_rejects_earlier_candidate_slot_and_continues(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    genesis = write_genesis(tmp_path, state)
    parent = header_at(7, genesis, state.state_root)
    rejected = header_at(6, parent, state.state_root)
    sibling = header_at(8, parent, state.state_root)
    for name, header in [('001.bin', parent), ('002.bin', rejected), ('003.bin', sibling)]:
        write_trace(tmp_path, name, header, state)
    imported = []

    async def validate(block, produce=False):
        imported.append(block.header.timeslot)
        if block.header.timeslot == 6:
            raise BlockValidationError(BlockValidationErrorCode.bad_slot)

    monkeypatch.setattr(app, 'state_transition', validate)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert imported == [7, 6, 8]
    assert app.working_state.state_root == state.state_root
