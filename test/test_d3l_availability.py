from dataclasses import replace

import pytest
from jamcodec.types import H256, Vec

from pyjamaz.availability import (
    AvailabilityArtifacts, DataUnavailable, ImportedSegment, build_availability_artifacts,
    verify_segment_shard,
)
from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import RefinementContext, ValidatorData, WorkReport
from pyjamaz.storage import FileStorageEngine, InMemoryStorageEngine


@pytest.fixture
def data():
    exports = [bytes([i + 1]) * 4104 for i in range(3)]
    bundle = b'canonical bundle'
    artifacts = build_availability_artifacts(b'p' * 32, bundle, exports, 6)
    report = WorkReport(artifacts.spec, RefinementContext(*([bytes(32)] * 4), 0, []),
                        1, bytes(32), 0, b'', {}, [])
    validators = [ValidatorData(bytes(32), bytes([i]) * 32, bytes(144), bytes(128)) for i in range(6)]
    source = AvailabilitySource(report, validators, validators[:2], b'b' * 32, 10)
    return bundle, exports, artifacts, source


def retain(store, data, source=None):
    bundle, exports, artifacts, original = data
    store.store_work_report(original.report, bundle, exports, artifacts=artifacts)
    store.register_source(original if source is None else source)


def test_artifacts_and_source_metadata_survive_restart(tmp_path, data):
    store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    retain(store, data)
    store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    bundle, exports, artifacts, source = data
    assert store.sources() == [source]
    assert store.source_for(package_hash=source.spec.hash) == source
    assert store.source_for(exports_root=source.spec.exports_root) == source
    assert store.source_for(erasure_root=source.spec.erasure_root) == source
    assert store.specification(source.spec.erasure_root) == source.spec
    assert store.segment_root_for_package(source.spec.hash) == source.spec.exports_root
    assert store.retrieve_segments(source.spec.exports_root).segments == exports
    assert store.storage_engine.get(b'bundle:' + source.spec.hash) == bundle
    for shard in artifacts.shards:
        assert store.retrieve_validator_shard(source.spec, shard.shard_index) == shard
        chunk, proof = store.retrieve_segment_shard(source.spec, shard.shard_index, len(exports))
        verify_segment_shard(chunk, len(exports), shard.shard_index, proof, source.spec)


def test_local_reports_do_not_establish_chain_backed_metadata(data):
    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.store_work_report(source.report, bundle, exports, artifacts=artifacts)
    assert store.specification(source.spec.erasure_root) == source.spec
    with pytest.raises(DataUnavailable, match='chain-backed'):
        store.source_for(package_hash=source.spec.hash)


def test_source_lookup_selects_active_branch_and_preserves_historical_set(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    later = replace(original, registered_block=b'c' * 32, registered_slot=20)
    store.register_source(original)
    store.register_source(later)
    assert store.source_for(package_hash=original.spec.hash) == later
    assert store.source_for(package_hash=original.spec.hash,
                            canonical=lambda block: block == original.registered_block) == original
    assert store.source_for(exports_root=original.spec.exports_root).validators == original.validators
    with pytest.raises(DataUnavailable, match='chain-backed'):
        store.source_for(erasure_root=original.spec.erasure_root, canonical=lambda _: False)


@pytest.mark.parametrize('fault', ['count', 'duplicate', 'guarantor_duplicate', 'guarantor_encoding', 'assurance', 'slot'])
def test_invalid_source_context_is_not_published(data, fault):
    _, _, _, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    if fault == 'count':
        source = replace(source, validators=source.validators[:-1])
    elif fault == 'duplicate':
        source = replace(source, validators=source.validators[:-1] + source.validators[:1])
    elif fault == 'guarantor_duplicate':
        source = replace(source, guarantors=source.guarantors[:1] * 2)
    elif fault == 'guarantor_encoding':
        source = replace(source, guarantors=[replace(source.validators[0], metadata=b'x' * 127)])
    elif fault == 'assurance':
        source = replace(source, assured_block=b'a' * 32)
    else:
        source = replace(source, registered_slot=True)
    with pytest.raises(ProcessWorkpackageError):
        store.register_source(source)
    assert store.storage_engine.as_dict() == {}


def test_previous_rotation_guarantor_is_retained_independently_of_assurers(data):
    _, _, _, source = data
    historical = replace(source.guarantors[0], ed25519=b'h' * 32, metadata=b'm' * 128)
    source = replace(source, guarantors=[historical])
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.register_source(source)
    retrieved = store.source_for(package_hash=source.spec.hash)
    assert historical.ed25519 not in {validator.ed25519 for validator in retrieved.validators}
    assert retrieved.guarantors == [historical]


@pytest.mark.parametrize('fault', ['truncated', 'trailing', 'identity', 'validators'])
def test_corrupt_source_metadata_is_retryable(data, fault):
    _, _, _, source = data
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    store.register_source(source)
    raw = source.to_jam_bytes().to_bytes()
    if fault == 'truncated':
        raw = raw[:20]
    elif fault == 'trailing':
        raw += bytes(1)
    elif fault == 'identity':
        raw = replace(source, registered_block=bytes(32)).to_jam_bytes().to_bytes()
    else:
        raw = replace(source, validators=source.validators[:-1]).to_jam_bytes().to_bytes()
    engine.put(b'source-v1:' + source.identity, raw)
    assert store.sources() == []
    with pytest.raises(DataUnavailable, match='chain-backed'):
        store.source_for(package_hash=source.spec.hash)


@pytest.mark.parametrize('fault', ['missing', 'corrupt'])
def test_unavailable_source_does_not_hide_healthy_sources_or_remove_repair_indexes(data, fault):
    _, _, _, source = data
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    healthy = replace(source, registered_block=b'c' * 32, registered_slot=20)
    store.register_source(source)
    store.register_source(healthy)
    key = b'source-v1:' + source.identity
    if fault == 'missing':
        engine.delete(key)
    else:
        engine.put(key, b'corrupt record')
    assert store.sources() == [healthy]
    assert store.source_for(package_hash=source.spec.hash) == healthy
    assert set(store._index(b'source-list-v1')) == {source.identity, healthy.identity}
    assert set(store._index(b'source-index-v1:package' + source.spec.hash)) == {source.identity, healthy.identity}
    store.register_source(source)
    assert set(record.identity for record in store.sources()) == {source.identity, healthy.identity}


def test_corrupt_global_source_index_remains_unavailable(data):
    _, _, _, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.register_source(source)
    store.storage_engine.put(b'source-list-v1', b'corrupt index')
    with pytest.raises(DataUnavailable, match='index'):
        store.sources()


def test_historical_assurance_selects_registration_that_existed_at_its_slot(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    later = replace(original, registered_block=b'l' * 32, registered_slot=100)
    store.register_source(original)
    store.register_source(later)
    store.mark_assured(original.report, b'a' * 32, 20, lambda _: True)
    assert store._source(original.identity).assured_slot == 20
    assert store._source(later.identity).assured_block is None


def test_assurance_matches_full_report_when_erasure_root_is_shared(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    another_report = replace(original.report, core_index=original.report.core_index + 1)
    other = replace(original, report=another_report, registered_block=b'o' * 32, registered_slot=11)
    store.register_source(original)
    store.register_source(other)
    store.mark_assured(original.report, b'a' * 32, 20, lambda _: True)
    assert store._source(original.identity).assured_slot == 20
    assert store._source(other.identity).assured_block is None


def test_older_assurance_replay_preserves_existing_canonical_reference(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    existing = replace(original, assured_block=b'n' * 32, assured_slot=30)
    store.register_source(existing)
    store.mark_assured(original.report, b'a' * 32, 20, lambda _: True)
    assert store._source(original.identity) == existing


def test_assurance_replay_replaces_orphan_reference_and_ignores_unavailable_source(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    existing = replace(original, assured_block=b'o' * 32, assured_slot=30)
    missing = replace(original, registered_block=b'm' * 32, registered_slot=11)
    store.register_source(existing)
    store.register_source(missing)
    store.storage_engine.delete(b'source-v1:' + missing.identity)
    canonical = lambda block: block in {original.registered_block, b'a' * 32}
    store.mark_assured(original.report, b'a' * 32, 20, canonical)
    repaired = store._source(original.identity)
    assert repaired.assured_block == b'a' * 32 and repaired.assured_slot == 20


def test_assurance_without_a_matching_eligible_registration_remains_unavailable(data):
    _, _, _, original = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.register_source(original)
    for report, slot, canonical in ((original.report, 5, lambda _: True),
                                    (replace(original.report, core_index=0), 20, lambda _: True),
                                    (original.report, 20, lambda _: False)):
        with pytest.raises(DataUnavailable, match='matching source'):
            store.mark_assured(report, b'a' * 32, slot, canonical)


def test_local_report_lookup_establishes_only_local_source_provenance(data):
    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.store_work_report(source.report, bundle, exports, artifacts=artifacts)
    assert store.local_report_for_exports(source.spec.exports_root) == source.report
    with pytest.raises(DataUnavailable, match='chain-backed'):
        store.source_for(exports_root=source.spec.exports_root)


def test_missing_local_report_does_not_hide_another_report_for_same_exports(data):
    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.store_work_report(source.report, bundle, exports, artifacts=artifacts)
    other_artifacts = build_availability_artifacts(b'q' * 32, b'other bundle', exports, 6)
    other_report = replace(source.report, package_spec=other_artifacts.spec)
    store.store_work_report(other_report, b'other bundle', exports, artifacts=other_artifacts)
    store.storage_engine.delete(b'local-report-v1:' + source.spec.erasure_root)
    assert store.local_report_for_exports(source.spec.exports_root) == other_report


def test_local_report_lookup_checks_index_root_and_report_dimensions(data):
    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.store_work_report(source.report, bundle, exports, artifacts=artifacts)
    wrong_root = b'w' * 32
    store.storage_engine.put(b'local-exports-v1:' + wrong_root,
                             Vec(H256).encode([source.spec.erasure_root]).to_bytes())
    with pytest.raises(DataUnavailable, match='index'):
        store.local_report_for_exports(wrong_root)
    bad = replace(source.report, package_spec=replace(source.spec, erasure_shards=0))
    store.storage_engine.put(b'local-report-v1:' + source.spec.erasure_root, bad.to_jam_bytes().to_bytes())
    with pytest.raises(DataUnavailable):
        store.local_report_for_exports(source.spec.exports_root)


@pytest.mark.parametrize('fault', ['truncated', 'trailing', 'noncanonical', 'duplicates', 'mismatch'])
def test_corrupt_source_indexes_are_retryable(data, fault):
    _, _, _, source = data
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    store.register_source(source)
    lookup = source.spec.hash
    raw = Vec(H256).encode([source.identity]).to_bytes()
    if fault == 'truncated':
        raw = raw[:-1]
    elif fault == 'trailing':
        raw += bytes(1)
    elif fault == 'noncanonical':
        raw = b'\x80\x01' + raw[1:]
    elif fault == 'duplicates':
        raw = Vec(H256).encode([source.identity, source.identity]).to_bytes()
    else:
        lookup = b'q' * 32
    engine.put(b'source-index-v1:package' + lookup, raw)
    with pytest.raises(DataUnavailable, match='index'):
        store.source_for(package_hash=lookup)


@pytest.mark.parametrize('kind', ['source', 'row', 'audit'])
def test_missing_retained_records_are_retryable(tmp_path, data, kind):
    store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    retain(store, data)
    _, _, artifacts, source = data
    if kind == 'source':
        store.storage_engine.delete(b'source-v1:' + source.identity)
        read = lambda: store.source_for(package_hash=source.spec.hash)
    else:
        prefix = b'row-v1:' if kind == 'row' else b'audit-v1:'
        store.storage_engine.delete(store._shard_key(prefix, source.spec, 0))
        read = lambda: store.retrieve_validator_shard(artifacts.spec, 0)
    with pytest.raises(DataUnavailable):
        read()


@pytest.mark.parametrize('kind', ['local-report', 'row', 'audit'])
def test_corrupt_artifact_records_are_retryable(data, kind):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    retain(store, data)
    _, _, artifacts, source = data
    if kind == 'local-report':
        key = b'local-report-v1:' + source.spec.erasure_root
        store.storage_engine.put(key, store.storage_engine.get(key) + bytes(1))
        read = lambda: store.specification(source.spec.erasure_root, canonical=lambda _: False)
    else:
        prefix = b'row-v1:' if kind == 'row' else b'audit-v1:'
        key = store._shard_key(prefix, source.spec, 0)
        store.storage_engine.put(key, store.storage_engine.get(key)[:-1])
        read = lambda: store.retrieve_validator_shard(artifacts.spec, 0)
    with pytest.raises(DataUnavailable, match='invalid'):
        read()


def test_artifact_records_are_verified_before_metadata_is_published(data):
    bundle, exports, artifacts, source = data
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    bad = AvailabilityArtifacts(artifacts.spec, artifacts.shards[:-1])
    with pytest.raises(ProcessWorkpackageError):
        store.store_work_report(source.report, bundle, exports, artifacts=bad)
    bad = replace(artifacts, shards=artifacts.shards[:-1] + (replace(artifacts.shards[-1], bundle_shard=b''),))
    with pytest.raises(ProcessWorkpackageError):
        store.store_work_report(source.report, bundle, exports, artifacts=bad)
    assert engine.as_dict() == {}


def test_failed_payload_write_does_not_publish_report_metadata(data):
    class FailingStorage(InMemoryStorageEngine):
        def put(self, key, value):
            if key.startswith(b'row-v1:'):
                raise OSError('disk full')
            super().put(key, value)

    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(FailingStorage())
    with pytest.raises(OSError, match='disk full'):
        store.store_work_report(source.report, bundle, exports, artifacts=artifacts)
    assert not any(key.startswith((b'local-report-v1:', b'package-root:', b'row-index-v1:'))
                   for key in store.storage_engine.as_dict())


def test_finality_prunes_audit_payload_but_keeps_proven_segment_rows(data):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    retain(store, data)
    _, _, artifacts, source = data
    store.mark_assured(source.report, b'a' * 32, 12, canonical=lambda _: True)
    assert store.source_for(package_hash=source.spec.hash).assured_slot == 12
    store.prune(20, lambda _: True, lambda _: False)
    assert store.retrieve_validator_shard(source.spec, 0) == artifacts.shards[0]
    store.prune(20, lambda _: True, lambda block: block == b'a' * 32)
    with pytest.raises(DataUnavailable, match='audit'):
        store.retrieve_validator_shard(source.spec, 0)
    assert store.storage_engine.get(b'bundle:' + source.spec.hash) is None
    for shard in artifacts.shards:
        chunk, proof = store.retrieve_segment_shard(source.spec, shard.shard_index, 0)
        verify_segment_shard(chunk, 0, shard.shard_index, proof, source.spec)


def test_retention_boundary_and_active_holds_protect_shared_roots(data):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    retain(store, data)
    _, exports, _, source = data
    tree = ConstantDepthMerkleTree(exports)
    store.store_import(tree.root(), 0, ImportedSegment(exports[0], tuple(tree.trace(0))))
    store.mark_assured(source.report, b'a' * 32, 12, canonical=lambda _: True)
    later = replace(source, registered_block=b'c' * 32, registered_slot=30,
                    assured_block=b'd' * 32, assured_slot=31)
    store.register_source(later)
    expiry = 30 + 672 * EPOCH_TIMESLOTS
    store.prune(expiry - 1, lambda _: True, lambda _: True)
    assert store.retrieve_segment_shard(source.spec, 0, 0)[0]
    assert store.retrieve_import(tree.root(), 0).segment == exports[0]
    with store.hold(source.spec.erasure_root):
        with store.hold(source.spec.erasure_root):
            store.prune(expiry, lambda _: True, lambda _: True)
            assert store.retrieve_segment_shard(source.spec, 0, 0)[0]
        store.prune(expiry, lambda _: True, lambda _: True)
        assert store.retrieve_segments(tree.root()).segments == exports
    store.prune(expiry, lambda _: True, lambda _: True)
    with pytest.raises(DataUnavailable):
        store.retrieve_segment_shard(source.spec, 0, 0)
    with pytest.raises(DataUnavailable):
        store.retrieve_segments(tree.root())
    with pytest.raises(DataUnavailable):
        store.retrieve_import(tree.root(), 0)


def test_unassured_fork_does_not_prevent_canonical_audit_pruning(data):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    _, _, _, source = data
    canonical = replace(source, assured_block=b'a' * 32, assured_slot=12)
    retain(store, data, canonical)
    store.register_source(replace(source, registered_block=b'c' * 32, registered_slot=20))
    store.prune(30, lambda block: block == source.registered_block, lambda _: True)
    with pytest.raises(DataUnavailable, match='audit'):
        store.retrieve_validator_shard(source.spec, 0)
    assert store.retrieve_segment_shard(source.spec, 0, 0)[0]


def test_shared_exports_wait_for_every_retained_source_and_active_request(data):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    retain(store, data)
    _, exports, _, source = data
    store.mark_assured(source.report, b'a' * 32, 12, canonical=lambda _: True)
    artifacts = build_availability_artifacts(b'q' * 32, b'another bundle', exports, 6)
    later = replace(source, report=replace(source.report, package_spec=artifacts.spec),
                    registered_block=b'c' * 32, registered_slot=30,
                    assured_block=b'd' * 32, assured_slot=31)
    store.store_work_report(later.report, b'another bundle', exports, artifacts=artifacts)
    store.register_source(later)
    expiry = 30 + 672 * EPOCH_TIMESLOTS
    store.prune(expiry - 1, lambda _: True, lambda _: True)
    assert store.retrieve_segments(source.spec.exports_root).segments == exports
    with pytest.raises(DataUnavailable):
        store.retrieve_segment_shard(source.spec, 0, 0)
    with store.hold(later.spec.erasure_root):
        store.prune(expiry, lambda _: True, lambda _: True)
        assert store.retrieve_segments(source.spec.exports_root).segments == exports
    store.prune(expiry, lambda _: True, lambda _: True)
    with pytest.raises(DataUnavailable):
        store.retrieve_segments(source.spec.exports_root)


@pytest.mark.parametrize('sharing', ['unrelated', 'erasure', 'exports', 'package'])
def test_missing_metadata_protects_shared_payloads_without_blocking_unrelated_pruning(data, sharing):
    bundle, exports, artifacts, source = data
    store = DataAvailabilityStore(InMemoryStorageEngine())
    source = replace(source, assured_block=b'a' * 32, assured_slot=12)
    retain(store, data, source)
    if sharing == 'erasure':
        missing = replace(source, registered_block=b'c' * 32, registered_slot=20,
                          assured_block=None, assured_slot=None)
        store.register_source(missing)
    else:
        other_exports = exports if sharing == 'exports' else [b'z' * 4104]
        other_hash = source.spec.hash if sharing == 'package' else b'q' * 32
        other_artifacts = build_availability_artifacts(other_hash, b'other bundle', other_exports, 6)
        missing = replace(source, report=replace(source.report, package_spec=other_artifacts.spec),
                          registered_block=b'c' * 32, registered_slot=20,
                          assured_block=None, assured_slot=None)
        store.store_work_report(missing.report, b'other bundle', other_exports, artifacts=other_artifacts)
        store.register_source(missing)
    store.storage_engine.delete(b'source-v1:' + missing.identity)
    expiry = 20 + 672 * EPOCH_TIMESLOTS
    store.prune(expiry, lambda _: True, lambda _: True)
    if sharing == 'erasure':
        assert store.retrieve_validator_shard(source.spec, 0) == artifacts.shards[0]
    else:
        with pytest.raises(DataUnavailable):
            store.retrieve_segment_shard(source.spec, 0, 0)
    if sharing in ('erasure', 'exports'):
        assert store.retrieve_segments(source.spec.exports_root).segments == exports
    else:
        with pytest.raises(DataUnavailable):
            store.retrieve_segments(source.spec.exports_root)
    if sharing in ('erasure', 'package'):
        assert store.storage_engine.get(b'bundle:' + source.spec.hash) is not None
    else:
        assert store.storage_engine.get(b'bundle:' + source.spec.hash) is None
    assert missing.identity in store._index(b'source-list-v1')


@pytest.mark.parametrize('assured', [False, True])
def test_audit_serving_survives_export_expiry_until_assurance_finality(data, assured):
    store = DataAvailabilityStore(InMemoryStorageEngine())
    retain(store, data)
    _, _, artifacts, source = data
    if assured:
        store.mark_assured(source.report, b'a' * 32, 12, canonical=lambda _: True)
    expiry = source.registered_slot + 672 * EPOCH_TIMESLOTS
    store.prune(expiry, lambda _: True, lambda _: False)
    for shard in artifacts.shards:
        assert store.retrieve_validator_shard(source.spec, shard.shard_index) == shard
    if assured:
        store.prune(expiry, lambda _: True, lambda _: True)
        with pytest.raises(DataUnavailable):
            store.retrieve_validator_shard(source.spec, 0)


def test_atomic_file_replacement_preserves_previous_record_on_failure(tmp_path, monkeypatch):
    import pyjamaz.storage as storage_module

    engine = FileStorageEngine(str(tmp_path))
    engine.put(b'key', b'previous')
    original = storage_module.os.replace
    observed = []

    def replace_record(temporary, destination):
        with open(temporary, 'rb') as stream:
            observed.append((engine.get(b'key'), stream.read()))
        raise OSError('replacement failed')

    monkeypatch.setattr(storage_module.os, 'replace', replace_record)
    with pytest.raises(OSError, match='replacement failed'):
        engine.put(b'key', b'complete new record')
    assert observed == [(b'previous', b'complete new record')]
    assert engine.get(b'key') == b'previous'
    assert [path.name for path in tmp_path.iterdir()] == [b'key'.hex() + '.bin']
    monkeypatch.setattr(storage_module.os, 'replace', original)
    engine.put(b'key', b'complete new record')
    assert engine.get(b'key') == b'complete new record'
