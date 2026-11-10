import pytest

from pyjamaz.availability import DataUnavailable, ImportedSegment
from pyjamaz.d3l import DataAvailabilityStore
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.storage import FileStorageEngine, InMemoryStorageEngine


@pytest.fixture
def imports():
    exports = [bytes([index + 1]) * EC_SEGMENT_SIZE for index in range(3)]
    tree = ConstantDepthMerkleTree(exports)
    return exports, tree.root(), ImportedSegment(exports[1], tuple(tree.trace(1)))


def test_verified_import_is_idempotent_and_does_not_create_package_mapping(imports):
    exports, root, imported = imports
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    store.store_segments(D3LEntry(root, exports))
    retained = engine.get(root)
    store.store_import(root, 1, imported)
    stored = engine.as_dict()
    store.store_import(root, 1, imported)
    assert store.retrieve_import(root, 1) == imported
    assert engine.as_dict() == stored
    assert engine.get(root) == retained
    assert store.retrieve_segments(root).segments == exports
    with pytest.raises(DataUnavailable, match='mapping'):
        store.segment_root_for_package(b'p' * 32)


def test_import_survives_reopening_disk_store(tmp_path, imports):
    _, root, imported = imports
    store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    store.store_import(root, 1, imported)
    reopened = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    assert reopened.retrieve_import(root, 1) == imported


@pytest.mark.parametrize('kind', ['import', 'segments', 'mapping'])
def test_missing_disk_data_is_retryable(tmp_path, kind):
    store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    with pytest.raises(DataUnavailable):
        if kind == 'import':
            store.retrieve_import(b'r' * 32, 1)
        elif kind == 'segments':
            store.retrieve_segments(b'r' * 32)
        else:
            store.segment_root_for_package(b'p' * 32)


@pytest.mark.parametrize('fault', ['segment', 'proof', 'truncated', 'trailing', 'noncanonical'])
def test_corrupt_cache_record_is_rejected_on_read(imports, fault):
    _, root, imported = imports
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    store.store_import(root, 1, imported)
    key, data = engine.as_list()[0]
    if fault == 'segment':
        data = bytes([data[0] ^ 1]) + data[1:]
    elif fault == 'proof':
        data = data[:-1] + bytes([data[-1] ^ 1])
    elif fault == 'truncated':
        data = data[:EC_SEGMENT_SIZE]
    elif fault == 'trailing':
        data += bytes(1)
    else:
        # Two hashes encoded with an overlong length prefix.
        data = data[:EC_SEGMENT_SIZE] + b'\x80\x02' + data[EC_SEGMENT_SIZE + 1:]
    engine.put(key, data)
    with pytest.raises(DataUnavailable, match='invalid'):
        store.retrieve_import(root, 1)


@pytest.mark.parametrize('fault', ['root', 'index', 'segment', 'proof'])
def test_invalid_import_is_not_stored(imports, fault):
    _, root, imported = imports
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    index = 1
    if fault == 'root':
        root = bytes(32)
    elif fault == 'index':
        index = True
    elif fault == 'segment':
        imported = ImportedSegment(imported.segment[:-1], imported.justification)
    else:
        imported = ImportedSegment(imported.segment, ())
    with pytest.raises(ProcessWorkpackageError):
        store.store_import(root, index, imported)
    assert engine.as_list() == []


@pytest.mark.parametrize('fault', ['malformed', 'trailing', 'noncanonical', 'root'])
def test_corrupt_complete_export_record_is_retryable(imports, fault):
    exports, root, _ = imports
    engine = InMemoryStorageEngine()
    store = DataAvailabilityStore(engine)
    data = D3LEntry(root, exports).to_jam_bytes().to_bytes()
    if fault == 'malformed':
        data = data[:33]
    elif fault == 'trailing':
        data += bytes(1)
    elif fault == 'noncanonical':
        data = data[:32] + b'\x80\x03' + data[33:]
    else:
        data = bytes(32) + data[32:]
    engine.put(root, data)
    with pytest.raises(DataUnavailable, match='invalid'):
        store.retrieve_segments(root)
    store.store_segments(D3LEntry(root, exports))
    assert store.retrieve_segments(root).segments == exports
