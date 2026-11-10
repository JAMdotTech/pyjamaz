import asyncio
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from asyncclick.testing import CliRunner
from jamcodec.types import Bytes, U32, Vec

from pyjamaz import cli
from pyjamaz.availability import BundleData, availability_spec
from pyjamaz.fuzzer.v1.types import Features, FuzzerMessage, RefineBundle, WorkPackageBundle
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, TraceGenesis
from pyjamaz.models.block import Header
from pyjamaz.models.common import RefinementContext, WorkDigest, WorkExecResult, WorkItem, WorkPackage, WorkReport
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.pvm.constants import Opcode
from pyjamaz.pvm.types import PVMCode
from pyjamaz.refinement import Refinement
from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_preimage_availability
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine

# Exercise the real target and PVM using the existing detached-storage harness.
from test.test_fuzzer_refinement import target


@pytest.fixture
def case(tmp_path):
    item = WorkItem(0, bytes(32), 1_000_000, 1_000_000, 0, b'', [], [])
    package = WorkPackage(0, bytes(32), RefinementContext(
        bytes(32), bytes(32), bytes(32), bytes(32), 0, [],
    ), b'', b'', [item])
    request = RefineBundle(0, {}, 6, WorkPackageBundle(package, [], [], []))
    report = WorkReport(
        availability_spec(package.hash(), package.to_jam_bytes().to_bytes(), [], 6),
        package.context, 0, package.authorizer_hash(), 2, b'', {},
        [WorkDigest.from_work_item(item, WorkExecResult(ok=b''), 2)],
    )
    keyvals = [(b'm' * 31, b'initial state')]
    genesis = TraceGenesis(Header.default(), StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals))
    fixture = SimpleNamespace(folder=tmp_path, genesis=genesis, request=request, report=report)

    def write(folder=None):
        folder = folder or fixture.folder
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in [('genesis', fixture.genesis), ('refine', fixture.request), ('report', fixture.report)]:
            (folder / f'{name}.bin').write_bytes(value.to_jam_bytes().to_bytes())
    fixture.write = write
    write()
    return fixture


@pytest.fixture
def fake_session(monkeypatch, case):
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)

    def install(*, refine=True, response=None, state=None):
        class Session:
            features = Features(refine=refine)

            def __init__(self):
                self.requests = []
                self.connections = self.closes = 0

            async def connect(self):
                self.connections += 1

            async def close(self):
                self.closes += 1

            async def send_request(self, request):
                self.requests.append(request)
                if request.initialize is not None:
                    return FuzzerMessage(state_root=case.genesis.state.state_root)
                if request.refine_bundle is not None:
                    return response or FuzzerMessage(work_report=case.report)
                assert request.get_state == case.genesis.header.hash
                return FuzzerMessage(state=case.genesis.state.keyvals if state is None else state)

        session = Session()
        monkeypatch.setattr(cli, 'FuzzerSession', lambda *args, **kwargs: session)
        return session
    return install


def replay(folder):
    return asyncio.run(CliRunner().invoke(cli.main, ['fuzzer', 'traces', str(folder)]))


def test_matching_report_and_unchanged_state_pass_twice(case, fake_session):
    for _ in range(2):
        session = fake_session()
        result = replay(case.folder)
        assert result.exit_code == 0, result.output
        assert [request.enum_value()[0] for request in session.requests] == [
            'initialize', 'refine_bundle', 'get_state',
        ]
        assert session.connections == session.closes == 1


def test_each_refinement_fixture_gets_fresh_session(case, fake_session, tmp_path):
    case.write(tmp_path / 'another')
    session = fake_session()
    result = replay(tmp_path)
    assert result.exit_code == 0, result.output
    assert session.connections == session.closes == 2
    assert sum(request.initialize is not None for request in session.requests) == 2


@pytest.mark.parametrize('change,field', [
    ('auth_gas', 'auth_gas_used'), ('refine_gas', 'results[0].refine_load.gas_used'),
    ('erasure_root', 'package_spec.erasure_root'), ('result', 'results[0].result.ok'),
])
def test_complete_report_mismatch_reports_changed_field(case, fake_session, change, field):
    actual = deepcopy(case.report)
    if change == 'auth_gas':
        actual.auth_gas_used += 1
    elif change == 'refine_gas':
        actual.results[0].refine_load.gas_used += 1
    elif change == 'erasure_root':
        actual.package_spec.erasure_root = b'!' * 32
    else:
        actual.results[0].result.ok = b'wrong result'
    session = fake_session(response=FuzzerMessage(work_report=actual))
    result = replay(case.folder)
    assert result.exit_code != 0
    assert 'Work report mismatch' in result.output
    assert field in result.output
    assert 'expected=' in result.output and 'actual=' in result.output
    assert session.requests[-1].get_state == case.genesis.header.hash
    assert session.closes == 1


@pytest.mark.parametrize('error', ['Unauthorized', ''])
def test_unexpected_error_fails_and_checks_state(case, fake_session, error):
    session = fake_session(response=FuzzerMessage(error=error))
    result = replay(case.folder)
    assert result.exit_code != 0
    assert 'RefineBundle failed' in result.output
    assert session.requests[-1].get_state == case.genesis.header.hash


def test_refinement_must_not_mutate_initialized_state(case, fake_session):
    fake_session(state=[(b'm' * 31, b'changed')])
    result = replay(case.folder)
    assert result.exit_code != 0
    assert 'Refinement changed initialized state' in result.output


def test_refinement_requires_negotiated_feature(case, fake_session):
    session = fake_session(refine=False)
    result = replay(case.folder)
    assert result.exit_code != 0
    assert 'Refinement was not negotiated' in result.output
    assert session.requests == []


@pytest.mark.parametrize('missing', ['genesis.bin', 'refine.bin', 'report.bin'])
def test_incomplete_fixture_fails(case, fake_session, missing):
    (case.folder / missing).unlink()
    session = fake_session()
    result = replay(case.folder)
    assert result.exit_code != 0
    assert f'missing {case.folder / missing}' in result.output
    assert session.requests == []


@pytest.mark.parametrize('name', ['genesis.bin', 'refine.bin', 'report.bin'])
def test_fixture_with_trailing_bytes_fails(case, fake_session, name):
    file = case.folder / name
    file.write_bytes(file.read_bytes() + b'\x00')
    session = fake_session()
    result = replay(case.folder)
    assert result.exit_code != 0
    assert 'trailing bytes' in result.output
    assert name in result.output
    assert session.requests == []


def test_real_target_replays_real_pvm_report_twice(case, target, monkeypatch):
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)
    raw = bytes((Opcode.load_imm.value, 8, 0, 0, 0, 0, Opcode.jump_ind.value, 0))
    code = PVMCode(0, 0, len(raw), [], raw, [True, False, False, False, False, False, True, False])
    encoded = code.to_jam_bytes().to_bytes()
    preimage = (Bytes.encode(b'').to_bytes() + bytes(8) + (4096).to_bytes(3, 'little')
                + len(encoded).to_bytes(4, 'little') + encoded)
    code_hash = blake2b_256_hash(preimage)
    package = case.request.bundle.work_package
    package.auth_code_hash = package.items[0].code_hash = code_hash
    keyvals = [
        (state_key_constructor_preimage(0, code_hash), preimage),
        (state_key_constructor_preimage_availability(0, code_hash, len(preimage)), Vec(U32).encode([0]).to_bytes()),
    ]
    case.genesis.state = StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals)
    engine = InMemoryStorageEngine()
    for key, value in keyvals:
        engine.put(key, value)
    services = ServicesState(services={})
    services.set_state_storage(StateStorage(engine))
    services.pending_changes = PendingChanges()
    case.report = Refinement(services, BundleData.from_parts(package, [], [], [])).compute_work_report(
        package, 0, {}, 6,
    )
    assert case.report.results[0].result.ok == b''
    assert case.report.auth_gas_used > 0
    case.write()

    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            for _ in range(2):
                result = await CliRunner().invoke(cli.main, [
                    'fuzzer', 'traces', str(case.folder), '--socket-path', target.path,
                ])
                assert result.exit_code == 0, result.output or result.exception
                assert target.app.state_storage.state_root() == case.genesis.state.state_root
        finally:
            server.close()
            await server.wait_closed()
    asyncio.run(run())


def test_captured_polkajam_fixture_replays_twice(target, monkeypatch):
    fixture_dir = os.getenv('PYJAMAZ_REFINEMENT_TRACE_DIR')
    if fixture_dir is None:
        pytest.skip('Set PYJAMAZ_REFINEMENT_TRACE_DIR to replay a captured reference fixture')
    assert fixture_dir, 'PYJAMAZ_REFINEMENT_TRACE_DIR must name a fixture directory'
    folder = Path(fixture_dir)
    assert folder.is_dir(), f'Captured fixture directory does not exist: {folder}'
    # Validate the supplied oracle rather than computing an expected report here.
    for name in ('genesis.bin', 'refine.bin', 'report.bin'):
        assert (folder / name).is_file(), f'Captured fixture is missing {folder / name}'
    genesis = cli._read_refinement_fixture(folder / 'genesis.bin', TraceGenesis)
    monkeypatch.setattr(cli, 'setup_logging', lambda *args: None)

    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            for _ in range(2):
                result = await CliRunner().invoke(cli.main, [
                    'fuzzer', 'traces', str(folder), '--socket-path', target.path,
                ])
                assert result.exit_code == 0, result.output or result.exception
                assert target.app.state_storage.state_root() == genesis.state.state_root
        finally:
            server.close()
            await server.wait_closed()
    asyncio.run(run())
