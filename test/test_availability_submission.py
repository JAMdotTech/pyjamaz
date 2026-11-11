"""The staged CE facade validates full B(p,l) before queue admission."""

import asyncio
from types import SimpleNamespace

import pytest

from pyjamaz.availability import BundleData, DataUnavailable
from pyjamaz.bundle import decode_bundle
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import ImportSegment, WorkItemExtrinsic
from pyjamaz.runtime.availability import AvailabilityRuntime
from pyjamaz.transport.jamnp_messages import encode_import_proofs
from test.test_runtime_refinement import runtime, package


def staged(runtime):
    availability = AvailabilityRuntime(runtime.app)
    runtime.app.runtime = SimpleNamespace(availability=availability, refine_pipeline=runtime.pipeline)
    return availability


def test_ce133_facade_retains_bundle_and_authorization_for_requested_core(runtime):
    availability = staged(runtime)
    value = package()
    blob = b'extrinsic'
    value.items[0].extrinsic = [WorkItemExtrinsic(blake2b_256_hash(blob), len(blob))]

    async def submit():
        context = await availability.authorize_submission(bytes(32), 0, value, {})
        await availability.complete_submission(context, 133, [blob])
        item = runtime.pipeline._pending_work_packages[value.hash()]
        assert item.core_index == 0 and item.authorization_context is context.authorization
        assert decode_bundle(item.bundle).extrinsics == [blob]
        await runtime.pipeline._refine_work_package(item)
        assert item.work_report.core_index == 0

    asyncio.run(submit())


def test_ce146_facade_checks_tagged_imports_and_preserves_complete_bundle(runtime):
    availability = staged(runtime)
    exports = [b'a' * 4104, b'b' * 4104]
    tree = ConstantDepthMerkleTree(exports)
    source_hash = b'p' * 32
    value = package(imports=[ImportSegment.from_work_package_hash(source_hash, 1)])
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
        SimpleNamespace(hash=source_hash, exports_root=tree.root()),
    ])]

    async def submit():
        context = await availability.authorize_submission(bytes(32), 0, value, {source_hash: tree.root()})
        await availability.complete_submission(context, 146, [b'', exports[1], encode_import_proofs([tree.trace(1)])])
        item = runtime.pipeline._pending_work_packages[value.hash()]
        expected = BundleData.from_parts(value, [], [exports[1]], [tree.trace(1)]).assemble_bundle(value, context.mappings)
        assert item.bundle == expected
        assert runtime.app.d3l_store.storage_engine.as_dict() == {}
        await runtime.pipeline._refine_work_package(item)
        assert item.work_report.segment_root_lookup == {source_hash: tree.root()}

    asyncio.run(submit())


@pytest.mark.parametrize('payload', [[b''], [b'bad', b''], [b'', b'', b'\x00']])
def test_malformed_staged_payload_never_enters_queue_or_verified_storage(runtime, payload):
    availability = staged(runtime)
    value = package()

    async def submit():
        context = await availability.authorize_submission(bytes(32), 0, value, {})
        with pytest.raises((ProcessWorkpackageError, ValueError)):
            await availability.complete_submission(context, 146, payload)
        assert runtime.pipeline._pending_work_packages == {}
        assert runtime.app.d3l_store.storage_engine.as_dict() == {}

    asyncio.run(submit())


def test_stale_submission_restarts_before_payload_verification(runtime, monkeypatch):
    availability = staged(runtime)
    value = package()

    async def submit():
        context = await availability.authorize_submission(bytes(32), 0, value, {})
        runtime.app.working_state.state_root = b'n' * 32
        monkeypatch.setattr(BundleData, 'from_parts', lambda *_: pytest.fail('stale payload was processed'))
        with pytest.raises(DataUnavailable, match='stale'):
            await availability.complete_submission(context, 133, [b''])
        assert runtime.pipeline._pending_work_packages == {}

    asyncio.run(submit())
