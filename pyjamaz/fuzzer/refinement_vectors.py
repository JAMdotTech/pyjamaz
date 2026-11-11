"""Import standalone Ξ JSON vectors into binary v1 refinement fixtures.

The source corpus supplies service state, not a chain snapshot. Global state
and the initialization header are deterministic synthetic scaffolding. Package
contexts, authorizer inputs and reference reports are never repaired or executed.
"""

import hashlib
import json
from dataclasses import fields
from pathlib import Path

from pyjamaz.bundle import decode_bundle

from pyjamaz.fuzzer.v1.types import RefineBundle, WorkPackageBundle
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, TraceGenesis
from pyjamaz.models.block import Header
from pyjamaz.models.common import WorkPackage, WorkReport
from pyjamaz.models.state import JamState, ServiceAccount, STORAGE_KEY_MAPPING
from pyjamaz.settings import GP_VERSION, TEST_SUITE
from pyjamaz.state.base import state_key_constructor_preimage, state_key_constructor_service_account


def _hex(value):
    if not isinstance(value, str) or not value.startswith('0x'):
        raise ValueError('expected a 0x-prefixed hex string')
    return bytes.fromhex(value[2:])


def _bundle(package, raw):
    """Decode B(p,l), whose data sequences have manifest-defined lengths."""
    parts = decode_bundle(raw)
    if parts.package != package:
        raise ValueError('bundle work package differs from JSON or is noncanonical')
    # Proof validity and manifest semantics belong to the target, not import.
    return WorkPackageBundle(package, parts.extrinsics, parts.segments, parts.justifications)


def _convert(data):
    package = WorkPackage.from_json(data['work_package'])
    expected = WorkReport.from_json(data['expected']['work_report'])
    request = RefineBundle(data['core_idx'], dict(expected.segment_root_lookup),
                           expected.package_spec.erasure_shards, _bundle(package, _hex(data['bundle'])))

    state = JamState.create_genesis_state()
    state.timeslot.number = package.context.lookup_anchor_slot
    keys_by_type = {cls: key for key, cls in STORAGE_KEY_MAPPING.items()}
    keyvals = {keys_by_type[type(component)]: component.to_jam_bytes().to_bytes()
               for item in fields(state)
               if type(component := getattr(state, item.name)) in keys_by_type}

    def put(key, value):
        if len(key) != 31:
            raise ValueError('service data keys must be 31 bytes')
        if key in keyvals and keyvals[key] != value:
            raise ValueError(f'conflicting state entries for {key.hex()}')
        keyvals[key] = value

    for service_id, entry in data['services'].items():
        service_id = int(service_id)
        if not 0 <= service_id < 2**32:
            raise ValueError('service ID must fit in U32')
        account = entry['service']
        converted = ServiceAccount(
            code_hash=_hex(account['code_hash']), balance=account['balance'],
            gas_limit_accumulate=account['min_item_gas'], gas_limit_on_transfer=account['min_memo_gas'],
            footprint_storage_bytes=account['bytes'], footprint_storage_items=account['items'],
            deposit_offset=account['deposit_offset'], creation_slot=account['creation_slot'],
            last_accumulation_slot=account['last_accumulation_slot'], parent_service=account['parent_service'],
            storage_items={}, preimages={}, preimage_availability={},
        )
        if len(converted.code_hash) != 32:
            raise ValueError('service code hash must be 32 bytes')
        put(state_key_constructor_service_account(service_id), converted.to_serialized_bytes())
        for raw in entry['data']:
            put(_hex(raw['key']), _hex(raw['value']))
        for preimage in entry['preimage_blobs']:
            blob, digest = _hex(preimage['blob']), _hex(preimage['hash'])
            if blake2b_256_hash(blob) != digest:
                raise ValueError('preimage hash does not match blob')
            put(state_key_constructor_preimage(service_id, digest), blob)

    keyvals = sorted(keyvals.items())
    header = Header.default()
    header.timeslot = package.context.lookup_anchor_slot
    genesis = TraceGenesis(header, StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals))
    # Exercise codec bounds before producing any files.
    for value in (genesis, request, expected):
        value.to_jam_bytes()
    return genesis, request, expected


def load_refinement_vector(source: Path):
    """Convert a vector without executing it or writing files."""
    return _parse(Path(source).read_bytes())


def _parse(raw):
    try:
        return _convert(json.loads(raw))
    except Exception as exc:
        raise ValueError(f'Invalid refinement JSON vector: {exc}') from exc


def import_refinement_vector(source: Path, destination: Path):
    """Write a new fixture directory; never overwrite files or adjust the oracle."""
    source, destination = Path(source), Path(destination)
    raw = source.read_bytes()
    genesis, request, expected = _parse(raw)
    if destination.exists():
        raise FileExistsError(f'fixture destination already exists: {destination}')
    warnings = []
    package = request.bundle.work_package
    if state_key_constructor_preimage(package.auth_code_host, package.auth_code_hash) not in dict(genesis.state.keyvals):
        warnings.append(f'authorization preimage missing for service {package.auth_code_host}')
    if expected.authorizer_hash != package.authorizer_hash():
        warnings.append('expected authorizer hash differs from H(auth_code_hash || authorizer_config)')
    encoded = {name: value.to_jam_bytes().to_bytes() for name, value in (
        ('genesis.bin', genesis), ('refine.bin', request), ('report.bin', expected),
    )}
    manifest = {
        'source': str(source.resolve()), 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'graypaper_version': GP_VERSION, 'profile': TEST_SUITE,
        'initialization': 'synthetic default global state and header; supplied service state only',
        'package_context_unchanged': True, 'expected_report_unchanged': True,
        'transport_parameters': 'core_idx from input; segment_root_lookup and erasure_shards from expected report',
        'exported_segments': 'preserved in source.json; protocol returns report commitments, not exported bytes',
        'warnings': warnings,
        'sha256': {name: hashlib.sha256(value).hexdigest() for name, value in encoded.items()},
    }
    destination.mkdir(parents=True)
    for name, value in encoded.items():
        (destination / name).write_bytes(value)
    (destination / 'source.json').write_bytes(raw)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
