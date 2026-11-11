import asyncio

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.graypaper_constants import COMMON_ERA
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.models.state import JamState
from pyjamaz.storage import InMemoryStorageEngine


@pytest.fixture
def replay_app(monkeypatch):
    app = PyjamazApp(AppConfig(
        ring_data=b'', storage_engine=InMemoryStorageEngine(), common_era=COMMON_ERA,
    ))
    app.working_state = JamState.create_genesis_state()
    asyncio.run(app.store_jam_state())
    state = StateDump(app.state_storage.state_root(), app.state_db.as_list())
    imported = []

    async def initialize_app(**kwargs):
        return app

    async def transition(block, produce=False):
        imported.append((block.header.hash, app.app_context.skip_lookup_anchor_ancestry.get()))

    monkeypatch.setattr(cli, 'initialize_app', initialize_app)
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)
    monkeypatch.setattr(cli.settings, 'SOLO_MODE', False)
    monkeypatch.setattr(cli.settings, 'SKIP_TIMESLOT_WALL_CLOCK_CHECK', False)
    monkeypatch.setattr(app, 'state_transition', transition)
    return app, state, imported


def write_short_trace(folder, state, *, corrupt_checkpoint=False):
    checkpoint = Header.default()
    checkpoint.timeslot = 7
    checkpoint.parent = b'p' * 32
    checkpoint.parent_state_root = state.state_root
    post_state = StateDump(b'!' * 32, state.keyvals) if corrupt_checkpoint else state
    (folder / '00000001.bin').write_bytes(Trace(
        state, Block(checkpoint, Extrinsic.default()), post_state,
    ).to_jam_bytes().to_bytes())
    child = Header.default()
    child.timeslot = 9
    child.parent = checkpoint.hash
    child.parent_state_root = state.state_root
    (folder / '00000002.bin').write_bytes(Trace(
        state, Block(child, Extrinsic.default()), state,
    ).to_jam_bytes().to_bytes())
    return checkpoint, child


def replay(folder, *options):
    return asyncio.run(CliRunner().invoke(cli.main, ['traces', str(folder), *options]))


@pytest.mark.parametrize('strict', [False, True])
def test_short_trace_uses_first_record_as_checkpoint(tmp_path, replay_app, strict):
    app, state, imported = replay_app
    checkpoint, child = write_short_trace(tmp_path, state)
    options = ['--prompt', '--strict-ancestry'] if strict else ['--prompt']

    result = replay(tmp_path, *options)

    assert result.exit_code == 0, result.output
    assert imported == [(child.hash, not strict)]
    assert app.retrieve_block_header(checkpoint.hash).to_jam_bytes().to_bytes() == checkpoint.to_jam_bytes().to_bytes()
    assert not app.app_context.skip_lookup_anchor_ancestry.get()


def test_short_trace_rejects_corrupt_checkpoint_state(tmp_path, replay_app):
    _, state, imported = replay_app
    write_short_trace(tmp_path, state, corrupt_checkpoint=True)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert 'Checkpoint state root mismatch' in result.output
    assert imported == []


def test_checkpoint_alone_is_not_a_successful_replay(tmp_path, replay_app):
    _, state, imported = replay_app
    write_short_trace(tmp_path, state)
    (tmp_path / '00000002.bin').unlink()

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert 'no subsequent block' in result.output
    assert imported == []


def test_checkpoint_policy_does_not_leak_to_genesis_corpus(tmp_path, replay_app):
    app, state, imported = replay_app
    shortened, complete = tmp_path / 'a-shortened', tmp_path / 'b-complete'
    shortened.mkdir()
    complete.mkdir()
    _, short_child = write_short_trace(shortened, state)
    genesis = Header.default()
    (complete / 'genesis.bin').write_bytes(TraceGenesis(genesis, state).to_jam_bytes().to_bytes())
    child = Header.default()
    child.timeslot = 1
    child.parent = genesis.hash
    child.parent_state_root = state.state_root
    (complete / '00000001.bin').write_bytes(Trace(
        state, Block(child, Extrinsic.default()), state,
    ).to_jam_bytes().to_bytes())

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert imported == [(short_child.hash, True), (child.hash, False)]
    assert not app.app_context.skip_lookup_anchor_ancestry.get()


def test_checkpoint_policy_is_restored_after_unexpected_failure(tmp_path, replay_app, monkeypatch):
    app, state, _ = replay_app
    write_short_trace(tmp_path, state)

    async def fail(block, produce=False):
        assert app.app_context.skip_lookup_anchor_ancestry.get()
        raise RuntimeError('unexpected import failure')

    monkeypatch.setattr(app, 'state_transition', fail)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert not app.app_context.skip_lookup_anchor_ancestry.get()
