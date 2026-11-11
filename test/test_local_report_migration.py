"""Upgrade retained local reports without making their provenance chain-backed."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pyjamaz.availability import DataUnavailable
from pyjamaz.d3l import DataAvailabilityStore
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import ImportSegment
from pyjamaz.runtime.pipelines.refine import RefinePipeline
from pyjamaz.storage import FileStorageEngine, InMemoryStorageEngine, RocksDBStorageEngine
from test.test_availability_lifecycle import source_data
from test.test_runtime_refinement import package


def retain_legacy_report(engine, report, exports):
    """The report publication layout before local-exports-v1 was added."""
    spec = report.package_spec
    engine.put(spec.exports_root, D3LEntry(spec.exports_root, exports).to_jam_bytes().to_bytes())
    engine.put(b'bundle:' + spec.hash, b'bundle')
    engine.put(b'package-root:' + spec.hash, spec.exports_root)
    engine.put(b'local-report-v1:' + spec.erasure_root, report.to_jam_bytes().to_bytes())


@pytest.mark.parametrize('backend', ['memory', 'file', 'rocks'])
def test_legacy_local_report_remains_eligible_for_direct_root_import_after_restart(tmp_path, source_data, backend):
    _, report, _, exports = source_data
    if backend == 'memory':
        engine = InMemoryStorageEngine()
        reopen = lambda: InMemoryStorageEngine(engine.storage)
    elif backend == 'file':
        engine = FileStorageEngine(str(tmp_path))
        reopen = lambda: FileStorageEngine(str(tmp_path))
    else:
        pytest.importorskip('rocksdict')
        engine = RocksDBStorageEngine.create_from_file(str(tmp_path / 'rocks'))
        reopen = lambda: RocksDBStorageEngine.create_from_file(str(tmp_path / 'rocks'))
    retain_legacy_report(engine, report, exports)
    engine.close()
    engine = reopen()
    try:
        store = DataAvailabilityStore(engine)
        state = SimpleNamespace(recent_history=SimpleNamespace(recent_blocks=[]))
        pipeline = RefinePipeline(SimpleNamespace(working_state=state, d3l_store=store))
        value = package(imports=[ImportSegment.from_segment_root(report.package_spec.exports_root, 0)])
        pipeline._validate_import_sources(value, {}, state)
        assert store.local_report_for_exports(report.package_spec.exports_root) == report
        assert store.retrieve_segments(report.package_spec.exports_root).segments == exports
        assert store.segment_root_for_package(report.package_spec.hash) == report.package_spec.exports_root
        with pytest.raises(DataUnavailable, match='chain-backed'):
            store.source_for(exports_root=report.package_spec.exports_root)

        # The repaired index survives another store instance and avoids another scan.
        reopened = DataAvailabilityStore(engine)
        assert reopened.local_report_for_exports(report.package_spec.exports_root) == report
        assert reopened._local_report_keys is None
    finally:
        engine.close()


def test_local_report_upgrade_is_bounded_and_does_not_rescan_unknown_roots(source_data):
    class CountingStorage(InMemoryStorageEngine):
        def __init__(self):
            super().__init__()
            self.keys_seen = 0
            self.passes = 0
            self.payload_reads = 0

        def iter_keys(self):
            self.passes += 1
            for key in super().iter_keys():
                self.keys_seen += 1
                yield key

        def get(self, key):
            if key.startswith(b'audit-v1:'):
                self.payload_reads += 1
            return super().get(key)

    _, report, _, exports = source_data
    engine = CountingStorage()
    limit = DataAvailabilityStore.LOCAL_REPORT_BACKFILL_BATCH_SIZE
    for index in range(limit * 2):
        engine.put(b'audit-v1:' + index.to_bytes(32, 'little'), b'unread payload')
    retain_legacy_report(engine, report, exports)
    store = DataAvailabilityStore(engine)
    for attempt in range(2):
        with pytest.raises(DataUnavailable):
            store.local_report_for_exports(report.package_spec.exports_root)
        assert engine.keys_seen == limit * (attempt + 1)
    assert store.local_report_for_exports(report.package_spec.exports_root) == report
    assert engine.payload_reads == 0

    for _ in range(3):
        with pytest.raises(DataUnavailable):
            store.local_report_for_exports(b'?' * 32)
    assert engine.passes == 1
    assert engine.keys_seen == limit * 2 + 4


@pytest.mark.parametrize('fault', ['truncated', 'dimensions', 'mismatched_key', 'missing'])
def test_invalid_or_missing_legacy_candidate_does_not_hide_valid_report(source_data, fault):
    _, report, _, exports = source_data
    engine = InMemoryStorageEngine()
    bad_key = b'local-report-v1:' + b'z' * 32
    if fault == 'truncated':
        bad = report.to_jam_bytes().to_bytes()[:-1]
    elif fault == 'dimensions':
        bad = replace(report, package_spec=replace(report.package_spec, erasure_root=b'z' * 32,
                                                   erasure_shards=0)).to_jam_bytes().to_bytes()
    else:
        bad = report.to_jam_bytes().to_bytes()
    engine.put(bad_key, bad)
    retain_legacy_report(engine, report, exports)
    store = DataAvailabilityStore(engine)
    if fault == 'missing':
        # A file/record may disappear after the key iterator captures it.
        store._local_report_keys = engine.iter_keys()
        engine.delete(bad_key)
    assert store.local_report_for_exports(report.package_spec.exports_root) == report
    assert store._index(b'local-exports-v1:' + report.package_spec.exports_root) == [report.package_spec.erasure_root]


def test_key_iteration_respects_memory_and_rocks_namespaces(tmp_path):
    engines = [InMemoryStorageEngine()]
    pytest.importorskip('rocksdict')
    engines.append(RocksDBStorageEngine.create_from_file(str(tmp_path / 'rocks')))
    try:
        for engine in engines:
            engine.put(b'outside', b'value')
            namespace = engine.namespace(b'local')
            namespace.put(b'local-report-v1:key', b'value')
            assert list(namespace.iter_keys()) == [b'local-report-v1:key']
    finally:
        for engine in engines:
            engine.close()


def test_file_key_iteration_ignores_nonrecord_entries(tmp_path):
    engine = FileStorageEngine(str(tmp_path))
    engine.put(b'local-report-v1:key', b'value')
    (tmp_path / 'temporary-write').write_bytes(b'partial value')
    (tmp_path / 'not-hex.bin').write_bytes(b'invalid name')
    (tmp_path / 'abcd.bin').mkdir()
    assert list(engine.iter_keys()) == [b'local-report-v1:key']
