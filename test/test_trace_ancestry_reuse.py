import asyncio

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.graypaper_constants import COMMON_ERA
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.models.state import JamState
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


@pytest.fixture
def replay_app(monkeypatch):
    app = PyjamazApp(AppConfig(
        ring_data=b"", storage_engine=InMemoryStorageEngine(), common_era=COMMON_ERA,
    ))
    app.working_state = JamState.create_genesis_state()
    asyncio.run(app.store_jam_state())
    state = StateDump(app.state_storage.state_root(), app.state_db.as_list())

    async def initialize_app(**_kwargs):
        return app

    monkeypatch.setattr(cli, "initialize_app", initialize_app)
    monkeypatch.setattr(cli, "setup_logging", lambda *_args: None)
    monkeypatch.setattr(cli.settings, "SOLO_MODE", False)
    monkeypatch.setattr(cli.settings, "SKIP_TIMESLOT_WALL_CLOCK_CHECK", False)
    return app, state


def write_chain(folder, state, count):
    parent = Header.default()
    (folder / "genesis.bin").write_bytes(TraceGenesis(parent, state).to_jam_bytes().to_bytes())
    headers = [parent]
    for slot in range(1, count + 1):
        header = Header.default()
        header.parent, header.timeslot = parent.hash, slot
        header.parent_state_root = state.state_root
        (folder / f"{slot:03}.bin").write_bytes(Trace(
            state, Block(header, Extrinsic.default()), state,
        ).to_jam_bytes().to_bytes())
        headers.append(header)
        parent = header
    return headers


def replay(folder):
    return asyncio.run(CliRunner().invoke(cli.main, ["traces", str(folder)]))


def test_linear_replay_reuses_headers_without_retaining_state(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    headers = write_chain(tmp_path, state, 12)
    checked_headers = []
    stored_headers = []
    resolve = cli._trace_ancestor_headers
    store = app.store_block_header

    def resolve_ancestry(block, known):
        checked_headers.append(len(known))
        return resolve(block, known)

    async def store_header(header):
        stored_headers.append(header.hash)
        await store(header)

    async def inspect(block, produce=False):
        slot = block.header.timeslot
        assert set(app.state_storage.ancestors) == {header.hash for header in headers[:slot + 1]}
        assert len(app.state_storage.parents) <= 2
        assert set(app.state_storage.change_sets) == {block.header.hash}
        assert app.state_storage.transaction == {}

    monkeypatch.setattr(cli, "_trace_ancestor_headers", resolve_ancestry)
    monkeypatch.setattr(app, "store_block_header", store_header)
    monkeypatch.setattr(app, "state_transition", inspect)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert checked_headers == [1] * 12
    assert len(stored_headers) <= 3 * 12


def test_rejected_parent_rebuilds_ancestry_for_next_input(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    headers = write_chain(tmp_path, state, 2)
    checked_headers = []
    resolve = cli._trace_ancestor_headers

    def resolve_ancestry(block, known):
        checked_headers.append(len(known))
        return resolve(block, known)

    async def reject_first(block, produce=False):
        if block.header.timeslot == 1:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_attempt)
        assert set(app.state_storage.ancestors) == {header.hash for header in headers}

    monkeypatch.setattr(cli, "_trace_ancestor_headers", resolve_ancestry)
    monkeypatch.setattr(app, "state_transition", reject_first)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert checked_headers == [1, 2]


def test_reused_parent_still_checks_canonical_identity(tmp_path, replay_app, monkeypatch):
    app, state = replay_app
    write_chain(tmp_path, state, 2)

    async def mutate_header(block, produce=False):
        block.header.entropy_source = b"changed".ljust(96, b"!")

    monkeypatch.setattr(app, "state_transition", mutate_header)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "does not match its indexed hash" in str(result.exception)


def test_clear_can_retain_headers_without_retaining_executable_state():
    engine = InMemoryStorageEngine()
    engine.put(b"key", b"base")
    storage = StateStorage(engine)
    parent, child = Header.default(), Header.default()
    child.parent, child.timeslot = parent.hash, 1
    storage.set_finalized_header(parent)
    storage.add_ancestor(child)
    storage.set_block_hash(child.hash, parent.hash)
    storage.put(b"key", b"committed overlay")
    storage.commit()
    storage.put(b"key", b"pending overlay")
    ancestors = storage.ancestors

    storage.clear(keep_ancestors=True)

    assert storage.ancestors is ancestors
    assert set(storage.ancestors) == {parent.hash, child.hash}
    assert storage.get(b"key") == b"base"
    assert storage.change_sets == storage.parents == storage.transaction == {}
    assert storage.block_hash is storage.finalized_block_hash is None
    storage.clear()
    assert storage.ancestors == {}
