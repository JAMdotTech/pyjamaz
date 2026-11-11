"""Retained history can arrive after its availability backfill attempt."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pyjamaz.availability import DataUnavailable, build_availability_artifacts
from pyjamaz.constants import WELL_KNOWN_STORAGE_KEYS
from pyjamaz.graypaper_constants import CORE_COUNT
from pyjamaz.models.block import Block, Extrinsic
from pyjamaz.models.common import Credential, Guarantee
from pyjamaz.models.state import AssurancesState
from test.test_availability_lifecycle import backfill_app
from test.test_local_availability_fixes import history_runtime


@pytest.mark.parametrize('extend_head', [False, True])
def test_restored_header_resumes_discovery_at_same_or_extended_head(extend_head):
    runtime, headers, calls, h = history_runtime(3)
    missing = headers.pop(h(2))
    assert runtime._backfill_sources() is False
    assert not runtime.canonical(h(1))
    assert calls['blocks'] == 0  # Wait for ancestry before chronological replay.
    for _ in range(3):
        before = dict(calls)
        assert runtime._backfill_sources() is False
        assert calls['headers'] - before['headers'] == 1
        assert calls['blocks'] == 0

    headers[h(2)] = missing
    if extend_head:
        headers[h(4)] = SimpleNamespace(parent=h(3), timeslot=4)
        runtime.app.state_storage.block_hash = h(4)
    runtime._backfill_sources()
    assert all(runtime.canonical(h(i)) for i in range(5 if extend_head else 4))
    assert calls['blocks'] == (5 if extend_head else 4)
    assert runtime._canonical_cursor is None
    assert not runtime._backfill_pending and not runtime._backfill_retry


def remove_body(app, block):
    keys = (b'block-by-hash:' + block.header.hash,
            b'block:' + block.header.timeslot.to_bytes(4, 'little'))
    saved = {key: app.block_db.get(key) for key in keys}
    for key in keys:
        app.block_db.delete(key)
    return saved


@pytest.mark.parametrize('extend_head', [False, True])
def test_restored_registration_body_recovers_source_and_assurance(backfill_app, extend_head):
    app, registration, head, historical = backfill_app
    runtime = app.runtime.availability
    saved = remove_body(app, registration)
    package_hash = registration.extrinsic.guarantees[0].report.package_spec.hash
    with pytest.raises(DataUnavailable):
        runtime.source_for(package_hash=package_hash)
    assert registration.header.hash in runtime._backfill_retry
    assert head.header.hash in runtime._backfill_retry

    for key, value in saved.items():
        app.block_db.put(key, value)
    if extend_head:
        next_block = Block(replace(head.header, parent=head.header.hash, timeslot=3), Extrinsic.default())
        next_block.header.extrinsic_hash = next_block.extrinsic.generate_extrinsic_hash()
        app.state_storage.set_header(next_block.header)
        app.state_storage.commit()
        asyncio.run(app.store_block(next_block))

    # Exercise the replay worker's path before lookup can use targeted repair hints.
    runtime._backfill_sources()
    source = app.d3l_store.source_for(package_hash=package_hash)
    assert source.registered_block == registration.header.hash
    assert source.validators == historical
    assert source.assured_block == head.header.hash
    assert source.assured_slot == head.header.timeslot
    assert not runtime._backfill_retry


def test_missing_body_does_not_block_an_independent_later_registration(backfill_app):
    app, registration, head, _ = backfill_app
    runtime = app.runtime.availability
    remove_body(app, registration)
    spec = build_availability_artifacts(b'n' * 32, b'new bundle', [b'y' * 4104], 6).spec
    report = replace(registration.extrinsic.guarantees[0].report, package_spec=spec)
    later = Block(replace(head.header, parent=head.header.hash, timeslot=3), Extrinsic.default())
    later.extrinsic.guarantees = [Guarantee(report, 3, [Credential(0, bytes(64))])]
    later.header.extrinsic_hash = later.extrinsic.generate_extrinsic_hash()
    app.state_storage.set_header(later.header)
    app.state_storage.commit()
    asyncio.run(app.store_block(later))

    source = runtime.source_for(package_hash=spec.hash)
    assert source.registered_block == later.header.hash
    assert source.spec.erasure_shards == 6
    assert registration.header.hash in runtime._backfill_retry


def test_missing_parent_assurance_state_does_not_withhold_same_block_guarantee(backfill_app):
    app, registration, head, _ = backfill_app
    runtime = app.runtime.availability
    spec = build_availability_artifacts(b'n' * 32, b'new bundle', [b'y' * 4104], 6).spec
    report = replace(registration.extrinsic.guarantees[0].report, package_spec=spec)
    mixed = Block(replace(head.header), replace(head.extrinsic))
    mixed.extrinsic.guarantees = [Guarantee(report, 2, [Credential(0, bytes(64))])]
    mixed.header.extrinsic_hash = mixed.extrinsic.generate_extrinsic_hash()
    app.state_storage.set_header(mixed.header)
    app.state_storage.put(WELL_KNOWN_STORAGE_KEYS[8], app.working_state.validator_pool.to_jam_bytes().to_bytes())
    app.state_storage.put(WELL_KNOWN_STORAGE_KEYS[10], AssurancesState([None] * CORE_COUNT).to_jam_bytes().to_bytes())
    app.state_storage.commit()
    asyncio.run(app.store_block(mixed))
    changes = app.state_storage.change_sets[registration.header.hash]
    pending = changes.pop(WELL_KNOWN_STORAGE_KEYS[10])

    source = runtime.source_for(package_hash=spec.hash)
    assert source.registered_block == mixed.header.hash
    assert mixed.header.hash in runtime._backfill_retry
    older_hash = registration.extrinsic.guarantees[0].report.package_spec.hash
    assert app.d3l_store.source_for(package_hash=older_hash).assured_block is None

    changes[WELL_KNOWN_STORAGE_KEYS[10]] = pending
    runtime._backfill_sources()
    assert app.d3l_store.source_for(package_hash=older_hash).assured_block == mixed.header.hash
    assert not runtime._backfill_retry


@pytest.mark.parametrize('gap', ['header', 'body'])
def test_background_backfill_waits_for_a_later_wakeup_when_history_is_missing(gap):
    async def run():
        runtime, headers, calls, h = history_runtime(3)
        if gap == 'header':
            missing = headers.pop(h(2))
        else:
            original = runtime.app.retrieve_block_by_hash
            unavailable = {h(2)}

            def block(block_hash):
                value = original(block_hash)
                return None if block_hash in unavailable else value

            runtime.app.retrieve_block_by_hash = block
        runtime._backfill_wakeup.set()
        task = asyncio.create_task(runtime._backfill_worker())
        try:
            for _ in range(5):
                await asyncio.sleep(0)
            stopped = dict(calls)
            for _ in range(5):
                await asyncio.sleep(0)
            assert calls == stopped
            assert not task.done()
            if gap == 'header':
                headers[h(2)] = missing
            else:
                unavailable.clear()
            runtime._backfill_wakeup.set()
            for _ in range(5):
                await asyncio.sleep(0)
            assert runtime.canonical(h(0))
            assert runtime._canonical_cursor is None
            assert not runtime._backfill_pending and not runtime._backfill_retry
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_missing_body_retries_remain_bounded():
    runtime, _, calls, _ = history_runtime(200)
    original = runtime.app.retrieve_block_by_hash

    def unavailable(block_hash):
        original(block_hash)
        return None

    runtime.app.retrieve_block_by_hash = unavailable
    for _ in range(20):
        before = dict(calls)
        more = runtime._backfill_sources()
        assert calls['headers'] - before['headers'] <= 2 * runtime.BACKFILL_BATCH_SIZE
        assert calls['blocks'] - before['blocks'] <= runtime.BACKFILL_BATCH_SIZE
        if not more:
            break
    else:
        pytest.fail('initial backfill did not stop at unavailable bodies')
    assert len(runtime._backfill_retry) == 200  # No body is needed for genesis.
    for _ in range(3):
        before = calls['blocks']
        assert runtime._backfill_sources() is False
        assert calls['blocks'] - before == runtime.BACKFILL_BATCH_SIZE
        assert len(runtime._backfill_retry) == 200
