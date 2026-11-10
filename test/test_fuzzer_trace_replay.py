import asyncio

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.fuzzer.v1.types import FuzzerMessage
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header


@pytest.fixture
def trace_files(tmp_path):
    keyvals = [(b'\x01' * 31, b'parent state')]
    state = StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals)
    genesis = Header.default()
    (tmp_path / 'genesis.bin').write_bytes(TraceGenesis(genesis, state).to_jam_bytes().to_bytes())

    def write_trace(number=1, pre_state=None, post_state=None):
        header = Header.default()
        header.timeslot = number
        header.parent = genesis.hash
        header.parent_state_root = state.state_root
        trace = Trace(pre_state or state, Block(header, Extrinsic.default()), post_state or state)
        (tmp_path / f'{number:08}.bin').write_bytes(trace.to_jam_bytes().to_bytes())
        return trace

    return tmp_path, state, genesis, write_trace


@pytest.fixture
def fake_session(monkeypatch):
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)

    def install(responses, connect_error=None):
        class Session:
            def __init__(self):
                self.requests = []
                self.responses = iter(responses)
                self.closed = False

            async def connect(self):
                self.writer = object()
                if connect_error is not None:
                    raise connect_error

            async def send_request(self, request):
                self.requests.append(request)
                response = next(self.responses)
                if isinstance(response, Exception):
                    raise response
                return response

            async def close(self):
                self.closed = True

        session = Session()
        monkeypatch.setattr(cli, 'FuzzerSession', lambda *args, **kwargs: session)
        return session

    return install


def replay(folder, prompt=False):
    args = ['fuzzer', 'traces', str(folder)]
    if prompt:
        args.append('--prompt-on-diff')
    return asyncio.run(CliRunner().invoke(cli.main, args, input='q\n' if prompt else None))


def test_matching_roots_succeed_and_close_session(trace_files, fake_session):
    folder, state, _, write_trace = trace_files
    write_trace()
    session = fake_session([FuzzerMessage(state_root=state.state_root)] * 2)

    result = replay(folder)

    assert result.exit_code == 0, result.output
    assert len(session.requests) == 2
    assert session.closed


@pytest.mark.parametrize('prompt,expected_count', [(False, 2), (True, 1)])
def test_root_mismatches_fail_even_after_prompt_quit(trace_files, fake_session, prompt, expected_count):
    folder, state, _, write_trace = trace_files
    write_trace(1)
    write_trace(2)
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(state_root=b'!' * 32),
        FuzzerMessage(state_root=b'!' * 32),
    ])

    result = replay(folder, prompt)

    assert result.exit_code != 0
    assert f'{expected_count} fuzzer trace state-root mismatch' in result.output
    assert len(session.requests) == 1 + expected_count
    assert session.closed


@pytest.mark.parametrize('error', ['bad block', ''])
def test_expected_rejection_checks_actual_parent_state(trace_files, fake_session, error):
    folder, state, genesis, write_trace = trace_files
    # The fixture's pre-state root must never substitute for the target's root.
    write_trace(pre_state=StateDump(b'!' * 32, state.keyvals))
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(error=error),
        FuzzerMessage(state=state.keyvals),
    ])

    result = replay(folder)

    assert result.exit_code == 0, result.output
    assert session.requests[-1].get_state == genesis.hash
    assert session.closed


def test_rejected_block_with_changed_parent_state_fails(trace_files, fake_session):
    folder, state, genesis, write_trace = trace_files
    write_trace()
    session = fake_session([
        FuzzerMessage(state_root=state.state_root),
        FuzzerMessage(error='bad block'),
        FuzzerMessage(state=[(state.keyvals[0][0], b'changed by failed import')]),
    ])

    result = replay(folder)

    assert result.exit_code != 0
    assert '1 fuzzer trace state-root mismatch' in result.output
    assert session.requests[-1].get_state == genesis.hash
    assert session.closed


@pytest.mark.parametrize('operation,response', [
    ('Initialize', FuzzerMessage(error='invalid initial state')),
    ('Initialize', FuzzerMessage(state=[])),
    ('ImportBlock', FuzzerMessage(state=[])),
    ('GetState', FuzzerMessage(error='unknown parent')),
    ('GetState', FuzzerMessage(state_root=bytes(32))),
])
def test_protocol_errors_fail_and_close_session(trace_files, fake_session, operation, response):
    folder, state, _, write_trace = trace_files
    write_trace()
    responses = []
    if operation != 'Initialize':
        responses.append(FuzzerMessage(state_root=state.state_root))
    if operation == 'GetState':
        responses.append(FuzzerMessage(error='bad block'))
    responses.append(response)
    session = fake_session(responses)

    result = replay(folder)

    assert result.exit_code != 0
    assert operation in result.output
    assert session.closed


def test_initial_root_mismatch_fails_and_closes_session(trace_files, fake_session):
    folder, _, _, write_trace = trace_files
    write_trace()
    session = fake_session([FuzzerMessage(state_root=b'!' * 32)])

    result = replay(folder)

    assert result.exit_code != 0
    assert 'initial state root mismatch' in result.output
    assert len(session.requests) == 1
    assert session.closed


def test_request_failure_closes_session(trace_files, fake_session):
    folder, state, _, write_trace = trace_files
    write_trace()
    session = fake_session([FuzzerMessage(state_root=state.state_root), RuntimeError('request timed out')])

    result = replay(folder)

    assert result.exit_code != 0
    assert str(result.exception) == 'request timed out'
    assert session.closed


def test_handshake_failure_closes_open_socket(trace_files, fake_session):
    folder, _, _, write_trace = trace_files
    write_trace()
    session = fake_session([], connect_error=RuntimeError('invalid PeerInfo'))

    result = replay(folder)

    assert result.exit_code != 0
    assert str(result.exception) == 'invalid PeerInfo'
    assert session.requests == []
    assert session.closed
