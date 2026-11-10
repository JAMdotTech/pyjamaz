import asyncio

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.fuzzer.v1.types import FuzzerMessage
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header


def state_dump(value):
    keyvals = [(b'\x01' * 31, value)]
    return StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals)


def write_chain(folder, *, genesis=False, corrupt_checkpoint=False):
    folder.mkdir(exist_ok=True)
    prior, state = state_dump(b'before checkpoint'), state_dump(b'checkpoint')
    header = Header.default()
    header.timeslot = 7
    header.parent = b'p' * 32
    header.parent_state_root = prior.state_root
    checkpoint_state = StateDump(b'!' * 32, state.keyvals) if corrupt_checkpoint else state
    if genesis:
        (folder / 'genesis.bin').write_bytes(TraceGenesis(header, state).to_jam_bytes().to_bytes())
    else:
        (folder / '00000001.bin').write_bytes(Trace(
            prior, Block(header, Extrinsic.default()), checkpoint_state,
        ).to_jam_bytes().to_bytes())

    def candidate(number=2, post_state=None):
        child = Header.default()
        child.parent = header.hash
        child.parent_state_root = state.state_root
        child.timeslot = header.timeslot + 1
        child.author_index = number
        trace = Trace(state, Block(child, Extrinsic.default()), post_state or state)
        (folder / f'{number:08}.bin').write_bytes(trace.to_jam_bytes().to_bytes())
        return trace

    return header, state, candidate


@pytest.fixture
def fake_session(monkeypatch):
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)

    def install(responses, fail_connect=None):
        class Session:
            def __init__(self):
                self.responses = iter(responses)
                self.requests = []
                self.connections = []
                self.connect_count = 0
                self.close_count = 0

            async def connect(self):
                self.connect_count += 1
                self.writer = object()
                if self.connect_count == fail_connect:
                    raise RuntimeError('handshake failed')

            async def send_request(self, request):
                self.requests.append(request)
                self.connections.append(self.connect_count)
                return next(self.responses)

            async def close(self):
                self.close_count += 1

        session = Session()
        monkeypatch.setattr(cli, 'FuzzerSession', lambda *args, **kwargs: session)
        return session

    return install


def replay(folder):
    return asyncio.run(CliRunner().invoke(cli.main, ['fuzzer', 'traces', str(folder)]))


def test_shortened_trace_initializes_real_checkpoint_without_importing_it(tmp_path, fake_session):
    header, state, candidate = write_chain(tmp_path)
    expected = state_dump(b'after candidate')
    trace = candidate(post_state=expected)
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(state_root=expected.state_root),
    ])

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert len(session.requests) == 2
    initialization = session.requests[0].initialize
    assert initialization.header.to_jam_bytes().to_bytes() == header.to_jam_bytes().to_bytes()
    assert initialization.state == state.keyvals
    assert initialization.ancestry == []
    assert session.requests[1].import_block.header.hash == trace.block.header.hash
    assert session.close_count == 1


def test_rejected_candidate_queries_checkpoint_and_then_imports_sibling(tmp_path, fake_session):
    header, state, candidate = write_chain(tmp_path)
    rejected = candidate()
    expected = state_dump(b'accepted sibling')
    accepted = candidate(3, expected)
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(error='Invalid author key'),
        FuzzerMessage(state=state.keyvals),
        FuzzerMessage(state_root=expected.state_root),
    ])

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert session.requests[0].initialize.header.hash == header.hash
    assert session.requests[1].import_block.header.hash == rejected.block.header.hash
    assert session.requests[2].get_state == header.hash
    assert session.requests[3].import_block.header.hash == accepted.block.header.hash
    assert session.connect_count == session.close_count == 1


def test_changed_parent_state_after_rejection_fails(tmp_path, fake_session):
    header, state, candidate = write_chain(tmp_path)
    candidate()
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(error='Invalid seal key'),
        FuzzerMessage(state=state_dump(b'corrupt parent').keyvals),
    ])

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert '1 fuzzer trace state-root mismatch' in result.output
    assert session.requests[-1].get_state == header.hash
    assert session.close_count == 1


def test_corrupt_checkpoint_is_rejected_before_initializing_target(tmp_path, fake_session):
    _, _, candidate = write_chain(tmp_path, corrupt_checkpoint=True)
    candidate()
    session = fake_session([])

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert 'Checkpoint state root mismatch' in result.output
    assert session.requests == []
    assert session.close_count == 1


def test_checkpoint_without_candidates_does_not_pass(tmp_path, fake_session):
    write_chain(tmp_path)
    session = fake_session([])

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert 'no subsequent block' in result.output
    assert session.requests == []
    assert session.close_count == 1


def test_checkpoint_target_root_mismatch_closes_session(tmp_path, fake_session):
    _, _, candidate = write_chain(tmp_path)
    candidate()
    session = fake_session([FuzzerMessage(state_root=b'!' * 32)])

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert 'initial state root mismatch' in result.output
    assert len(session.requests) == 1
    assert session.close_count == 1


@pytest.mark.parametrize('second_has_genesis', [False, True])
def test_independent_directories_get_fresh_sessions(tmp_path, fake_session, second_has_genesis):
    first_header, state, first_candidate = write_chain(tmp_path / 'a-first')
    first_candidate()
    second_header, _, second_candidate = write_chain(tmp_path / 'b-second', genesis=second_has_genesis)
    second_candidate()
    session = fake_session([FuzzerMessage(state_root=state.state_root)] * 4)

    result = replay(tmp_path)

    assert result.exit_code == 0, result.output
    assert session.connect_count == session.close_count == 2
    assert session.connections == [1, 1, 2, 2]
    assert session.requests[0].initialize.header.hash == first_header.hash
    assert session.requests[2].initialize.header.hash == second_header.hash
    assert all(request.import_block is not None for request in session.requests[1::2])


def test_partial_reconnect_failure_closes_new_session(tmp_path, fake_session):
    _, state, candidate = write_chain(tmp_path / 'a-first')
    candidate()
    _, _, candidate = write_chain(tmp_path / 'b-second')
    candidate()
    session = fake_session([FuzzerMessage(state_root=state.state_root)] * 2, fail_connect=2)

    result = replay(tmp_path)

    assert result.exit_code != 0
    assert str(result.exception) == 'handshake failed'
    assert session.connect_count == session.close_count == 2
    assert session.connections == [1, 1]
