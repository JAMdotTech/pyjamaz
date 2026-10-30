import asyncio
from copy import deepcopy
from types import SimpleNamespace
from tempfile import TemporaryDirectory

import pytest
from asyncclick.testing import CliRunner
from jam_erasure import encode_shards
from jamcodec.base import JamBytes
from jamcodec.types import Bytes, H256, U32, Vec

from pyjamaz import refinement as refinement_module
from pyjamaz.app import PyjamazApp
from pyjamaz.availability import BundleData, availability_spec, paged_proof_segments
from pyjamaz.erasure import erasure_data_shards
from pyjamaz.refinement import Refinement
from pyjamaz.exceptions import BlockValidationError
from pyjamaz.fuzzer.v1.session import FuzzerSession
from pyjamaz.fuzzer.v1.target import FuzzerTarget
from pyjamaz.fuzzer.v1.types import FuzzerMessage, InitializeMessage, RefineBundle, WorkPackageBundle
from pyjamaz.hashing import blake2b_256_hash as hash_blob
from pyjamaz.merkle import ConstantDepthMerkleTree, PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, Trace, TraceGenesis
from pyjamaz.models.block import Block, Extrinsic, Header
from pyjamaz.models.common import ImportSegment, RefinementContext, WorkExecResult, WorkItem, WorkItemExtrinsic, WorkPackage
from pyjamaz.models.context import AppContext
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.pvm.constants import Opcode
from pyjamaz.pvm.types import PVMCode
from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_preimage_availability
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


MARKER = b'm' * 31


@pytest.fixture
def refine_request():
    segments = [bytes([i]) * 4104 for i in range(4)]
    tree = ConstantDepthMerkleTree(segments)
    reference = b'r' * 32
    item = WorkItem(0, bytes(32), 1000, 1000, 2, b'payload', [
        ImportSegment.from_segment_root(tree.root(), 1),
        ImportSegment.from_work_package_hash(reference, 2),
    ], [WorkItemExtrinsic.from_blob(b'abc'), WorkItemExtrinsic.from_blob(b'')])
    package = WorkPackage(0, bytes(32), RefinementContext(
        bytes(32), bytes(32), bytes(32), bytes(32), 0, [],
    ), b'', b'', [item])
    bundle = WorkPackageBundle(package, [b'abc', b''], segments[1:3], [tree.trace(1), tree.trace(2)])
    return RefineBundle(1, {reference: tree.root()}, 6, bundle)


@pytest.fixture
def target():
    engine = InMemoryStorageEngine()
    app = PyjamazApp.__new__(PyjamazApp)
    app.state_db = engine.namespace(b'state')
    app.block_db = engine.namespace(b'block')
    app.state_storage = StateStorage(app.state_db)
    app.app_context = AppContext(state_storage=app.state_storage)
    app.working_state = None
    app.pubsub = app.d3l_store = None

    def retrieve():
        services = ServicesState(services={})
        services.set_state_storage(app.state_storage)
        services.pending_changes = PendingChanges()
        return SimpleNamespace(state_root=app.state_storage.state_root(), services=services)

    app.retrieve_jam_state = retrieve
    app.import_block = app._import_block

    async def transition(block, produce=False):
        await app.initialize(block.header)
        app.state_storage.put(MARKER, block.header.timeslot.to_bytes(4, 'little'))
        if block.header.author_index:
            raise BlockValidationError('invalid block')
        app.state_storage.commit()
        app.working_state = retrieve()

    app.state_transition = transition
    # macOS Unix-domain socket paths cannot exceed 104 bytes.
    with TemporaryDirectory(prefix='refine-', dir='/tmp') as directory:
        yield FuzzerTarget(f'{directory}/target.sock', app)


async def initialize(target):
    header = Header.default()
    response = await target.msg_initialize(FuzzerMessage(initialize=InitializeMessage(
        header, [(MARKER, bytes(4))], [],
    )))
    assert response.error is None
    return header


@pytest.fixture
def vm(monkeypatch):
    calls = []
    auth = SimpleNamespace(work_exec_result=WorkExecResult(ok=b'auth'), gas_used=3)
    output = SimpleNamespace(work_exec_result=WorkExecResult(ok=b'result'), gas_used=7,
                             export_segments=[b'x' * 4104, b'y' * 4104])
    monkeypatch.setattr(refinement_module, 'pvm_invoke_is_authorized', lambda *_: auth)

    def refine(**kwargs):
        calls.append(kwargs)
        return output

    monkeypatch.setattr(refinement_module, 'pvm_invoke_refine', refine)
    return SimpleNamespace(calls=calls, auth=auth, output=output)


def test_bundle_encoding_and_imports_follow_manifest_order(refine_request):
    bundle = refine_request.bundle
    data = BundleData.from_parts(bundle.work_package, bundle.extrinsics, bundle.import_segments, bundle.justifications)
    extrinsics = [data.extrinsic_data(item) for item in bundle.work_package.items]
    segments = [data.import_segments(refine_request.segment_root_lookup, item) for item in bundle.work_package.items]
    encoded = data.assemble_bundle(bundle.work_package, refine_request.segment_root_lookup)
    assert extrinsics == [[b'abc', b'']]
    assert segments == [bundle.import_segments]
    assert encoded == (bundle.work_package.to_jam_bytes().to_bytes() + b'abc'
                       + b''.join(bundle.import_segments)
                       + b''.join(b'\x02' + b''.join(path) for path in bundle.justifications))
    assert encoded != bundle.to_jam_bytes().to_bytes()


@pytest.mark.parametrize('fault', [
    'extra_extrinsic', 'missing_extrinsic', 'wrong_length', 'wrong_hash', 'extra_import',
    'missing_import', 'missing_proof', 'wrong_segment', 'wrong_proof', 'reversed_proof',
    'missing_mapping', 'extra_mapping', 'wrong_mapping', 'short_segment',
])
def test_invalid_bundles_are_rejected_before_execution(target, refine_request, vm, fault):
    bundle = refine_request.bundle
    if fault == 'extra_extrinsic':
        bundle.extrinsics.append(b'')
    elif fault == 'missing_extrinsic':
        bundle.extrinsics.pop()
    elif fault == 'wrong_length':
        bundle.extrinsics[0] = b'abcd'
    elif fault == 'wrong_hash':
        bundle.extrinsics[0] = b'xyz'
    elif fault == 'extra_import':
        bundle.import_segments.append(bytes(4104))
    elif fault == 'missing_import':
        bundle.import_segments.pop()
    elif fault == 'missing_proof':
        bundle.justifications.pop()
    elif fault == 'wrong_segment':
        bundle.import_segments[0] = bytes(4104)
    elif fault == 'wrong_proof':
        bundle.justifications[0][0] = bytes(32)
    elif fault == 'reversed_proof':
        bundle.justifications[0].reverse()
    elif fault == 'missing_mapping':
        refine_request.segment_root_lookup.clear()
    elif fault == 'extra_mapping':
        refine_request.segment_root_lookup[b'z' * 32] = bytes(32)
    elif fault == 'wrong_mapping':
        refine_request.segment_root_lookup[b'r' * 32] = bytes(32)
    elif fault == 'short_segment':
        bundle.import_segments[0] = bytes(4103)

    async def run():
        await initialize(target)
        response = await target._dispatch(FuzzerMessage(refine_bundle=refine_request))
        assert response.error is not None
        assert response.work_report is None
        assert vm.calls == []

    asyncio.run(run())


def test_refinement_uses_last_successful_state_without_mutating_it(target, refine_request, vm):
    async def run():
        genesis = await initialize(target)
        header = Header.default()
        header.parent, header.timeslot = genesis.hash, 1
        assert (await target.msg_import_block(FuzzerMessage(import_block=Block(header, Extrinsic.default())))).error is None
        selected = target.app.working_state
        storage = target.app.state_storage
        before = deepcopy(storage.change_sets)
        # Reject a sibling based on the older state; refinement must still use the successful head.
        rejected = deepcopy(header)
        rejected.timeslot, rejected.author_index = 2, 1
        assert (await target.msg_import_block(FuzzerMessage(import_block=Block(rejected, Extrinsic.default())))).error
        response = await target._dispatch(FuzzerMessage(refine_bundle=refine_request))
        report = response.work_report
        assert report is not None
        assert report.segment_root_lookup == refine_request.segment_root_lookup
        assert report.package_spec.erasure_shards == refine_request.erasure_shards
        assert report.package_spec.erasure_root != bytes(32)
        assert report.results[0].result.ok == b'result'
        assert vm.calls[0]['work_items_import_segments'] == [refine_request.bundle.import_segments]
        assert vm.calls[0]['extrinsics'] == [[b'abc', b'']]
        assert vm.calls[0]['services_state'].state_storage.get(MARKER) == (1).to_bytes(4, 'little')
        assert storage.change_sets == before
        assert storage.block_hash == header.hash
        assert target.app.working_state.state_root == selected.state_root
        assert storage.transaction == {}

    asyncio.run(run())


@pytest.mark.parametrize('failure', ['out_of_gas', 'panic', 'bad_code', 'code_oversize', 'bad_exports', 'digest_oversize'])
def test_item_failures_are_reports_with_declared_zero_exports(target, refine_request, vm, failure):
    if failure == 'bad_exports':
        vm.output.export_segments = []
    elif failure == 'digest_oversize':
        vm.output.work_exec_result = WorkExecResult(ok=bytes(48 * 1024))
    else:
        vm.output.work_exec_result = WorkExecResult(**{failure: True})

    async def run():
        await initialize(target)
        response = await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))
        assert response.error is None
        report = response.work_report
        assert report.results[0].result.enum_value()[0] == failure
        assert report.package_spec.exports_count == 2
        assert report.package_spec.exports_root == ConstantDepthMerkleTree([bytes(4104)] * 2).root()
        assert report.results[0].refine_load.gas_used == 7

    asyncio.run(run())


def test_authorization_failure_is_recoverable(target, refine_request, vm):
    async def run():
        await initialize(target)
        vm.auth.work_exec_result = WorkExecResult(panic=True)
        assert (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))).error
        assert vm.calls == []
        vm.auth.work_exec_result = WorkExecResult(ok=b'')
        assert (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))).work_report

    asyncio.run(run())


@pytest.mark.parametrize('metadata', [b'', bytes(5), b'\xff'])
def test_real_authorizer_and_refine_pvm_on_historical_state(target, refine_request, metadata):
    # Return an empty successful result from both real invocations.
    raw = bytes((Opcode.load_imm.value, 8, 0, 0, 0, 0, Opcode.jump_ind.value, 0))
    code = PVMCode(0, 0, len(raw), [], raw, [True, False, False, False, False, False, True, False])
    encoded_code = code.to_jam_bytes().to_bytes()
    preimage = (Bytes.encode(metadata).to_bytes() + bytes(8) + (4096).to_bytes(3, 'little')
                + len(encoded_code).to_bytes(4, 'little') + encoded_code)
    code_hash = hash_blob(preimage)
    package = refine_request.bundle.work_package
    package.auth_code_hash = package.items[0].code_hash = code_hash
    package.items[0].export_count = 0
    state = [
        (state_key_constructor_preimage(0, code_hash), preimage),
        (state_key_constructor_preimage_availability(0, code_hash, len(preimage)), Vec(U32).encode([0]).to_bytes()),
    ]

    async def run():
        await target.msg_initialize(FuzzerMessage(initialize=InitializeMessage(Header.default(), state, [])))
        response = await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))
        assert response.error is None
        report = response.work_report
        assert report.auth_output == b''
        assert report.auth_gas_used > 0
        assert report.results[0].result.ok == b''
        assert report.results[0].refine_load.gas_used > 0
        assert report.package_spec.exports_count == 0
        assert report.package_spec.erasure_root != bytes(32)
        # Reusing the same package at another historical time cannot retain stale code.
        package.context.lookup_anchor_slot = 10
        key = state_key_constructor_preimage_availability(0, code_hash, len(preimage))
        target.app.state_db.put(key, Vec(U32).encode([0, 10]).to_bytes())
        assert (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))).error == 'Unauthorized'

    asyncio.run(run())


def test_multiple_items_preserve_groups_and_export_offsets(target, refine_request, vm, monkeypatch):
    package = refine_request.bundle.work_package
    second = deepcopy(package.items[0])
    second.export_count = 1
    second.import_segments.reverse()
    package.items.append(second)
    bundle = refine_request.bundle
    bundle.extrinsics += list(bundle.extrinsics)
    bundle.import_segments += list(reversed(bundle.import_segments))
    bundle.justifications += list(reversed(bundle.justifications))

    def refine(**kwargs):
        vm.calls.append(kwargs)
        if kwargs['work_item_index'] == 0:
            # A failed item must not consume output space available to the next item.
            return SimpleNamespace(work_exec_result=WorkExecResult(ok=bytes(48 * 1024 - 4)),
                                   gas_used=2, export_segments=[])
        return SimpleNamespace(work_exec_result=WorkExecResult(ok=b'next'),
                               gas_used=3, export_segments=[b'z' * 4104])

    monkeypatch.setattr(refinement_module, 'pvm_invoke_refine', refine)

    async def run():
        await initialize(target)
        response = await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))
        assert response.error is None
        report = response.work_report
        assert report.results[0].result.bad_exports
        assert report.results[1].result.ok == b'next'
        assert [c['export_segment_offset'] for c in vm.calls] == [0, 2]
        assert vm.calls[1]['work_items_import_segments'] == [bundle.import_segments[:2], bundle.import_segments[2:]]
        assert vm.calls[1]['extrinsics'] == [[b'abc', b''], [b'abc', b'']]
        assert report.package_spec.exports_root == ConstantDepthMerkleTree([bytes(4104)] * 2 + [b'z' * 4104]).root()

    asyncio.run(run())


@pytest.mark.parametrize(('field', 'value'), [('core_index', 65535), ('erasure_shards', 0), ('erasure_shards', 7)])
def test_invalid_computation_arguments_are_recoverable(target, refine_request, vm, field, value):
    setattr(refine_request, field, value)

    async def run():
        await initialize(target)
        assert (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))).error
        assert vm.calls == []

    asyncio.run(run())


def test_oversized_authorizer_result_is_rejected(target, refine_request, vm):
    vm.auth.work_exec_result = WorkExecResult(ok=bytes(48 * 1024 + 1))

    async def run():
        await initialize(target)
        assert (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=refine_request))).error == 'Oversized auth result'
        assert vm.calls == []

    asyncio.run(run())


@pytest.mark.parametrize('count', [0, 1, 63, 64, 65, 129])
def test_paged_proof_encoding(count):
    exports = [i.to_bytes(4, 'little') * 1026 for i in range(count)]
    tree = ConstantDepthMerkleTree(exports)
    pages = paged_proof_segments(exports)
    assert len(pages) == (count + 63) // 64
    for page_index, page in enumerate(pages):
        stream = JamBytes(page)
        path_codec, leaves_codec = Vec(H256).new(), Vec(H256).new()
        path_codec.decode(stream)
        leaves_codec.decode(stream)
        path, leaves = path_codec.to_serializable_obj(), leaves_codec.to_serializable_obj()
        start = page_index * 64
        assert len(page) == 4104
        assert leaves == [hash_blob(b'leaf' + s) for s in exports[start:start + 64]]
        assert path == tree.trace(start)[:max(0, (count - 1).bit_length() - 6)]
        assert not any(stream.get_remaining_bytes())


def test_availability_matches_independent_per_segment_construction(refine_request):
    # CC0 GP-0.8.0 tiny ec-3 vector from davxy/jam-test-vectors/erasure/tiny.
    assert encode_shards(bytes.fromhex('615d17'), 3, 3) == [
        bytes.fromhex(s) for s in ('615d', '1700', '0000', '59d0', '0615', '756d')
    ]
    bundle = refine_request.bundle
    data = BundleData.from_parts(bundle.work_package, bundle.extrinsics, bundle.import_segments, bundle.justifications)
    encoded = data.assemble_bundle(bundle.work_package, refine_request.segment_root_lookup)
    exports = [bytes([i]) * 4104 for i in range(3)]
    originals = erasure_data_shards(6)
    shard_lists = [encode_shards(s, originals, 6 - originals) for s in exports + paged_proof_segments(exports)]

    def node(values):
        if not values:
            return bytes(32)
        if len(values) == 1:
            return values[0]
        split = (len(values) + 1) // 2
        return hash_blob(b'node' + node(values[:split]) + node(values[split:]))

    rows = list(zip(*shard_lists))
    bundle_shards = encode_shards(encoded, originals, 6 - originals)
    expected = node([hash_blob(shard) + node(list(row)) for shard, row in zip(bundle_shards, rows)])
    spec = availability_spec(bundle.work_package.hash(), encoded, exports, 6)
    assert spec.erasure_root == expected
    assert spec.length == len(encoded)
    assert spec.hash == bundle.work_package.hash()


def test_dynamic_erasure_dimensions(refine_request, monkeypatch):
    from pyjamaz import erasure
    from pyjamaz.graypaper_constants import valid_validator_count
    # Exercise the full-domain counts even when pytest runs with Tiny constants.
    monkeypatch.setattr(erasure, 'valid_validator_count', lambda n: valid_validator_count(n, core_count=341))
    for validators, originals in [(6, 3), (9, 4), (1020, 228), (1023, 342)]:
        assert erasure_data_shards(validators) == originals
        bundle = refine_request.bundle
        spec = availability_spec(bundle.work_package.hash(), b'bundle', [bytes(4104)], validators)
        assert spec.erasure_shards == validators
        assert spec.erasure_root != bytes(32)


def test_frame_rejects_trailing_bytes():
    async def run():
        message = FuzzerMessage(state_root=bytes(32)).to_jam_bytes().to_bytes() + b'\0'
        reader = asyncio.StreamReader()
        reader.feed_data(len(message).to_bytes(4, 'little') + message)
        reader.feed_eof()
        with pytest.raises(ValueError, match='trailing bytes'):
            await FuzzerMessage.fuzzer_decode(reader)

    asyncio.run(run())


def test_socket_negotiation_and_rejection_recovery(target, refine_request, vm):
    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            session = FuzzerSession(target.path, app=None)
            await session.connect()
            try:
                assert session.features.refine
                init = InitializeMessage(Header.default(), [(MARKER, bytes(4))], [])
                await session.send_request(FuzzerMessage(initialize=init))
                invalid = deepcopy(refine_request)
                invalid.bundle.extrinsics[0] = b'bad'
                assert (await session.send_request(FuzzerMessage(refine_bundle=invalid))).error
                expected = (await target.msg_refine_bundle(FuzzerMessage(refine_bundle=deepcopy(refine_request)))).work_report
                response = await session.send_request(FuzzerMessage(refine_bundle=refine_request))
                assert response.work_report.to_jam_bytes().to_bytes() == expected.to_jam_bytes().to_bytes()
            finally:
                await session.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


@pytest.mark.parametrize('local_ancestry', [False, True])
@pytest.mark.parametrize('peer_ancestry', [False, True])
def test_initialized_session_negotiates_ancestry(target, monkeypatch, local_ancestry, peer_ancestry):
    target_handshake = target.msg_handshake
    client_handshake = FuzzerSession.msg_handshake
    transition = target.app.state_transition
    seen = []

    def handshake():
        message = target_handshake()
        message.peer_info.features.block_ancestry = local_ancestry
        return message

    def peer_handshake(session):
        message = client_handshake(session)
        message.peer_info.features.block_ancestry = peer_ancestry
        return message

    async def record_transition(block, produce=False):
        seen.append(target.app.app_context.skip_lookup_anchor_ancestry.get())
        await transition(block, produce)

    monkeypatch.setattr(target, 'msg_handshake', handshake)
    monkeypatch.setattr(FuzzerSession, 'msg_handshake', peer_handshake)
    monkeypatch.setattr(target.app, 'state_transition', record_transition)

    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            session = FuzzerSession(target.path, app=None)
            await session.connect()
            try:
                genesis = Header.default()
                await session.send_request(FuzzerMessage(initialize=InitializeMessage(genesis, [], [])))
                header = Header.default()
                header.parent, header.timeslot = genesis.hash, 1
                response = await session.send_request(FuzzerMessage(import_block=Block(header, Extrinsic.default())))
                assert response.state_root is not None
                assert seen == [not (local_ancestry and peer_ancestry)]
            finally:
                await session.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_unnegotiated_and_uninitialized_refinement_closes_without_error(target, refine_request):
    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            for negotiate, initialized in [(False, True), (True, False)]:
                session = FuzzerSession(target.path, app=None)
                reader, writer = await asyncio.open_unix_connection(target.path)
                peer = session.msg_handshake()
                peer.peer_info.features.refine = negotiate
                writer.write(peer.fuzzer_encode())
                await writer.drain()
                assert (await FuzzerMessage.fuzzer_decode(reader)).peer_info
                if initialized:
                    writer.write(FuzzerMessage(initialize=InitializeMessage(Header.default(), [], [])).fuzzer_encode())
                    await writer.drain()
                    assert (await FuzzerMessage.fuzzer_decode(reader)).state_root is not None
                writer.write(FuzzerMessage(refine_bundle=refine_request).fuzzer_encode())
                await writer.drain()
                assert await asyncio.wait_for(reader.read(), timeout=2) == b''
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_internal_refinement_error_and_duplicate_initialize_close_session(target, refine_request, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('internal failure')

    monkeypatch.setattr(Refinement, 'compute_work_report', fail)

    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            for duplicate_init in (False, True):
                session = FuzzerSession(target.path, app=None)
                await session.connect()
                init = FuzzerMessage(initialize=InitializeMessage(Header.default(), [], []))
                await session.send_request(init)
                request_message = init if duplicate_init else FuzzerMessage(refine_bundle=refine_request)
                session.writer.write(request_message.fuzzer_encode())
                await session.writer.drain()
                assert await asyncio.wait_for(session.reader.read(), timeout=2) == b''
                await session.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_trace_runner_reconnects_for_separate_chains(target, tmp_path, monkeypatch):
    from pyjamaz import cli

    monkeypatch.setattr(cli, 'setup_logging', lambda *_: None)
    initial = [(MARKER, bytes(4))]
    posterior = [(MARKER, (1).to_bytes(4, 'little'))]
    pre_state = StateDump(PatriciaMerkleTrie(initial).root(), initial)
    post_state = StateDump(PatriciaMerkleTrie(posterior).root(), posterior)
    genesis = Header.default()
    header = Header.default()
    header.parent, header.timeslot = genesis.hash, 1
    for name in ('first', 'second'):
        directory = tmp_path / name
        directory.mkdir()
        (directory / 'genesis.bin').write_bytes(TraceGenesis(genesis, pre_state).to_jam_bytes().to_bytes())
        trace = Trace(pre_state, Block(header, Extrinsic.default()), post_state)
        (directory / '00000001.bin').write_bytes(trace.to_jam_bytes().to_bytes())

    async def run():
        server = await asyncio.start_unix_server(target._handle_client, path=target.path)
        try:
            result = await CliRunner().invoke(cli.main, [
                'fuzzer', 'traces', str(tmp_path), '--socket-path', target.path,
            ])
            assert result.exit_code == 0, result.output
            assert target.app.state_storage.get(MARKER) == posterior[0][1]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
