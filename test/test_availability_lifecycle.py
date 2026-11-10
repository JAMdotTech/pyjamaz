import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from pyjamaz import app as app_module
from pyjamaz.app import PyjamazApp
from pyjamaz.availability import DataUnavailable, build_availability_artifacts
from pyjamaz.constants import MESSAGE_TYPES, WELL_KNOWN_STORAGE_KEYS
from pyjamaz.d3l import AvailabilitySource, DataAvailabilityStore
from pyjamaz.graypaper_constants import CORE_COUNT, EPOCH_TIMESLOTS, ROTATION_PERIOD_CORE
from pyjamaz.models.block import Assurance as ExtrinsicAssurance, Block, Extrinsic, Header
from pyjamaz.models.common import Assurance, Credential, Guarantee, RefinementContext, ValidatorData, WorkReport
from pyjamaz.models.context import AppContext
from pyjamaz.models.state import AssurancesState, EntropyState, JamState, ValidatorArchiveState, ValidatorPoolState
from pyjamaz.runtime.availability import AvailabilityRuntime
from pyjamaz.runtime.node_runtime import NodeRuntime
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import FileStorageEngine, InMemoryStorageEngine
from pyjamaz.transport.pubsub import PubSub


@pytest.fixture
def source_data():
    exports = [b'x' * 4104]
    artifacts = build_availability_artifacts(b'p' * 32, b'bundle', exports, 6)
    report = WorkReport(artifacts.spec, RefinementContext(*([bytes(32)] * 4), 0, []),
                        0, bytes(32), 0, b'', {}, [])
    validators = [ValidatorData(bytes(32), bytes([i]) * 32, bytes(144), bytes(128)) for i in range(6)]
    return artifacts, report, validators, exports


def test_previous_rotation_signers_and_post_transition_assurers_are_recorded_separately(source_data):
    _, report, validators, _ = source_data
    historical = replace(validators[0], ed25519=b'h' * 32, metadata=b'm' * 128)
    block = Block(Header.default(), Extrinsic.default())
    block.header.timeslot = EPOCH_TIMESLOTS
    block.extrinsic.guarantees = [Guarantee(report, block.header.timeslot - ROTATION_PERIOD_CORE,
                                          [Credential(0, bytes(64))])]
    app = SimpleNamespace(d3l_store=DataAvailabilityStore(InMemoryStorageEngine()),
                          config=SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=validators[0].ed25519))),
                          state_storage=SimpleNamespace(finalized_block_hash=None, parents={}),
                          retrieve_block_header=lambda _: None)
    runtime = AvailabilityRuntime(app)
    context = SimpleNamespace(
        guarantor_assignments=[SimpleNamespace(validator_ed25519=validators[0].ed25519)],
        prev_guarantor_assignments=[SimpleNamespace(validator_ed25519=historical.ed25519)],
    )
    runtime.record_committed(block, validators, [historical], context, [])
    source = app.d3l_store.source_for(package_hash=report.package_spec.hash)
    assert source.validators == validators
    assert source.guarantors == [historical]
    assert runtime.assigned_index(source) == 0


@pytest.fixture
def transition_app(monkeypatch, source_data):
    _, report, validators, _ = source_data
    app = PyjamazApp.__new__(PyjamazApp)
    app.app_context = AppContext()
    app.block_context = MagicMock()
    app.block_context.guarantor_assignments = [SimpleNamespace(validator_ed25519=validators[0].ed25519)]
    app.block_context.accumulatable_work_reports = []
    app.block_context.queued_work_reports = []
    app.working_state = SimpleNamespace(**{name: MagicMock() for name in JamState.__dataclass_fields__})
    app.working_state.state_root = bytes(32)
    app.initialize = AsyncMock()
    app.store_jam_state = AsyncMock()
    app.state_storage = MagicMock()
    app.state_storage.get_parent.return_value = Header.default()
    app.state_storage.finalized_block_hash = None
    app.state_storage.state_root.return_value = bytes(32)
    app.d3l_store = DataAvailabilityStore(InMemoryStorageEngine())
    app.config = SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=validators[0].ed25519)))
    app.retrieve_block_header = lambda _: None
    app.components = MagicMock()
    app.components.validator_pool.state_transition.return_value.post_state.validators = validators
    app.components.validator_archive.state_transition.return_value.post_state.validators = []
    app.components.assurances.state_transition_after_assurances.return_value.reported = []
    app.components.services.state_transition_accumulation = AsyncMock(return_value=MagicMock())
    app.components.services.state_transition_after_preimages = AsyncMock(return_value=MagicMock())
    app.runtime = SimpleNamespace(availability=AvailabilityRuntime(app))
    monkeypatch.setattr(app_module, 'BlockValidation', Mock())
    monkeypatch.setattr(app_module, 'SKIP_VALIDATE_GUARANTEES', False)
    monkeypatch.setattr(app_module.settings, 'SKIP_TIMESLOT_WALL_CLOCK_CHECK', True)
    monkeypatch.setattr(Header, 'set_author_bandersnatch_key', Mock())
    block = Block(Header.default(), Extrinsic.default())
    block.header.timeslot = 1
    block.extrinsic.guarantees = [Guarantee(report, 1, [Credential(0, bytes(64))])]
    block.header.extrinsic_hash = block.extrinsic.generate_extrinsic_hash()
    return app, block


def test_source_metadata_is_published_after_successful_state_commit(transition_app):
    app, block = transition_app
    committed = []
    app.state_storage.commit.side_effect = lambda: committed.append(True)
    original = app.runtime.availability.record_committed

    def record(*args):
        assert committed == [True]
        original(*args)

    app.runtime.availability.record_committed = record
    asyncio.run(app.state_transition(block))
    source = app.d3l_store.source_for(package_hash=block.extrinsic.guarantees[0].report.package_spec.hash)
    assert source.registered_block == block.header.hash
    app.components.assurances.validate_guarantees.assert_called_once()


def test_failed_state_commit_does_not_publish_source_metadata(transition_app):
    app, block = transition_app
    app.state_storage.commit.side_effect = OSError('commit failed')
    with pytest.raises(OSError, match='commit failed'):
        asyncio.run(app.state_transition(block))
    assert app.d3l_store.sources() == []
    assert app.runtime.availability._queue.empty()


def test_skipped_guarantee_validation_does_not_publish_source_metadata(transition_app, monkeypatch):
    app, block = transition_app
    monkeypatch.setattr(app_module, 'SKIP_VALIDATE_GUARANTEES', True)
    asyncio.run(app.state_transition(block))
    assert app.d3l_store.sources() == []


def test_placeholder_finalized_signal_does_not_prune_and_real_finalization_does(source_data):
    async def run():
        artifacts, report, validators, exports = source_data
        app = PyjamazApp.__new__(PyjamazApp)
        app.block_db = InMemoryStorageEngine()
        app.state_storage = StateStorage(InMemoryStorageEngine())
        app.d3l_store = DataAvailabilityStore(InMemoryStorageEngine())
        app.config = SimpleNamespace(ring_data=b'')
        app.pubsub = PubSub()
        app.working_state = SimpleNamespace(statistics=MagicMock())
        genesis = Header.default()
        registration = replace(genesis, parent=genesis.hash, timeslot=1)
        assurance = replace(genesis, parent=registration.hash, timeslot=2)
        headers = {header.hash: header for header in (genesis, registration, assurance)}
        app.retrieve_block_header = headers.get
        app.state_storage.set_finalized_header(genesis)
        for header in (registration, assurance):
            app.state_storage.set_header(header)
            app.state_storage.commit()
        app.runtime = NodeRuntime(app)
        app.add_ancestor_header = AsyncMock()
        app.store_block = AsyncMock()
        app.d3l_store.store_work_report(report, b'bundle', exports, artifacts=artifacts)
        app.d3l_store.register_source(AvailabilitySource(report, validators, validators[:2],
                                                       registration.hash, 1, assurance.hash, 2))
        app.d3l_store.prune = Mock(wraps=app.d3l_store.prune)
        await app.add_ancestor_block(Block(assurance, Extrinsic.default()))
        messages = [await app.pubsub.receive_stream.receive() for _ in range(3)]
        assert [message.topic for message in messages] == [MESSAGE_TYPES.BEST_BLOCK, MESSAGE_TYPES.FINALIZED_BLOCK,
                                                         MESSAGE_TYPES.STATISTICS]
        for message in messages:
            for subscriber in app.pubsub.subscriptions[message.topic.value]:
                await subscriber(message.data)
        app.d3l_store.prune.assert_not_called()
        assert app.d3l_store.retrieve_validator_shard(report.package_spec, 0) == artifacts.shards[0]
        await app.finalize(assurance.hash)
        assert app.state_storage.finalized_block_hash == assurance.hash
        assert app.retrieve_finalized_head() == assurance.hash
        app.d3l_store.prune.assert_called_once()
        with pytest.raises(DataUnavailable, match='audit'):
            app.d3l_store.retrieve_validator_shard(report.package_spec, 0)
        assert app.d3l_store.retrieve_segment_shard(report.package_spec, 0, 0)[0]
        await app.finalize(assurance.hash)
        app.d3l_store.prune.assert_called_once()

    asyncio.run(run())


@pytest.fixture
def backfill_app(monkeypatch, tmp_path, request):
    from pyjamaz import erasure, graypaper_constants

    # Exercise a historical set larger than Tiny's active set using Full's bounds.
    monkeypatch.setattr(erasure, 'valid_validator_count',
                        lambda count: graypaper_constants.valid_validator_count(count, core_count=341))
    for state in (ValidatorPoolState, ValidatorArchiveState):
        monkeypatch.setattr(state.__dataclass_fields__['validators'].metadata['codec'], 'maximum', 1023)
    historical = [ValidatorData(bytes(32), bytes([i + 10]) * 32, bytes(144), bytes(128)) for i in range(9)]
    current = [replace(validator, ed25519=bytes([i + 40]) * 32) for i, validator in enumerate(historical[:6])]
    spec = build_availability_artifacts(b'p' * 32, b'old bundle', [b'x' * 4104], 9).spec
    report = WorkReport(spec, RefinementContext(*([bytes(32)] * 4), 0, []), 0, bytes(32), 0, b'', {}, [])
    genesis = Header.default()
    registration = Block(replace(genesis, parent=genesis.hash, timeslot=1), Extrinsic.default())
    registration.extrinsic.guarantees = [Guarantee(report, 1, [Credential(0, bytes(64))])]
    registration.header.extrinsic_hash = registration.extrinsic.generate_extrinsic_hash()
    head = Block(replace(genesis, parent=registration.header.hash, timeslot=2), Extrinsic.default())
    head.extrinsic.assurances = [
        ExtrinsicAssurance(registration.header.hash, [True] + [False] * (CORE_COUNT - 1), i, bytes(64))
        for i in range(getattr(request, 'param', 7))
    ]
    head.header.extrinsic_hash = head.extrinsic.generate_extrinsic_hash()
    app = PyjamazApp.__new__(PyjamazApp)
    app.block_db = InMemoryStorageEngine()
    app.state_storage = StateStorage(InMemoryStorageEngine())
    app.d3l_store = DataAvailabilityStore(FileStorageEngine(str(tmp_path)))
    app.config = SimpleNamespace(keys=SimpleNamespace(ed25519=SimpleNamespace(public_key=historical[0].ed25519)))
    app.working_state = SimpleNamespace(validator_pool=ValidatorPoolState(current))
    app.state_storage.set_finalized_header(genesis)
    app.state_storage.set_header(registration.header)
    for component, value in ((8, ValidatorPoolState(historical)), (9, ValidatorArchiveState(current)),
                             (6, EntropyState([bytes(32)] * 4)),
                             (10, AssurancesState([Assurance(registration.extrinsic.guarantees[0], 1)]
                                                   + [None] * (CORE_COUNT - 1)))):
        app.state_storage.put(WELL_KNOWN_STORAGE_KEYS[component], value.to_jam_bytes().to_bytes())
    app.state_storage.commit()
    app.state_storage.set_header(head.header)
    app.state_storage.put(WELL_KNOWN_STORAGE_KEYS[8], ValidatorPoolState(current).to_jam_bytes().to_bytes())
    app.state_storage.put(WELL_KNOWN_STORAGE_KEYS[10], AssurancesState([None] * CORE_COUNT).to_jam_bytes().to_bytes())
    app.state_storage.commit()

    async def persist():
        await app.store_block_header(genesis)
        await app.store_block(registration)
        await app.store_block(head)

    asyncio.run(persist())
    app.runtime = SimpleNamespace(availability=AvailabilityRuntime(app))
    return app, registration, head, historical


def test_backfill_uses_committed_historical_state_and_retries_missing_source_at_same_head(backfill_app):
    app, registration, _, historical = backfill_app
    runtime = app.runtime.availability
    package_hash = registration.extrinsic.guarantees[0].report.package_spec.hash
    source = runtime.source_for(package_hash=package_hash)
    assert source.validators == historical
    assert source.spec.erasure_shards == 9
    assert len(app.working_state.validator_pool.validators) == 6
    assert source.guarantors == historical[:1]
    app.d3l_store.storage_engine.delete(b'source-v1:' + source.identity)
    assert runtime.source_for(package_hash=package_hash) == source


def test_backfill_does_not_fabricate_missing_historical_state(backfill_app):
    app, registration, _, _ = backfill_app
    del app.state_storage.change_sets[registration.header.hash][WELL_KNOWN_STORAGE_KEYS[6]]
    with pytest.raises(DataUnavailable, match='chain-backed'):
        app.runtime.availability.source_for(package_hash=registration.extrinsic.guarantees[0].report.package_spec.hash)
    assert app.d3l_store.sources() == []


def test_backfill_preserves_existing_assurance_reference(backfill_app):
    app, registration, head, _ = backfill_app
    runtime = app.runtime.availability
    report = registration.extrinsic.guarantees[0].report
    source = runtime.source_for(package_hash=report.package_spec.hash)
    app.d3l_store.mark_assured(report, head.header.hash, head.header.timeslot, lambda _: True)
    retained = replace(source, assured_block=head.header.hash, assured_slot=head.header.timeslot)
    app.runtime.availability = AvailabilityRuntime(app)
    app.runtime.availability._backfill_sources()
    assert app.runtime.availability.source_for(package_hash=report.package_spec.hash) == retained


@pytest.mark.parametrize('backfill_app', [6, 7], indirect=True)
def test_backfill_replays_assurances_against_prior_set_in_chronological_order(backfill_app):
    app, registration, head, _ = backfill_app
    source = app.runtime.availability.source_for(package_hash=registration.extrinsic.guarantees[0].report.package_spec.hash)
    # Nine prior assurers require seven votes, even though the post-state has six.
    if len(head.extrinsic.assurances) == 7:
        assert source.assured_block == head.header.hash
        assert source.assured_slot == 2
    else:
        assert source.assured_block is None
        assert source.assured_slot is None


def test_backfill_retains_audit_payload_when_assurance_parent_context_is_missing(backfill_app):
    app, registration, _, _ = backfill_app
    del app.state_storage.change_sets[registration.header.hash][WELL_KNOWN_STORAGE_KEYS[10]]
    source = app.runtime.availability.source_for(package_hash=registration.extrinsic.guarantees[0].report.package_spec.hash)
    assert source.assured_block is None
