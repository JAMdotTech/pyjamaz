import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from pyjamaz import refinement as refinement_module, graypaper_constants as gp_const
from pyjamaz.availability import (
    BundleData, DataUnavailable, ImportedSegment, availability_spec, recover_import,
    validate_work_package, zero_pad,
)
from pyjamaz.d3l import DataAvailabilityStore
from pyjamaz.erasure import encode_blob, encode_chunks, erasure_data_shards
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import (
    Credential, ImportSegment, RefinementContext, WorkExecResult, WorkItem, WorkPackage,
)
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.refinement import Refinement
from pyjamaz.runtime.pipelines import refine
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import FileStorageEngine, InMemoryStorageEngine


def package(payload=b'package', imports=None):
    return WorkPackage(0, bytes(32), RefinementContext(
        bytes(32), bytes(32), bytes(32), bytes(32), 0, [],
    ), b'', b'', [WorkItem(0, bytes(32), 1000, 1000, 2, payload, imports or [], [])])


@pytest.fixture
def runtime(monkeypatch):
    engine = InMemoryStorageEngine()
    services = ServicesState()
    services.set_state_storage(StateStorage(engine))
    services.pending_changes = PendingChanges()
    app = SimpleNamespace(
        working_state=SimpleNamespace(
            services=services, state_root=bytes(32), timeslot=SimpleNamespace(number=3),
            validator_pool=SimpleNamespace(validators=[SimpleNamespace(ed25519=bytes([i]) * 32) for i in range(6)]),
            recent_history=SimpleNamespace(recent_blocks=[]),
        ),
        d3l_store=DataAvailabilityStore(InMemoryStorageEngine()), pubsub=None,
        get_core_assigment=lambda: 0, retrieve_block_hash=lambda _: b'h' * 32,
        block_context=SimpleNamespace(guarantor_assignments=[]),
        config=SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=bytes(32)))),
    )
    signed, invocations = [], []

    async def sign(report):
        signed.append(report)
        return Credential(0, bytes(64))

    app.create_guarantee_signature = sign
    monkeypatch.setattr(WorkPackage, 'set_authorization_code', lambda *_: None)
    monkeypatch.setattr(refinement_module, 'pvm_invoke_is_authorized', lambda *_: SimpleNamespace(
        work_exec_result=WorkExecResult(ok=b'auth'), gas_used=1,
    ))

    def invoke(**kwargs):
        invocations.append(kwargs)
        return SimpleNamespace(work_exec_result=WorkExecResult(ok=b'result'), gas_used=2,
                               export_segments=[b'a' * 4104, b'b' * 4104])

    monkeypatch.setattr(refinement_module, 'pvm_invoke_refine', invoke)
    pipeline = refine.RefinePipeline(app)
    return SimpleNamespace(app=app, pipeline=pipeline, signed=signed, invocations=invocations, engine=engine)


def submit(runtime, value):
    runtime.pipeline.add_work_package(value, [])
    return runtime.pipeline._pending_work_packages[value.hash()]


def test_gp_interfaces_return_the_equations_results(runtime):
    value = package()
    data = BundleData()
    # B(p,l) returns exactly the bytes, while Xi(p,c,l,v) returns exactly the report.
    bundle = data.assemble_bundle(value, {})
    assert bundle == value.to_jam_bytes().to_bytes()
    execution = Refinement(runtime.app.working_state.services.snapshot(), data)
    report = execution.compute_work_report(value, 0, {}, 6)
    # A takes the hash, rather than the work-package or a caller-supplied exports root.
    assert report.package_spec == availability_spec(value.hash(), bundle, execution.exported_segments, 6)
    assert report.package_spec.length == len(bundle)
    assert execution.bundle == bundle
    assert runtime.signed == []
    assert runtime.app.d3l_store.storage_engine.as_list() == []


def test_runtime_resolves_tagged_and_duplicate_imports_from_retained_exports(runtime):
    async def run():
        first = package(b'first')
        first_item = submit(runtime, first)
        await runtime.pipeline._refine_work_package(first_item)
        root = first_item.work_report.package_spec.exports_root
        assert runtime.app.d3l_store.segment_root_for_package(first.hash()) == root
        assert runtime.app.d3l_store.storage_engine.get(b'bundle:' + first.hash())
        # Clear the queue cache to exercise the persisted mapping, not the in-memory report.
        runtime.pipeline._pending_work_packages.clear()
        second = package(b'second', [
            ImportSegment.from_work_package_hash(first.hash(), 1),
            ImportSegment.from_segment_root(root, 0),
            ImportSegment.from_work_package_hash(first.hash(), 1),
        ])
        second_item = submit(runtime, second)
        await runtime.pipeline._refine_work_package(second_item)
        assert second_item.work_report.segment_root_lookup == {first.hash(): root}
        assert runtime.invocations[-1]['work_items_import_segments'] == [[b'b' * 4104, b'a' * 4104, b'b' * 4104]]
        assert len(runtime.signed) == 2
        assert second_item.status.Reported.reported_in.slot == 3

    asyncio.run(run())


def test_runtime_uses_recent_history_mapping_for_external_package(runtime):
    source_hash = b's' * 32
    from pyjamaz.merkle import ConstantDepthMerkleTree

    exports = [b'x' * 4104, b'y' * 4104]
    root = ConstantDepthMerkleTree(exports).root()
    runtime.app.d3l_store.store_segments(D3LEntry(root, exports))
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(
        reported=[SimpleNamespace(hash=source_hash, exports_root=root)],
    )]
    value = package(imports=[ImportSegment.from_work_package_hash(source_hash, 0)])
    item = submit(runtime, value)
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.work_report.segment_root_lookup == {source_hash: root}


def test_recovered_cached_and_complete_exports_make_identical_reports(runtime):
    exports = [bytes([index + 1]) * 4104 for index in range(3)]
    tree = ConstantDepthMerkleTree(exports)
    root = tree.root()
    spec = availability_spec(b's' * 32, b'source bundle', exports, 6)
    mappings = {spec.hash: root}
    value = package(imports=[
        ImportSegment.from_work_package_hash(spec.hash, 2),
        ImportSegment.from_segment_root(root, 0),
        ImportSegment.from_work_package_hash(spec.hash, 2),
    ])
    second = deepcopy(value.items[0])
    second.import_segments = list(reversed(value.items[0].import_segments[:2]))
    value.items.append(second)
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(
        reported=[SimpleNamespace(hash=spec.hash, exports_root=root)],
    )]
    item = submit(runtime, value)
    store = runtime.app.d3l_store
    store.store_segments(D3LEntry(root, exports))

    def compute():
        data = runtime.pipeline._bundle_data(value, mappings)
        execution = Refinement(runtime.app.working_state.services.snapshot(), data)
        report = execution.compute_work_report(value, 0, mappings, 6)
        return report.to_jam_bytes().to_bytes(), execution.bundle

    expected = compute()
    shards = encode_blob(6, exports[2])
    recovered = recover_import(spec, 2, {i: shards[i] for i in (3, 4, 5)},
                               justification=tree.trace(2))
    store.store_import(root, 2, recovered)
    # One cached segment, with the other supplied by the complete-export fallback.
    assert compute() == expected
    store.store_import(root, 0, ImportedSegment(exports[0], tuple(tree.trace(0))))
    store.storage_engine.delete(root)
    assert compute() == expected
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.work_report.to_jam_bytes().to_bytes() == expected[0]
    expected_imports = [[exports[2], exports[0], exports[2]], [exports[0], exports[2]]]
    assert runtime.invocations[-1]['work_items_import_segments'] == expected_imports


def test_corrupt_individual_import_falls_back_to_complete_exports(runtime):
    exports = [b'x' * 4104, b'y' * 4104]
    tree = ConstantDepthMerkleTree(exports)
    root = tree.root()
    store = runtime.app.d3l_store
    store.store_import(root, 1, ImportedSegment(exports[1], tuple(tree.trace(1))))
    key = next(iter(store.storage_engine.as_dict()))
    store.storage_engine.put(key, b'corrupt')
    store.store_segments(D3LEntry(root, exports))
    value = package(imports=[ImportSegment.from_segment_root(root, 1)])
    data = runtime.pipeline._bundle_data(value, {})
    assert data.import_segments({}, value.items[0]) == [exports[1]]


@pytest.mark.parametrize('corrupt', [False, True])
def test_worker_retries_disk_import_until_verified_data_is_inserted(runtime, tmp_path, corrupt):
    exports = [b'x' * 4104, b'y' * 4104]
    tree = ConstantDepthMerkleTree(exports)
    root = tree.root()
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
        SimpleNamespace(hash=b's' * 32, exports_root=root),
    ])]
    runtime.app.d3l_store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    store = runtime.app.d3l_store
    if corrupt:
        store.store_import(root, 1, ImportedSegment(exports[1], tuple(tree.trace(1))))
        next(tmp_path.iterdir()).write_bytes(b'corrupt')
    item = submit(runtime, package(imports=[ImportSegment.from_segment_root(root, 1)]))

    async def run():
        worker = asyncio.create_task(runtime.pipeline._refine_worker())
        try:
            await runtime.pipeline._refine_queue.put(item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=2)
            assert item.status.Reportable
            assert runtime.invocations == runtime.signed == []
            store.store_import(root, 1, ImportedSegment(exports[1], tuple(tree.trace(1))))
            await runtime.pipeline._refine_queue.put(item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=2)
            assert item.status.Reported
            assert len(runtime.signed) == 1
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(run())


@pytest.mark.parametrize('corrupt_import', [False, True])
@pytest.mark.parametrize('fault', ['malformed', 'trailing', 'noncanonical', 'root', 'tree'])
def test_worker_retries_corrupt_complete_exports_until_repaired(runtime, tmp_path, corrupt_import, fault):
    exports = [b'x' * 4104, b'y' * 4104]
    tree = ConstantDepthMerkleTree(exports)
    root = tree.root()
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
        SimpleNamespace(hash=b's' * 32, exports_root=root),
    ])]
    runtime.app.d3l_store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    store = runtime.app.d3l_store
    if corrupt_import:
        store.store_import(root, 1, ImportedSegment(exports[1], tuple(tree.trace(1))))
        next(tmp_path.iterdir()).write_bytes(b'corrupt')
    data = D3LEntry(root, exports).to_jam_bytes().to_bytes()
    if fault == 'malformed':
        data = data[:33]
    elif fault == 'trailing':
        data += bytes(1)
    elif fault == 'noncanonical':
        data = data[:32] + b'\x80\x02' + data[33:]
    elif fault == 'root':
        data = bytes(32) + data[32:]
    else:
        data = D3LEntry(root, [b'z' * 4104] * 2).to_jam_bytes().to_bytes()
    store.storage_engine.put(root, data)
    item = submit(runtime, package(imports=[ImportSegment.from_segment_root(root, 1)]))

    async def run():
        worker = asyncio.create_task(runtime.pipeline._refine_worker())
        try:
            await runtime.pipeline._refine_queue.put(item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=2)
            assert item.status.Reportable
            assert runtime.invocations == runtime.signed == []
            store.store_segments(D3LEntry(root, exports))
            await runtime.pipeline._refine_queue.put(item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=2)
            assert item.status.Reported
            assert len(runtime.signed) == 1
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(run())


def test_complete_exports_still_reject_out_of_range_manifest_index(runtime):
    exports = [b'x' * 4104, b'y' * 4104]
    root = ConstantDepthMerkleTree(exports).root()
    runtime.app.d3l_store.store_segments(D3LEntry(root, exports))
    value = package(imports=[ImportSegment.from_segment_root(root, 2)])
    with pytest.raises(ProcessWorkpackageError, match='index out of range'):
        runtime.pipeline._bundle_data(value, {})


@pytest.mark.parametrize('in_progress', ['transaction', 'candidate'])
def test_runtime_waits_for_block_transition_before_taking_snapshot(runtime, in_progress):
    item = submit(runtime, package())
    storage = runtime.app.working_state.services.state_storage
    if in_progress == 'transaction':
        storage.transaction[b'k' * 31] = b'in progress'
    else:
        storage.block_hash = b'c' * 32
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.status.Reportable
    assert runtime.invocations == runtime.signed == []


def test_runtime_signs_only_its_own_credential_outside_solo_mode(runtime, monkeypatch):
    monkeypatch.setattr(refine, 'SOLO_MODE', False)
    runtime.app.block_context.guarantor_assignments = [SimpleNamespace(
        validator_ed25519=b'z' * 32, core_index=0,
    )]

    async def other_signature(*_):
        pytest.fail("runtime attempted to sign for another validator")

    runtime.app.create_guarantee_signature_for_validator = other_signature
    asyncio.run(runtime.pipeline._refine_work_package(submit(runtime, package())))
    assert len(runtime.signed) == 1


@pytest.mark.parametrize('change', ['branch', 'validators', 'core'])
def test_changed_runtime_view_discards_result_and_keeps_inputs_for_retry(runtime, monkeypatch, change):
    value = package()
    item = submit(runtime, value)
    runtime.engine.put(b'k' * 31, b'captured')
    original_state = runtime.app.working_state
    reports = []

    async def dispatch(compute, *args):
        runtime.engine.put(b'k' * 31, b'changed')
        assert compute.__self__.services.state_storage.get(b'k' * 31) == b'captured'
        reports.append(compute(*args))
        if change == 'branch':
            runtime.app.working_state = deepcopy(original_state)
            runtime.app.working_state.state_root = b'z' * 32
        elif change == 'validators':
            original_state.validator_pool.validators[0].ed25519 = b'z' * 32
        else:
            runtime.app.get_core_assigment = lambda: 1
        return reports[-1]

    monkeypatch.setattr(refine.anyio.to_thread, 'run_sync', dispatch)
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert reports[0].package_spec.erasure_shards == 6
    assert item.status.Reportable is not None
    assert item.work_report is None and item.signatures == []
    assert runtime.signed == []
    assert runtime.app.d3l_store.storage_engine.as_list() == []
    assert value.hash() in runtime.pipeline._work_package_extrinsics.extrinsic_data


def test_worker_rejects_one_package_then_processes_the_next(runtime):
    invalid = package(b'invalid')
    invalid.items = []
    bad_item, good_item = submit(runtime, invalid), submit(runtime, package(b'valid'))

    async def run():
        worker = asyncio.create_task(runtime.pipeline._refine_worker())
        try:
            await runtime.pipeline._refine_queue.put(bad_item)
            await runtime.pipeline._refine_queue.put(good_item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=5)
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(run())
    assert bad_item.status.Failed
    assert good_item.status.Reported
    assert len(runtime.signed) == 1


def test_unavailable_dependency_retries_without_killing_worker(runtime):
    item = submit(runtime, package(imports=[ImportSegment.from_work_package_hash(b'x' * 32, 0)]))

    async def run():
        worker = asyncio.create_task(runtime.pipeline._refine_worker())
        try:
            await runtime.pipeline._refine_queue.put(item)
            await asyncio.wait_for(runtime.pipeline._refine_queue.join(), timeout=2)
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(run())
    assert item.status.Reportable
    assert runtime.invocations == runtime.signed == []


def test_services_snapshot_detaches_storage_and_pending_preimages(runtime):
    services = runtime.app.working_state.services
    key = (0, b'p' * 32)
    runtime.engine.put(b'k' * 31, b'old')
    services.pending_changes.preimages[key] = b'pending'
    snapshot = services.snapshot()
    runtime.engine.put(b'k' * 31, b'new')
    services.pending_changes.preimages[key] = b'changed'
    assert snapshot.state_storage.get(b'k' * 31) == b'old'
    assert snapshot.pending_changes.preimages[key] == b'pending'


def test_erasure_signature_dimensions_and_padding():
    assert erasure_data_shards(6) == 3
    data = b'abc'
    padded = zero_pad(6, data)
    assert padded == b'abc' + bytes(3)
    assert zero_pad(6, padded) == padded
    assert len(encode_chunks(6, 1, padded)) == 6
    assert encode_chunks(6, 0, b'') == [b''] * 6
    with pytest.raises(ValueError, match='dimensions'):
        encode_chunks(6, 1, data)
    with pytest.raises(ValueError, match='piece count'):
        encode_chunks(6, -1, b'')


@pytest.mark.parametrize(('field', 'limit'), [
    ('refine_gas_limit', gp_const.GAS_REFINE),
    ('accumulate_gas_limit', gp_const.GAS_ACCUMULATION),
])
@pytest.mark.parametrize('excess', [0, 1])
def test_package_gas_limits_are_inclusive(field, limit, excess):
    value = package()
    value.items.append(deepcopy(value.items[0]))
    setattr(value.items[0], field, limit // 2)
    setattr(value.items[1], field, limit - limit // 2 + excess)
    if excess:
        with pytest.raises(ProcessWorkpackageError, match='gas limits'):
            validate_work_package(value)
    else:
        validate_work_package(value)
