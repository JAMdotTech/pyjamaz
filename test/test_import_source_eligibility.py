"""Runtime admission of known import roots, before the pure Xi calculation."""

import asyncio
from types import SimpleNamespace

import pytest

from pyjamaz.availability import DataUnavailable, ImportedSegment, availability_spec
from pyjamaz.bundle import encode_bundle
from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import ImportSegment, ValidatorData, WorkReport
from test.test_runtime_refinement import package, runtime, submit


def known_history(runtime, root):
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
        SimpleNamespace(hash=b's' * 32, exports_root=root),
    ])]


@pytest.mark.parametrize('route', ['bundle', 'complete_exports', 'individual_import'])
def test_valid_proof_without_known_source_never_reaches_refine(runtime, route):
    segment = b'x' * 4104
    root = ConstantDepthMerkleTree([segment]).root()
    value = package(imports=[ImportSegment.from_segment_root(root, 0)])
    store = runtime.app.d3l_store
    if route == 'complete_exports':
        store.store_segments(D3LEntry(root, [segment]))
    elif route == 'individual_import':
        store.store_import(root, 0, ImportedSegment(segment, ()))
    bundle = encode_bundle(value, [], [segment], [[]]) if route == 'bundle' else None
    runtime.pipeline.add_work_package(value, [], bundle=bundle)
    item = runtime.pipeline._pending_work_packages[value.hash()]
    before = store.storage_engine.as_dict()
    with pytest.raises(DataUnavailable, match='source'):
        asyncio.run(runtime.pipeline._refine_work_package(item))
    assert runtime.invocations == runtime.signed == []
    assert store.storage_engine.as_dict() == before


def test_recent_report_allows_supplied_import_without_local_storage(runtime):
    segment = b'x' * 4104
    root = ConstantDepthMerkleTree([segment]).root()
    known_history(runtime, root)
    runtime.app.d3l_store = None
    value = package(imports=[ImportSegment.from_segment_root(root, 0)])
    runtime.pipeline.add_work_package(value, [], bundle=encode_bundle(value, [], [segment], [[]]))
    item = runtime.pipeline._pending_work_packages[value.hash()]
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.status.Reported
    assert runtime.invocations[-1]['work_items_import_segments'] == [[segment]]


def test_local_computed_report_remains_known_after_store_restart_and_queue_clear(runtime):
    async def run():
        first = package(b'local source')
        source_item = submit(runtime, first)
        await runtime.pipeline._refine_work_package(source_item)
        root = source_item.work_report.package_spec.exports_root
        runtime.pipeline._pending_work_packages.clear()
        runtime.app.d3l_store = DataAvailabilityStore(runtime.app.d3l_store.storage_engine)
        assert runtime.app.working_state.recent_history.recent_blocks == []
        second = submit(runtime, package(b'consumer', [ImportSegment.from_segment_root(root, 1)]))
        await runtime.pipeline._refine_work_package(second)
        assert second.status.Reported
        assert runtime.invocations[-1]['work_items_import_segments'] == [[b'b' * 4104]]

    asyncio.run(run())


@pytest.mark.parametrize('canonical', [True, False])
def test_retained_chain_source_eligibility_follows_branch_without_an_age_cutoff(runtime, canonical):
    segment = b'x' * 4104
    spec = availability_spec(b's' * 32, b'source bundle', [segment], 6)
    value = package(imports=[ImportSegment.from_segment_root(spec.exports_root, 0)])
    report = WorkReport(spec, value.context, 0, bytes(32), 0, b'', {}, [])
    validators = [ValidatorData(bytes(32), bytes([i]) * 32, bytes(144), bytes(128)) for i in range(6)]
    store = runtime.app.d3l_store
    store.register_source(AvailabilitySource(report, validators, validators[:2], b'h' * 32, 0))
    runtime.app.working_state.timeslot.number = 10_000_000
    runtime.app.runtime = SimpleNamespace(availability=SimpleNamespace(
        source_for=lambda **lookup: store.source_for(**lookup, canonical=lambda _: canonical),
    ))
    runtime.pipeline.add_work_package(value, [], bundle=encode_bundle(value, [], [segment], [[]]))
    item = runtime.pipeline._pending_work_packages[value.hash()]
    if canonical:
        asyncio.run(runtime.pipeline._refine_work_package(item))
        assert item.status.Reported
    else:
        with pytest.raises(DataUnavailable, match='source'):
            asyncio.run(runtime.pipeline._refine_work_package(item))
        assert runtime.invocations == runtime.signed == []
