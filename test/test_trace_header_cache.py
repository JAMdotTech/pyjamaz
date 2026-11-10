import asyncio
from collections import Counter
from dataclasses import fields

import pytest
from asyncclick.testing import CliRunner
from jamcodec.base import JamBytes

from pyjamaz import cli
from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.graypaper_constants import COMMON_ERA, EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, EpochMark, EpochMarkValidatorKeys, Extrinsic, Header
from pyjamaz.models.common import TicketBody
from pyjamaz.models.state import JamState
from pyjamaz.storage import InMemoryStorageEngine


def plain_header(header):
    return Header(**{field.name: getattr(header, field.name) for field in fields(Header)})


def marked_header():
    header = Header.default()
    header.epoch_marker = EpochMark(
        entropy=b"e" * 32,
        tickets_entropy=b"t" * 32,
        validators=[EpochMarkValidatorKeys(b"b" * 32, b"v" * 32) for _ in range(VALIDATOR_COUNT)],
    )
    header.tickets_marker = [TicketBody(b"i" * 32, 0) for _ in range(EPOCH_TIMESLOTS)]
    header.offenders_marker = [b"o" * 32]
    return header


def test_trace_header_caches_canonical_encoding_and_ignores_input_hash(monkeypatch):
    source = marked_header()
    canonical = source.to_jam_bytes().to_bytes()
    source.hash = b"stale input override".ljust(32, b"!")
    header = cli._TraceHeader.from_header(source)
    serializations = []
    original = Header.to_jam_bytes

    def serialize(self):
        serializations.append(self)
        return original(self)

    monkeypatch.setattr(Header, "to_jam_bytes", serialize)
    for _ in range(3):
        assert header.to_jam_bytes().to_bytes() == canonical
        assert header.hash == blake2b_256_hash(canonical)
        assert header.get_unsigned_payload() == canonical[:-96]
    header._author_bandersnatch_key = b"derived author key".ljust(32, b"!")
    assert header.hash == blake2b_256_hash(canonical)
    assert serializations == [header]


@pytest.mark.parametrize("mutate", [
    lambda header: setattr(header, "parent", b"p" * 32),
    lambda header: setattr(header, "parent_state_root", b"r" * 32),
    lambda header: setattr(header, "extrinsic_hash", b"x" * 32),
    lambda header: setattr(header, "timeslot", header.timeslot + 1),
    lambda header: setattr(header, "author_index", header.author_index + 1),
    lambda header: setattr(header, "entropy_source", b"s" * 96),
    lambda header: setattr(header, "seal", b"z" * 96),
    lambda header: setattr(header.epoch_marker, "entropy", b"n" * 32),
    lambda header: setattr(header.epoch_marker, "tickets_entropy", b"n" * 32),
    lambda header: setattr(header.epoch_marker.validators[0], "ed25519", b"n" * 32),
    lambda header: setattr(header.tickets_marker[0], "attempt", 1),
    lambda header: header.tickets_marker.__setitem__(0, TicketBody(b"n" * 32, 0)),
    lambda header: header.offenders_marker.append(b"n" * 32),
    lambda header: header.offenders_marker.__setitem__(0, b"n" * 32),
    lambda header: setattr(header, "epoch_marker", None),
    lambda header: setattr(header, "tickets_marker", None),
])
def test_trace_header_invalidates_cache_on_codec_field_mutation(mutate):
    header = cli._TraceHeader.from_header(marked_header())
    before_bytes = header.to_jam_bytes().to_bytes()
    before_hash = header.hash

    mutate(header)

    canonical = plain_header(header).to_jam_bytes().to_bytes()
    assert canonical != before_bytes
    assert header.to_jam_bytes().to_bytes() == canonical
    assert header.hash == blake2b_256_hash(canonical) != before_hash


@pytest.mark.parametrize("mutate", [
    lambda header: setattr(header, "timeslot", False),
    lambda header: setattr(header, "author_index", 0.0),
    lambda header: setattr(header.tickets_marker[0], "attempt", False),
    lambda header: setattr(header.tickets_marker[0], "attempt", 0.0),
])
def test_trace_header_does_not_hide_invalid_equal_valued_types(mutate):
    header = cli._TraceHeader.from_header(marked_header())
    header.to_jam_bytes()
    mutate(header)

    with pytest.raises(ValueError, match="integer"):
        plain_header(header).to_jam_bytes()
    with pytest.raises(ValueError, match="integer"):
        header.to_jam_bytes()
    with pytest.raises(ValueError, match="integer"):
        header.hash


def test_trace_header_jam_bytes_have_independent_cursors_and_buffers():
    header = cli._TraceHeader.from_header(marked_header())
    first = header.to_jam_bytes()
    canonical = first.to_bytes()
    first.get_next_bytes(10)
    first.data[0] ^= 0xFF

    second = header.to_jam_bytes()

    assert second.offset == 0
    assert second.to_bytes() == canonical
    assert Header.from_jam_bytes(second).to_jam_bytes().to_bytes() == canonical
    assert first.offset == 10


def test_trace_header_does_not_change_shared_header_codec_or_runtime_mutability():
    source = Header.default()
    codec = Header.to_codec_def()
    header = cli._TraceHeader.from_header(source)
    header.hash
    assert cli._TraceHeader.to_codec_def() is codec
    assert codec._deserialize_type is Header
    block_bytes = Block(header, Extrinsic.default()).to_jam_bytes()
    assert type(Block.from_jam_bytes(block_bytes).header) is Header

    before_hash = source.hash
    source.timeslot += 1
    assert source.hash != before_hash
    assert source.hash == blake2b_256_hash(source.to_jam_bytes().to_bytes())


def test_cached_ancestry_still_rejects_changed_header_identity():
    parent = cli._TraceHeader.from_header(Header.default())
    indexed_hash = parent.hash
    child = Header.default()
    child.parent = indexed_hash
    child.timeslot = parent.timeslot + 2
    parent.timeslot += 1

    with pytest.raises(ValueError, match="does not match its indexed hash"):
        cli._trace_ancestor_headers(Block(child, Extrinsic.default()), {indexed_hash: parent})


def test_cached_ancestry_still_rejects_nonincreasing_slots():
    grandparent = cli._TraceHeader.from_header(Header.default())
    grandparent.timeslot = 3
    parent = cli._TraceHeader.from_header(Header.default())
    parent.parent, parent.timeslot = grandparent.hash, 3
    child = Header.default()
    child.parent = parent.hash
    child.timeslot = 4

    with pytest.raises(ValueError, match="timeslots are not strictly increasing"):
        cli._trace_ancestor_headers(
            Block(child, Extrinsic.default()), {parent.hash: parent, grandparent.hash: grandparent},
        )


@pytest.mark.parametrize("candidate_slot", [2, 3])
def test_candidate_slot_is_left_to_block_validation(candidate_slot):
    parent = cli._TraceHeader.from_header(Header.default())
    parent.timeslot = 3
    child = Header.default()
    child.parent, child.timeslot = parent.hash, candidate_slot

    assert cli._trace_ancestor_headers(Block(child, Extrinsic.default()), {parent.hash: parent}) == [parent]


def test_trace_ancestry_still_rejects_cycles():
    first, second, child = Header.default(), Header.default(), Header.default()
    first.hash, second.hash = b"a" * 32, b"b" * 32
    first.parent, second.parent, child.parent = second.hash, first.hash, first.hash
    first.timeslot, second.timeslot, child.timeslot = 2, 1, 3

    with pytest.raises(ValueError, match="cycle in trace header ancestry"):
        cli._trace_ancestor_headers(
            Block(child, Extrinsic.default()), {first.hash: first, second.hash: second},
        )


@pytest.fixture
def cache_replay_app(monkeypatch):
    app = PyjamazApp(AppConfig(
        ring_data=b"", storage_engine=InMemoryStorageEngine(), common_era=COMMON_ERA,
    ))
    app.working_state = JamState.create_genesis_state()
    asyncio.run(app.store_jam_state())
    state = StateDump(app.state_storage.state_root(), app.state_db.as_list())

    async def initialize_app(**kwargs):
        return app

    async def unchanged_state(block, produce=False):
        # Keep import/rollback, ancestry, persistence and state-root validation;
        # these synthetic headers do not carry valid consensus seals.
        return None

    monkeypatch.setattr(cli, "initialize_app", initialize_app)
    monkeypatch.setattr(cli, "setup_logging", lambda *args: None)
    monkeypatch.setattr(cli.settings, "SOLO_MODE", False)
    monkeypatch.setattr(cli.settings, "SKIP_TIMESLOT_WALL_CLOCK_CHECK", False)
    monkeypatch.setattr(app, "state_transition", unchanged_state)
    return app, state


def write_header_trace(folder, filename, state, parent, slot, seal=None):
    header = Header.default()
    header.parent = parent.hash
    header.parent_state_root = state.state_root
    header.timeslot = slot
    if seal is not None:
        header.seal = seal
    trace = Trace(state, Block(header, Extrinsic.default()), state)
    (folder / filename).write_bytes(trace.to_jam_bytes().to_bytes())
    return header


def write_genesis(folder, state):
    genesis = Header.default()
    (folder / "genesis.bin").write_bytes(TraceGenesis(genesis, state).to_jam_bytes().to_bytes())
    return genesis


def replay(folder):
    return asyncio.run(CliRunner().invoke(cli.main, ["traces", str(folder)]))


def test_trace_header_work_scales_with_unique_headers(tmp_path, cache_replay_app, monkeypatch):
    app, state = cache_replay_app
    parent = write_genesis(tmp_path, state)
    headers = [parent]
    for slot in range(1, 9):
        parent = write_header_trace(tmp_path, f"{slot:03}.bin", state, parent, slot)
        headers.append(parent)
    serialized = []
    persisted = []
    original_encode = Header.to_jam_bytes
    original_put = app.block_db.put

    def encode(header):
        if isinstance(header, cli._TraceHeader):
            serialized.append(header.timeslot)
        return original_encode(header)

    def put(key, value):
        if key.startswith(b"block_header:"):
            persisted.append(key)
        original_put(key, value)

    monkeypatch.setattr(Header, "to_jam_bytes", encode)
    monkeypatch.setattr(app.block_db, "put", put)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert Counter(serialized) == Counter(range(9))
    assert Counter(persisted) == Counter(b"block_header:" + header.hash for header in headers)


def test_replay_restores_cached_same_slot_sibling_indexes(tmp_path, cache_replay_app, monkeypatch):
    app, state = cache_replay_app
    genesis = write_genesis(tmp_path, state)
    first = write_header_trace(tmp_path, "001.bin", state, genesis, 7)
    sibling = write_header_trace(tmp_path, "002.bin", state, genesis, 7, seal=b"s" * 96)
    child = write_header_trace(tmp_path, "003.bin", state, first, 20)
    observed = {}

    async def inspect(block, produce=False):
        observed[block.header.hash] = app.retrieve_block_hash(7)

    monkeypatch.setattr(app, "state_transition", inspect)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert observed == {first.hash: first.hash, sibling.hash: sibling.hash, child.hash: first.hash}
    for header in (first, sibling):
        assert app.retrieve_block_header(header.hash).to_jam_bytes() == header.to_jam_bytes()
        assert app.block_db.get(b"block_number:" + header.hash) == (7).to_bytes(4, "little")


def test_persistence_reuse_restores_indexes_and_repairs_changed_bytes(cache_replay_app):
    app, _ = cache_replay_app
    header = cli._TraceHeader.from_header(Header.default())
    key = b"block_header:" + header.hash
    asyncio.run(app.store_block_header(header))
    app.block_db.put(key, b"corrupted stored bytes")
    app.block_db.delete(b"block_hash:" + header.timeslot.to_bytes(4, "little"))
    app.block_db.delete(b"block_number:" + header.hash)

    asyncio.run(app.store_block_header(header))

    assert app.block_db.get(key) == header.to_jam_bytes().to_bytes()
    assert app.retrieve_block_hash(header.timeslot) == header.hash
    assert app.block_db.get(b"block_number:" + header.hash) == header.timeslot.to_bytes(4, "little")


def test_replay_does_not_reuse_ancestor_cache_between_corpora(tmp_path, cache_replay_app):
    _, state = cache_replay_app
    first_folder, second_folder = tmp_path / "a", tmp_path / "b"
    first_folder.mkdir()
    second_folder.mkdir()
    genesis = write_genesis(first_folder, state)
    first = write_header_trace(first_folder, "001.bin", state, genesis, 7)
    write_genesis(second_folder, state)
    write_header_trace(second_folder, "001.bin", state, first, 20)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert "missing its parent header" in result.output
