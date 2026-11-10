"""Local availability lookup, bounded history repair and corrupt-cache behavior."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyjamaz.availability import DataUnavailable
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.block import Header
from pyjamaz.runtime.availability import AvailabilityRuntime
from pyjamaz.storage import InMemoryStorageEngine
from test.test_availability_lifecycle import backfill_app, source_data


def local_runtime(source_data):
    artifacts, report, validators, exports = source_data
    registration = Header.default()
    registration.timeslot = 1
    source = AvailabilitySource(report, validators, validators[:2], registration.hash, 1)
    store = DataAvailabilityStore(InMemoryStorageEngine())
    store.register_source(source)
    app = SimpleNamespace(
        d3l_store=store,
        state_storage=SimpleNamespace(block_hash=None, finalized_block_hash=registration.hash, parents={}),
        retrieve_block_header=lambda h: registration if h == registration.hash else None,
        retrieve_block_by_hash=lambda _: None,
        config=SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=validators[0].ed25519))),
    )
    return AvailabilityRuntime(app), source, artifacts, exports


def test_restart_uses_retained_finalized_head_for_sources_and_assigned_data(source_data):
    runtime, source, artifacts, _ = local_runtime(source_data)
    runtime.store.store_validator_shard(source.spec, artifacts.shards[0])
    assert runtime.canonical(source.registered_block)
    assert runtime.source_for(package_hash=source.spec.hash) == source
    assert runtime.store.specification(source.spec.erasure_root, runtime.canonical) == source.spec
    assert runtime.assigned_ready(source)


def test_trusted_finality_lineage_is_reused_until_next_confirmation(source_data):
    runtime, source, _, _ = local_runtime(source_data)
    assured = replace(source, assured_block=source.registered_block, assured_slot=1)
    next_header = Header.default()
    next_header.parent = source.registered_block
    next_header.timeslot = 2
    original_lookup = runtime.app.retrieve_block_header
    runtime.app.retrieve_block_header = lambda h: next_header if h == next_header.hash else original_lookup(h)
    runtime._lineage = Mock(wraps=runtime._lineage)
    runtime.on_finalized(source.registered_block)
    for _ in range(100):
        assert runtime._assurance_finalized(assured)
    runtime._lineage.assert_called_once_with(source.registered_block)

    newly_assured = replace(source, assured_block=next_header.hash, assured_slot=2)
    assert not runtime._assurance_finalized(newly_assured)
    runtime.on_finalized(next_header.hash)
    assert runtime._assurance_finalized(newly_assured)
    assert runtime._lineage.call_count == 2
    runtime.on_finalized(source.registered_block)
    assert runtime._availability_finalized_hash == next_header.hash
    assert runtime._assurance_finalized(newly_assured)
    assert runtime._lineage.call_count == 2


def history_runtime(count):
    def block_hash(number):
        return number.to_bytes(32, 'little')

    calls = {'headers': 0, 'blocks': 0}
    headers = {block_hash(i): SimpleNamespace(parent=block_hash(i - 1) if i else None, timeslot=i)
               for i in range(count + 1)}

    def header(h):
        calls['headers'] += 1
        return headers.get(h)

    def block(h):
        calls['blocks'] += 1
        return None

    app = SimpleNamespace(
        d3l_store=DataAvailabilityStore(InMemoryStorageEngine()),
        state_storage=SimpleNamespace(block_hash=block_hash(count), finalized_block_hash=block_hash(0), parents={}),
        retrieve_block_header=header, retrieve_block_by_hash=block,
    )
    return AvailabilityRuntime(app), headers, calls, block_hash


def test_history_backfill_is_bounded_and_unknown_roots_do_not_restart_it():
    runtime, _, calls, _ = history_runtime(1000)
    for _ in range(100):
        before = dict(calls)
        with pytest.raises(DataUnavailable):
            runtime.source_for(exports_root=b'?' * 32)
        # A new head and an older-ancestor batch each have their own small bound.
        assert calls['headers'] - before['headers'] <= 2 * runtime.BACKFILL_BATCH_SIZE
        assert calls['blocks'] - before['blocks'] <= runtime.BACKFILL_BATCH_SIZE
        if runtime._canonical_cursor is None and not runtime._backfill_pending:
            break
    else:
        pytest.fail('bounded backfill made no progress')
    finished = dict(calls)
    for _ in range(3):
        with pytest.raises(DataUnavailable):
            runtime.source_for(exports_root=b'?' * 32)
    assert calls == finished


def test_extending_or_reorganizing_head_does_not_rescan_completed_history():
    runtime, headers, calls, h = history_runtime(300)
    while True:
        runtime._backfill_sources()
        if runtime._canonical_cursor is None and not runtime._backfill_pending:
            break
    headers[h(301)] = SimpleNamespace(parent=h(300), timeslot=301)
    runtime.app.state_storage.block_hash = h(301)
    before = dict(calls)
    runtime._backfill_sources()
    assert calls['headers'] - before['headers'] == 1
    assert calls['blocks'] - before['blocks'] == 1
    assert runtime.canonical(h(0)) and runtime.canonical(h(301))

    fork = b'f' * 32
    headers[fork] = SimpleNamespace(parent=h(299), timeslot=301)
    runtime.app.state_storage.block_hash = fork
    before = dict(calls)
    runtime._backfill_sources()
    assert calls['headers'] - before['headers'] == 1
    assert calls['blocks'] - before['blocks'] == 1
    assert runtime.canonical(fork) and runtime.canonical(h(299))
    assert not runtime.canonical(h(300)) and not runtime.canonical(h(301))


def test_background_backfill_yields_between_batches():
    async def run():
        runtime, _, calls, h = history_runtime(1000)
        runtime._backfill_wakeup.set()
        task = asyncio.create_task(runtime._backfill_worker())
        previous = 0
        passes = 0
        try:
            while passes < 100:
                await asyncio.sleep(0)
                passes += 1
                assert calls['blocks'] - previous <= runtime.BACKFILL_BATCH_SIZE
                previous = calls['blocks']
                if runtime._canonical_cursor is None and not runtime._backfill_pending:
                    break
            assert passes > 1
            assert calls['blocks'] == 1001
            assert runtime.canonical(h(0))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_corrupt_complete_exports_remain_retryable(source_data):
    runtime, source, _, exports = local_runtime(source_data)
    runtime.store.store_segments(D3LEntry(source.spec.exports_root, [bytes(4104)]))
    with pytest.raises(DataUnavailable, match='do not match'):
        runtime._local_import(source.spec.exports_root, 0)
    runtime.store.store_segments(D3LEntry(source.spec.exports_root, exports))
    assert runtime._local_import(source.spec.exports_root, 0).segment == exports[0]


def test_valid_complete_exports_still_reject_invalid_manifest_index(source_data):
    runtime, source, _, exports = local_runtime(source_data)
    runtime.store.store_segments(D3LEntry(source.spec.exports_root, exports))
    with pytest.raises(ProcessWorkpackageError, match='index out of range') as error:
        runtime._local_import(source.spec.exports_root, 1)
    assert not isinstance(error.value, DataUnavailable)


def test_restored_historical_state_repairs_source_without_changing_head(backfill_app):
    app, registration, _, historical = backfill_app
    runtime = app.runtime.availability
    changes = app.state_storage.change_sets[registration.header.hash]
    key = WELL_KNOWN_STORAGE_KEYS[6]
    entropy = changes.pop(key)
    package_hash = registration.extrinsic.guarantees[0].report.package_spec.hash
    with pytest.raises(DataUnavailable):
        runtime.source_for(package_hash=package_hash)
    assert app.d3l_store.sources() == []
    changes[key] = entropy
    assert runtime.source_for(package_hash=package_hash).validators == historical
