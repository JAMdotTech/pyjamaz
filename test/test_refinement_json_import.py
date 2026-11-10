"""JSON adaptation preserves the reference oracle and malformed execution inputs."""

import asyncio
import json

import pytest
from jamcodec.base import JamBytes
from jamcodec.types import H256, U32, Vec

from pyjamaz.fuzzer.refinement_vectors import import_refinement_vector, load_refinement_vector
from pyjamaz.fuzzer.v1.types import FuzzerMessage, InitializeMessage, RefineBundle
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import TraceGenesis
from pyjamaz.models.common import (
    ImportSegment, RefinementContext, WorkDigest, WorkExecResult, WorkItem,
    WorkItemExtrinsic, WorkPackage, WorkPackageSpec, WorkReport,
)
from pyjamaz.models.state import ServiceAccount, STORAGE_KEY_MAPPING, TimeslotState
from pyjamaz.state.base import (
    state_key_constructor_preimage, state_key_constructor_preimage_availability,
    state_key_constructor_service_account,
)


@pytest.fixture
def vector(tmp_path):
    code = b'reference service code'
    code_hash = blake2b_256_hash(code)
    context = RefinementContext(
        b'a' * 32, b's' * 32, bytes(32), b'l' * 32, 7, [],
        anchor_slot=9, lookup_anchor_state_root=b'k' * 32,
    )
    item = WorkItem(1000, code_hash, 1000, 1000, 0, b'input', [], [])
    package = WorkPackage(0, code_hash, context, b'authorization', b'config', [item])
    # Deliberately disagree with locally computed authorization/hash: adaptation
    # must preserve the supplied oracle, never manufacture a passing report.
    expected = WorkReport(
        WorkPackageSpec(b'p' * 32, 123, b'e' * 32, b'x' * 32, 0, erasure_shards=6),
        context, 1, b'h' * 32, 123456, b'expected auth', {},
        [WorkDigest.from_work_item(item, WorkExecResult(ok=b'reference result'), 123)],
    )
    availability_key = state_key_constructor_preimage_availability(1000, code_hash, len(code))
    availability_value = Vec(U32).encode([0]).to_bytes()
    data = {
        'name': 'reference-test',
        'core_idx': 1,
        'services': {'1000': {
            'service': {
                'code_hash': '0x' + code_hash.hex(), 'balance': 999999,
                'min_item_gas': 123, 'min_memo_gas': 456, 'bytes': 777,
                'items': 2, 'deposit_offset': 12, 'creation_slot': 1,
                'last_accumulation_slot': 2, 'parent_service': 42,
            },
            'data': [{'key': '0x' + availability_key.hex(),
                      'value': '0x' + availability_value.hex()}],
            'preimage_blobs': [{'hash': '0x' + code_hash.hex(), 'blob': '0x' + code.hex()}],
        }},
        'work_package': package.to_json(),
        'bundle': '0x' + package.to_jam_bytes().to_bytes().hex(),
        'expected': {'work_report': expected.to_json(), 'exported_segments': []},
    }
    source = tmp_path / 'reference-test.json'
    source.write_text(json.dumps(data, indent=2) + '\n')
    return source, data, package, expected, code, availability_key, availability_value


def test_import_preserves_source_package_and_complete_expected_report(vector, tmp_path):
    source, _, package, expected, *_ = vector
    original = source.read_bytes()
    destination = tmp_path / 'imported'
    manifest = import_refinement_vector(source, destination)

    assert isinstance(manifest, dict)
    assert json.loads((destination / 'manifest.json').read_text()) == manifest
    assert source.read_bytes() == original
    assert (destination / 'source.json').read_bytes() == original
    assert (destination / 'report.bin').read_bytes() == expected.to_jam_bytes().to_bytes()
    request = RefineBundle.from_jam_bytes(JamBytes((destination / 'refine.bin').read_bytes()))
    assert request.bundle.work_package == package
    assert request.core_index == 1
    assert request.erasure_shards == 6
    assert request.segment_root_lookup == expected.segment_root_lookup
    assert expected.authorizer_hash != package.authorizer_hash()

    for name, codec in [('genesis', TraceGenesis), ('refine', RefineBundle), ('report', WorkReport)]:
        raw = (destination / f'{name}.bin').read_bytes()
        stream = JamBytes(raw)
        decoded = codec.from_jam_bytes(stream)
        assert stream.get_remaining_length() == 0
        assert decoded.to_jam_bytes().to_bytes() == raw


def test_initialization_preserves_supplied_services_without_inventing_authorizer(vector):
    source, _, package, _, code, availability_key, availability_value = vector
    genesis, request, _ = load_refinement_vector(source)
    state = dict(genesis.state.keyvals)
    assert all(key in state for key in STORAGE_KEY_MAPPING)
    assert len(state) == len(genesis.state.keyvals)
    assert PatriciaMerkleTrie(genesis.state.keyvals).root() == genesis.state.state_root
    assert genesis.header.timeslot == package.context.lookup_anchor_slot
    timeslot_key = next(key for key, codec in STORAGE_KEY_MAPPING.items() if codec is TimeslotState)
    assert TimeslotState.from_jam_bytes(JamBytes(state[timeslot_key])).number == genesis.header.timeslot
    assert request.bundle.work_package.context == package.context
    assert state_key_constructor_service_account(0) not in state
    assert state_key_constructor_preimage(0, package.auth_code_hash) not in state
    assert state[state_key_constructor_preimage(1000, package.items[0].code_hash)] == code
    assert state[availability_key] == availability_value
    account = ServiceAccount.from_serialized_bytes(state[state_key_constructor_service_account(1000)])
    assert (account.gas_limit_accumulate, account.gas_limit_on_transfer) == (123, 456)
    assert (account.footprint_storage_bytes, account.footprint_storage_items) == (777, 2)
    assert (account.deposit_offset, account.creation_slot, account.last_accumulation_slot,
            account.parent_service) == (12, 1, 2, 42)


def test_imported_full_state_initializes_real_target(vector, tmp_path):
    from pyjamaz.cli import initialize_app
    from pyjamaz.fuzzer.v1.target import FuzzerTarget

    genesis, _, _ = load_refinement_vector(vector[0])

    async def run():
        app = await initialize_app(read_state=False, storage_engine='memory', pubsub=False)
        target = FuzzerTarget(str(tmp_path / 'unused.sock'), app)
        response = await target.msg_initialize(FuzzerMessage(initialize=InitializeMessage(
            genesis.header, genesis.state.keyvals, [],
        )))
        assert response.state_root == genesis.state.state_root
        assert app.working_state.timeslot.number == genesis.header.timeslot

    asyncio.run(run())


def test_availability_bundle_order_and_invalid_import_proofs_are_preserved(vector):
    source, data, package, expected, *_ = vector
    roots = [b'r' * 32, b't' * 32]
    extrinsics = [b'first extrinsic', b'second extrinsic']
    segments = [b'x' * 4104, b'y' * 4104]
    proofs = [[], [b'z' * 32]]  # Deliberately invalid proofs: the target must reject them.
    package.items = [
        WorkItem(1000, package.auth_code_hash, 1000, 1000, 0, bytes([i]),
                 [ImportSegment.from_segment_root(root, 0)], [WorkItemExtrinsic.from_blob(blob)])
        for i, (root, blob) in enumerate(zip(roots, extrinsics))
    ]
    expected.segment_root_lookup = {b'w' * 32: b'm' * 32}
    data['work_package'] = package.to_json()
    data['expected']['work_report'] = expected.to_json()
    raw = (package.to_jam_bytes().to_bytes() + b''.join(extrinsics) + b''.join(segments)
           + b''.join(Vec(H256).encode(proof).to_bytes() for proof in proofs))
    data['bundle'] = '0x' + raw.hex()
    source.write_text(json.dumps(data))

    _, request, oracle = load_refinement_vector(source)
    assert request.bundle.work_package == package
    assert request.bundle.extrinsics == extrinsics
    assert request.bundle.import_segments == segments
    assert request.bundle.justifications == proofs
    assert request.segment_root_lookup == expected.segment_root_lookup
    assert oracle == expected


@pytest.mark.parametrize('fault', ['trailing', 'truncated', 'package_mismatch', 'invalid_json'])
def test_corrupt_input_is_rejected_without_writing_fixture(vector, tmp_path, fault):
    source, data, *_ = vector
    if fault == 'trailing':
        data['bundle'] += '00'
    elif fault == 'truncated':
        data['bundle'] = data['bundle'][:-2]
    elif fault == 'package_mismatch':
        data['work_package']['items'][0]['payload'] = '0x01'
    source.write_text('{' if fault == 'invalid_json' else json.dumps(data))
    destination = tmp_path / 'invalid-import'
    with pytest.raises(ValueError):
        import_refinement_vector(source, destination)
    assert not destination.exists() or not list(destination.iterdir())


def test_existing_destination_and_source_are_never_overwritten(vector, tmp_path):
    source = vector[0]
    original = source.read_bytes()
    destination = tmp_path / 'existing'
    destination.mkdir()
    sentinel = destination / 'report.bin'
    sentinel.write_bytes(b'keep this report')
    with pytest.raises((ValueError, FileExistsError)):
        import_refinement_vector(source, destination)
    assert sentinel.read_bytes() == b'keep this report'
    assert source.read_bytes() == original
