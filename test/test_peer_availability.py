"""Peer acquisition uses retained source metadata and authenticates recovered imports."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from jamcodec.types import U32, Vec

from pyjamaz import erasure
from pyjamaz.availability import (
    DataUnavailable, ImportedSegment, build_availability_artifacts, segment_shard_justification,
)
from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, valid_validator_count
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import ImportSegment, ValidatorData, WorkItem, WorkPackage, WorkReport
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.pvm.constants import Opcode
from pyjamaz.runtime.availability import AvailabilityRuntime
from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_preimage_availability
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine
from test.test_recovered_import_refine import load, pipeline, program_preimage
from test.test_runtime_refinement import package


def validators(count, offset=0):
    return [ValidatorData(bytes(32), (index + offset).to_bytes(32, 'little'), bytes(144), bytes(128))
            for index in range(count)]


class SourceProtocol:
    """A source that returns real H/E artifacts through the transport's decoded API."""

    def __init__(self, source, artifacts, exports):
        self.source, self.artifacts, self.exports = source, artifacts, exports
        self.calls = []
        self.complete = False
        self.corrupt_ordinary = False

    async def request_segments(self, peer, root, indices):
        self.calls.append(('complete', peer.ed25519, root, tuple(indices)))
        if not self.complete:
            raise DataUnavailable('complete exports not retained')
        tree = ConstantDepthMerkleTree(self.exports)
        return [ImportedSegment(self.exports[index], tuple(tree.trace(index))) for index in indices]

    async def request_segment_shards(self, peer, spec, shard_index, indices, *, proven):
        self.calls.append(('coded', peer.ed25519, spec, shard_index, tuple(indices), proven))
        row = self.artifacts.shards[shard_index]
        values = [(row.segment_shards[index], segment_shard_justification(row, index) if proven else ())
                  for index in indices]
        if self.corrupt_ordinary and not proven:
            return [(bytes([chunk[0] ^ 1]) + chunk[1:], proof) for chunk, proof in values]
        return values

    async def request_validator_shard(self, peer, spec, index):
        self.calls.append(('assigned', peer.ed25519, spec, index))
        return self.artifacts.shards[index]


@pytest.fixture
def peer_runtime(monkeypatch):
    # Exercise historical 9-validator reports even under the Tiny node profile.
    monkeypatch.setattr(erasure, 'valid_validator_count',
                        lambda count: valid_validator_count(count, core_count=341))

    def make(*, validator_count=6, export_count=65):
        exports = [(index + 1).to_bytes(4, 'little') * (EC_SEGMENT_SIZE // 4)
                   for index in range(export_count)]
        artifacts = build_availability_artifacts(b'p' * 32, b'source bundle', exports, validator_count)
        report = WorkReport(artifacts.spec, package().context, 1, bytes(32), 0, b'', {}, [])
        original = validators(validator_count)
        source = AvailabilitySource(report, original, original[:2], b'b' * 32, 1)
        store = DataAvailabilityStore(InMemoryStorageEngine())
        store.register_source(source)
        protocol = SourceProtocol(source, artifacts, exports)
        active = {source.registered_block}
        app = SimpleNamespace(
            d3l_store=store, protocol=protocol,
            state_storage=SimpleNamespace(block_hash=source.registered_block),
            working_state=SimpleNamespace(validator_pool=SimpleNamespace(validators=validators(6, 100))),
            config=SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=original[2].ed25519))),
        )
        runtime = AvailabilityRuntime(app)
        runtime.canonical = active.__contains__
        return SimpleNamespace(runtime=runtime, source=source, artifacts=artifacts, exports=exports,
                               protocol=protocol, store=store, active=active, app=app)

    return make


def test_complete_segments_are_verified_before_caching_and_coded_requests(peer_runtime):
    case = peer_runtime()
    original = case.protocol.request_segments
    case.protocol.complete = True

    async def request(peer, *args):
        values = await original(peer, *args)
        if peer == case.source.guarantors[0]:
            return [replace(values[0], segment=bytes(EC_SEGMENT_SIZE))]
        return values

    case.protocol.request_segments = request
    imported = asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 64))
    assert imported.segment == case.exports[64]
    assert case.store.retrieve_import(case.source.spec.exports_root, 64) == imported
    assert [call[0] for call in case.protocol.calls] == ['complete', 'complete']


def test_bad_ordinary_chunks_retry_proven_historical_set_and_page_index(peer_runtime):
    case = peer_runtime(validator_count=9)
    case.protocol.corrupt_ordinary = True
    imported = asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 64))
    assert imported.segment == case.exports[64]
    coded = [call for call in case.protocol.calls if call[0] == 'coded']
    assert {call[5] for call in coded} == {False, True}
    for _, peer, spec, shard_index, indices, _ in coded:
        assert spec.erasure_shards == 9
        assert indices == (64, 66)
        owner = (shard_index - case.source.report.core_index * erasure.erasure_data_shards(9)) % 9
        assert peer == case.source.validators[owner].ed25519
        assert peer not in {validator.ed25519 for validator in case.app.working_state.validator_pool.validators}


def test_insufficient_data_is_retryable_without_storing_unverified_imports(peer_runtime):
    case = peer_runtime()
    original = case.protocol.request_segment_shards

    async def unavailable(*args, **kwargs):
        raise ConnectionError('peer disconnected')

    case.protocol.request_segment_shards = unavailable
    with pytest.raises(DataUnavailable, match='not enough'):
        asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 0))
    with pytest.raises(DataUnavailable):
        case.store.retrieve_import(case.source.spec.exports_root, 0)
    case.protocol.request_segment_shards = original
    assert asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 0)).segment == case.exports[0]


def test_peer_timeouts_remain_retryable_and_cancel_transport_work(peer_runtime):
    case = peer_runtime()
    case.runtime.REQUEST_TIMEOUT = .01
    cancelled = 0

    async def request(*args, **kwargs):
        nonlocal cancelled
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise

    case.protocol.request_segment_shards = request
    with pytest.raises(DataUnavailable, match='not enough'):
        asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 0))
    # One bounded pass for CE139 and one for CE140, with no task left behind.
    assert cancelled == 2 * case.source.spec.erasure_shards
    assert case.store._active_roots == {}


def test_altered_individual_proof_is_discarded_in_proven_retry(peer_runtime):
    case = peer_runtime()
    case.protocol.corrupt_ordinary = True
    original = case.protocol.request_segment_shards

    async def request(*args, **kwargs):
        values = await original(*args, **kwargs)
        if args[2] == 0 and kwargs['proven']:
            return [(chunk, proof[:-1] + (bytes(len(proof[-1])),)) for chunk, proof in values]
        return values

    case.protocol.request_segment_shards = request
    imported = asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 1))
    assert imported.segment == case.exports[1]
    assert case.store.retrieve_import(case.source.spec.exports_root, 1) == imported


def test_proven_inconsistent_source_commitment_is_rejected_without_a_judgment(peer_runtime):
    case = peer_runtime()
    # A guaranteed report may commit to incompatible erasure and export roots.
    bad_spec = replace(case.source.spec, exports_root=b'!' * 32)
    bad_source = replace(case.source, report=replace(case.source.report, package_spec=bad_spec))
    case.store.register_source(bad_source)
    with pytest.raises(ProcessWorkpackageError, match='proven shards contradict'):
        asyncio.run(case.runtime.acquire_import(bad_spec.exports_root, 0))
    with pytest.raises(DataUnavailable):
        case.store.retrieve_import(bad_spec.exports_root, 0)


def test_branch_change_during_recovery_does_not_publish_import(peer_runtime):
    case = peer_runtime()
    original = case.protocol.request_segment_shards

    async def reorg(*args, **kwargs):
        values = await original(*args, **kwargs)
        case.active.clear()
        return values

    case.protocol.request_segment_shards = reorg
    with pytest.raises(DataUnavailable, match='branch changed'):
        asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 0))
    with pytest.raises(DataUnavailable):
        case.store.retrieve_import(case.source.spec.exports_root, 0)
    assert case.store._active_roots == {}


@pytest.mark.parametrize('proven', [False, True])
def test_package_acquisition_deduplicates_imports_and_reuses_pages(peer_runtime, proven):
    case = peer_runtime()
    case.protocol.corrupt_ordinary = proven
    root, source_hash = case.source.spec.exports_root, case.source.spec.hash
    value = package(imports=[ImportSegment.from_segment_root(root, 0),
                             ImportSegment.from_work_package_hash(source_hash, 1),
                             ImportSegment.from_segment_root(root, 0)])
    asyncio.run(case.runtime.acquire_package_imports(value, {source_hash: root}))
    complete = [call for call in case.protocol.calls if call[0] == 'complete']
    assert [call[3] for call in complete] == [(0,), (0,), (1,), (1,)]
    requests = [call for call in case.protocol.calls if call[0] == 'coded' and call[5] == proven]
    assert any(call[4] == (0, 65) for call in requests)
    assert any(call[4] == (1,) for call in requests)
    assert not any(call[4] == (1, 65) for call in requests)
    assert case.store.retrieve_import(root, 0).segment == case.exports[0]
    assert case.store.retrieve_import(root, 1).segment == case.exports[1]


def test_coded_acquisition_bounds_tasks_and_cancels_surplus(peer_runtime):
    case = peer_runtime()
    original = case.protocol.request_segment_shards
    live = maximum = cancelled = 0

    async def request(*args, **kwargs):
        nonlocal live, maximum, cancelled
        live += 1
        maximum = max(maximum, live)
        try:
            if args[2] == 3:
                await asyncio.Event().wait()
            await asyncio.sleep(0)
            return await original(*args, **kwargs)
        except asyncio.CancelledError:
            cancelled += 1
            raise
        finally:
            live -= 1

    case.protocol.request_segment_shards = request
    imported = asyncio.run(case.runtime.acquire_import(case.source.spec.exports_root, 0))
    assert imported.segment == case.exports[0]
    assert maximum == 4 and live == 0 and cancelled == 1
    assert case.store._active_roots == {}


def test_cancelling_acquisition_cancels_requests_and_releases_retention_hold(peer_runtime):
    case = peer_runtime()
    started = asyncio.Event()
    live = cancelled = 0

    async def request(*args, **kwargs):
        nonlocal live, cancelled
        live += 1
        if live == 4:
            started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise
        finally:
            live -= 1

    case.protocol.request_segment_shards = request

    async def run():
        task = asyncio.create_task(case.runtime.acquire_import(case.source.spec.exports_root, 0))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert cancelled == 4 and live == 0
    assert case.store._active_roots == {}


def test_assigned_acquisition_rejects_valid_row_for_another_index(peer_runtime):
    case = peer_runtime()
    requested = case.runtime.assigned_index(case.source)
    assert requested == 5  # (core 1 * D(6) + validator 2) mod 6.
    original = case.protocol.request_validator_shard

    async def request(peer, spec, index):
        row = await original(peer, spec, index)
        return case.artifacts.shards[0] if peer == case.source.guarantors[0] else row

    case.protocol.request_validator_shard = request
    asyncio.run(case.runtime.acquire_assigned(case.source))
    assert case.runtime.assigned_ready(case.source)
    assert len(case.protocol.calls) == 2


@pytest.mark.parametrize('selector', [5, 6])
def test_peer_imports_reach_real_pvm_fetch_and_match_complete_exports(peer_runtime, selector):
    case = peer_runtime()
    case.protocol.corrupt_ordinary = True
    source_hash, root = case.source.spec.hash, case.source.spec.exports_root
    output_address = 2 * 2**16
    refine_code = program_preimage([
        load(7, output_address), load(8, 0), load(9, EC_SEGMENT_SIZE),
        load(10, selector), load(11, 1), load(12, 1),
        bytes((Opcode.ecalli.value, 2)),
        load(7, output_address), load(8, EC_SEGMENT_SIZE), bytes((Opcode.jump_ind.value, 0)),
    ], heap_pages=2)
    auth_code = program_preimage([load(8, 0), bytes((Opcode.jump_ind.value, 0))])
    auth_hash, refine_hash = map(blake2b_256_hash, (auth_code, refine_code))
    state_engine = InMemoryStorageEngine()
    for code_hash, preimage in ((auth_hash, auth_code), (refine_hash, refine_code)):
        state_engine.put(state_key_constructor_preimage(0, code_hash), preimage)
        state_engine.put(state_key_constructor_preimage_availability(0, code_hash, len(preimage)),
                         Vec(U32).encode([0]).to_bytes())
    services = ServicesState()
    services.set_state_storage(StateStorage(state_engine))
    services.pending_changes = PendingChanges()
    initial_state = state_engine.as_dict()
    value = WorkPackage(0, auth_hash, package().context, b'', b'', [
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(root, 0),
            ImportSegment.from_work_package_hash(source_hash, 1),
        ], []),
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(root, 2),
            ImportSegment.from_work_package_hash(source_hash, 64),
        ], []),
    ])
    complete_store = DataAvailabilityStore(InMemoryStorageEngine())
    complete_store.store_segments(D3LEntry(root, case.exports))

    async def run(store, peer=False):
        execution = pipeline(services, store, source_hash, root)
        if peer:
            execution.app.protocol = case.protocol
            case.runtime.app = execution.app
            execution.app.runtime = SimpleNamespace(availability=case.runtime)
        execution.add_work_package(value, [])
        item = execution._pending_work_packages[value.hash()]
        await execution._refine_work_package(item)
        assert item.status.Reported
        assert [result.result.ok for result in item.work_report.results] == [
            case.exports[64] if selector == 5 else case.exports[1], case.exports[64],
        ]
        return item.work_report.to_jam_bytes().to_bytes(), store.storage_engine.get(b'bundle:' + value.hash())

    assert asyncio.run(run(case.store, peer=True)) == asyncio.run(run(complete_store))
    assert any(call[0] == 'coded' and call[5] for call in case.protocol.calls)
    assert state_engine.as_dict() == initial_state
    assert services.state_storage.transaction == {}
