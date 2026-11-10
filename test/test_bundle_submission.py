import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pyjamaz import refinement as refinement_module
from pyjamaz.availability import BundleData, DataUnavailable
from pyjamaz.bundle import decode_bundle, decode_package, encode_bundle
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import ImportSegment, WorkExecResult, WorkItemExtrinsic
from pyjamaz.refinement import Refinement
from pyjamaz.rpc.rpc import rpcSubmitWorkPackageBundle
from pyjamaz.rpc.ws_client import WebsocketClient
from pyjamaz.runtime.availability import AvailabilityRuntime
from pyjamaz.transport.jamnp_messages import encode_import_proofs
from pyjamaz.utils import base64_encode
from test.test_runtime_refinement import package, runtime


def bundle_case():
    segments = [b'x' * 4104, b'y' * 4104]
    tree = ConstantDepthMerkleTree(segments)
    value = package(imports=[ImportSegment.from_segment_root(tree.root(), 1),
                             ImportSegment.from_segment_root(tree.root(), 0)])
    value.items[0].extrinsic = [WorkItemExtrinsic.from_blob(b'abc')]
    proofs = [tree.trace(1), tree.trace(0)]
    imports = list(reversed(segments))
    return value, imports, proofs


def test_canonical_bundle_matches_gp_assembly():
    value, imports, proofs = bundle_case()
    encoded = encode_bundle(value, [b'abc'], imports, proofs)
    data = BundleData.from_parts(value, [b'abc'], imports, proofs)
    assert encoded == data.assemble_bundle(value, {})
    parts = decode_bundle(encoded)
    assert parts.package == value
    assert parts.extrinsics == [b'abc']
    assert parts.segments == imports and parts.justifications == proofs
    assert decode_package(encoded) == (value, len(value.to_jam_bytes().to_bytes()))


@pytest.mark.parametrize('fault', ['short_package', 'short_data', 'trailing', 'proof_count'])
def test_canonical_decoder_rejects_malformed_bundles(fault):
    value, imports, proofs = bundle_case()
    encoded = encode_bundle(value, [b'abc'], imports, proofs)
    if fault == 'short_package':
        encoded = encoded[:20]
    elif fault == 'short_data':
        encoded = encoded[:-1]
    elif fault == 'trailing':
        encoded += b'!'
    else:
        offset = len(value.to_jam_bytes().to_bytes()) + 3 + 2 * 4104
        encoded = encoded[:offset] + b'\x80\x01' + encoded[offset + 1:]
    with pytest.raises(ValueError):
        decode_bundle(encoded)


def test_representation_decoder_preserves_invalid_semantics_for_authorized_validation():
    value, imports, proofs = bundle_case()
    encoded = encode_bundle(value, [b'xyz'], imports, proofs)
    assert decode_bundle(encoded).extrinsics == [b'xyz']
    with pytest.raises(ProcessWorkpackageError, match='extrinsic hash'):
        BundleData.from_parts(value, [b'xyz'], imports, proofs)


def test_client_and_server_preserve_the_complete_bundle_and_core(runtime):
    value, imports, proofs = bundle_case()
    client = WebsocketClient('ws://unused')
    client._send_and_wait = AsyncMock()
    asyncio.run(client.submitWorkPackageBundle(1, value, imports, [b'abc'], proofs))
    method, params = client._send_and_wait.call_args.args
    assert method == 'submitWorkPackageBundle'
    assert params == [1, base64_encode(encode_bundle(value, [b'abc'], imports, proofs))]
    app = SimpleNamespace(add_work_package=runtime.pipeline.add_work_package)
    rpcSubmitWorkPackageBundle(app, params)
    item = runtime.pipeline._pending_work_packages[value.hash()]
    assert item.bundle == encode_bundle(value, [b'abc'], imports, proofs)
    assert item.core_index == 1


def test_client_requires_proofs_for_imports():
    value, imports, _ = bundle_case()
    client = WebsocketClient('ws://unused')
    client._send_and_wait = AsyncMock()
    with pytest.raises(ValueError, match='justifications'):
        asyncio.run(client.submitWorkPackageBundle(0, value, imports, [b'abc']))
    client._send_and_wait.assert_not_called()


def test_client_without_imports_remains_compatible():
    value = package()
    client = WebsocketClient('ws://unused')
    client._send_and_wait = AsyncMock()
    asyncio.run(client.submitWorkPackageBundle(0, value, [], []))
    assert client._send_and_wait.call_args.args == (
        'submitWorkPackageBundle', [0, base64_encode(value.to_jam_bytes().to_bytes())],
    )


def test_complete_bundle_refines_without_preexisting_import_storage(runtime):
    value, imports, proofs = bundle_case()
    runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
        SimpleNamespace(hash=b's' * 32, exports_root=value.items[0].import_segments[0].tree_root),
    ])]
    runtime.app.d3l_store = None
    encoded = encode_bundle(value, [b'abc'], imports, proofs)
    runtime.pipeline.add_work_package(value, [], core_index=0, bundle=encoded)
    item = runtime.pipeline._pending_work_packages[value.hash()]
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.status.Reported
    assert runtime.invocations[-1]['work_items_import_segments'] == [imports]
    assert runtime.invocations[-1]['extrinsics'] == [[b'abc']]
    assert len(runtime.signed) == 1


def test_unauthorized_bundle_is_rejected_before_payload_decode(runtime, monkeypatch):
    value = package()
    runtime.pipeline.add_work_package(value, [], core_index=0,
                                      bundle=value.to_jam_bytes().to_bytes() + b'garbage')
    monkeypatch.setattr(refinement_module, 'pvm_invoke_is_authorized', lambda *_: SimpleNamespace(
        work_exec_result=WorkExecResult(panic=True), gas_used=1,
    ))

    def unexpected(*_):
        pytest.fail('unauthorized package reached payload decoding')

    monkeypatch.setattr('pyjamaz.runtime.pipelines.refine.decode_bundle', unexpected)
    with pytest.raises(ProcessWorkpackageError, match='Unauthorized'):
        asyncio.run(runtime.pipeline._refine_work_package(runtime.pipeline._pending_work_packages[value.hash()]))
    assert runtime.invocations == []


def test_requested_core_is_not_silently_changed(runtime):
    value = package()
    runtime.pipeline.add_work_package(value, [], core_index=1)
    item = runtime.pipeline._pending_work_packages[value.hash()]
    asyncio.run(runtime.pipeline._refine_work_package(item))
    assert item.status.Reportable
    assert runtime.invocations == runtime.signed == []


def test_staged_authorization_runs_once_for_same_snapshot(runtime, monkeypatch):
    value = package()
    calls = []
    original = Refinement.authorize

    def authorize(self, *args):
        calls.append(args)
        return original(self, *args)

    monkeypatch.setattr(Refinement, 'authorize', authorize)

    async def run():
        context = await runtime.pipeline.authorize_submission(0, value)
        runtime.pipeline.add_work_package(value, [], core_index=0, authorization_context=context)
        item = runtime.pipeline._pending_work_packages[value.hash()]
        await runtime.pipeline._refine_work_package(item)
        assert item.status.Reported

    asyncio.run(run())
    assert len(calls) == 1


def test_stale_staged_authorization_is_not_reused(runtime, monkeypatch):
    value = package()
    calls = []
    original = Refinement.authorize

    def authorize(self, *args):
        calls.append(args)
        return original(self, *args)

    monkeypatch.setattr(Refinement, 'authorize', authorize)

    async def run():
        context = await runtime.pipeline.authorize_submission(0, value)
        context.head_root = b'old' * 10 + b'!!'
        runtime.pipeline.add_work_package(value, [], core_index=0, authorization_context=context)
        await runtime.pipeline._refine_work_package(runtime.pipeline._pending_work_packages[value.hash()])

    asyncio.run(run())
    assert len(calls) == 2


@pytest.mark.parametrize('kind', [133, 146])
def test_staged_network_payloads_queue_complete_bundle_and_reuse_authorization(runtime, monkeypatch, kind):
    if kind == 146:
        value, imports, proofs = bundle_case()
        runtime.app.working_state.recent_history.recent_blocks = [SimpleNamespace(reported=[
            SimpleNamespace(hash=b's' * 32, exports_root=value.items[0].import_segments[0].tree_root),
        ])]
        payloads = [b'abc', b''.join(imports), encode_import_proofs(proofs)]
    else:
        value, imports, proofs = package(), [], []
        value.items[0].extrinsic = [WorkItemExtrinsic.from_blob(b'abc')]
        payloads = [b'abc']
    availability = AvailabilityRuntime(runtime.app)
    runtime.app.runtime = SimpleNamespace(refine_pipeline=runtime.pipeline, availability=availability)
    calls = []
    authorize = Refinement.authorize

    def counted(self, *args):
        calls.append(args)
        return authorize(self, *args)

    monkeypatch.setattr(Refinement, 'authorize', counted)

    async def run():
        context = await availability.authorize_submission(bytes(32), 0, value, {})
        assert await availability.complete_submission(context, kind, payloads) == []
        item = runtime.pipeline._pending_work_packages[value.hash()]
        assert item.bundle == encode_bundle(value, [b'abc'], imports, proofs)
        await runtime.pipeline._refine_work_package(item)
        assert item.status.Reported

    asyncio.run(run())
    assert len(calls) == 1
    assert runtime.invocations[-1]['extrinsics'] == [[b'abc']]
    assert runtime.invocations[-1]['work_items_import_segments'] == [imports]


def test_staged_completion_rejects_stale_snapshot_before_payload_validation(runtime, monkeypatch):
    value = package()
    availability = AvailabilityRuntime(runtime.app)
    runtime.app.runtime = SimpleNamespace(refine_pipeline=runtime.pipeline, availability=availability)

    def unexpected(*_):
        pytest.fail('stale submission reached payload validation')

    monkeypatch.setattr(BundleData, 'from_parts', unexpected)

    async def run():
        context = await availability.authorize_submission(bytes(32), 0, value, {})
        context.authorization.head_root = b'old' * 10 + b'!!'
        with pytest.raises(DataUnavailable, match='stale'):
            await availability.complete_submission(context, 133, [b'invalid data'])

    asyncio.run(run())
    assert runtime.pipeline._pending_work_packages == {}
    assert runtime.invocations == []
