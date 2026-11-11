"""Recover imports locally, then consume them through the real refine PVM."""

import asyncio
from types import SimpleNamespace

import pytest
from jamcodec.types import Bytes, U32, Vec

from pyjamaz.availability import availability_spec, paged_proof_segments, recover_import
from pyjamaz.d3l import DataAvailabilityStore
from pyjamaz.erasure import encode_blob, erasure_data_shards
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import Credential, ImportSegment, RefinementContext, WorkItem, WorkPackage
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.pvm.constants import Opcode
from pyjamaz.pvm.types import PVMCode
from pyjamaz.runtime.pipelines.refine import RefinePipeline
from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_preimage_availability
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


def load(register, value):
    return bytes((Opcode.load_imm.value, register)) + value.to_bytes(4, 'little')


def program_preimage(instructions, heap_pages=0):
    raw = b''.join(instructions)
    starts = [bit for instruction in instructions
              for bit in [True] + [False] * (len(instruction) - 1)]
    code = PVMCode(0, 0, len(raw), [], raw, starts).to_jam_bytes().to_bytes()
    # GP-0.8.0-eq:A.42: no initial data, z heap pages and one stack page.
    return (Bytes.encode(b'').to_bytes() + bytes(6) + heap_pages.to_bytes(2, 'little')
            + (4096).to_bytes(3, 'little') + len(code).to_bytes(4, 'little') + code)


def pipeline(services, store, source_hash, exports_root):
    app = SimpleNamespace(
        working_state=SimpleNamespace(
            services=services, state_root=b's' * 32, timeslot=SimpleNamespace(number=1),
            validator_pool=SimpleNamespace(validators=[SimpleNamespace(ed25519=bytes([i]) * 32)
                                                       for i in range(6)]),
            recent_history=SimpleNamespace(recent_blocks=[SimpleNamespace(
                reported=[SimpleNamespace(hash=source_hash, exports_root=exports_root)],
            )]),
        ),
        d3l_store=store, pubsub=None, get_core_assigment=lambda: 0,
        retrieve_block_hash=lambda _: b'h' * 32,
        block_context=SimpleNamespace(guarantor_assignments=[]),
        config=SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=bytes(32)))),
    )

    async def sign(report):
        return Credential(0, bytes(64))

    app.create_guarantee_signature = sign
    return RefinePipeline(app)


@pytest.mark.parametrize('selector', [5, 6])
@pytest.mark.parametrize('proof_route', ['direct', 'page'])
def test_recovered_imports_match_complete_exports_in_real_refine(selector, proof_route):
    validator_count = 6
    source_hash = b'p' * 32
    exports = [index.to_bytes(4, 'little') * (EC_SEGMENT_SIZE // 4) for index in range(65)]
    tree = ConstantDepthMerkleTree(exports)
    spec = availability_spec(source_hash, b'source bundle', exports, validator_count)
    pages = paged_proof_segments(exports)
    complete_store = DataAvailabilityStore(InMemoryStorageEngine())
    complete_store.store_segments(D3LEntry(spec.exports_root, exports))
    recovered_store = DataAvailabilityStore(InMemoryStorageEngine())

    def parity_shards(data):
        shards = encode_blob(validator_count, data)
        return {index: shards[index] for index in range(erasure_data_shards(validator_count), validator_count)}

    for index in (0, 1, 2, 64):
        proof = ({'justification': tree.trace(index)} if proof_route == 'direct' else
                 {'proof_page_shards': parity_shards(pages[index // 64])})
        imported = recover_import(spec, index, parity_shards(exports[index]), **proof)
        recovered_store.store_import(spec.exports_root, index, imported)
    # Only individual imports were retained, without a complete export set or root mapping.
    assert recovered_store.storage_engine.get(spec.exports_root) is None
    assert recovered_store.storage_engine.get(b'package-root:' + source_hash) is None

    output_address = 2 * 2**16
    # GP-0.8.0-sec:B.5 fetch: selector 5 reads another item's segment;
    # selector 6 reads the current item's segment. Both return import index 1.
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
    services = ServicesState(services={})
    services.set_state_storage(StateStorage(state_engine))
    services.pending_changes = PendingChanges()
    package = WorkPackage(0, auth_hash, RefinementContext(
        bytes(32), bytes(32), bytes(32), bytes(32), 0, [],
    ), b'', b'', [
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(spec.exports_root, 0),
            ImportSegment.from_work_package_hash(source_hash, 1),
        ], []),
        WorkItem(0, refine_hash, 1000, 1000, 0, b'', [
            ImportSegment.from_segment_root(spec.exports_root, 2),
            ImportSegment.from_work_package_hash(source_hash, 64),
        ], []),
    ])
    initial_state = state_engine.as_dict()

    async def run(store):
        runtime = pipeline(services, store, source_hash, spec.exports_root)
        runtime.add_work_package(package, [])
        item = runtime._pending_work_packages[package.hash()]
        await runtime._refine_work_package(item)
        assert item.status.Reported
        report = item.work_report
        assert report.auth_output == b'' and report.auth_gas_used > 0
        assert all(result.refine_load.gas_used > 0 for result in report.results)
        assert [result.result.ok for result in report.results] == [
            exports[64] if selector == 5 else exports[1], exports[64],
        ]
        assert report.segment_root_lookup == {source_hash: spec.exports_root}
        return report.to_jam_bytes().to_bytes(), store.storage_engine.get(b'bundle:' + package.hash())

    assert asyncio.run(run(recovered_store)) == asyncio.run(run(complete_store))
    assert state_engine.as_dict() == initial_state
    assert services.state_storage.transaction == {}
