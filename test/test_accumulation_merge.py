"""Parallel accumulation merge rules, independent of the released PVM programs."""

import asyncio
from copy import deepcopy

import pytest

from pyjamaz.exceptions import BlockValidationError, StateKeyNoResult
from pyjamaz.graypaper_constants import CORE_COUNT, MAXIMUM_AUTHORIZATION_QUEUE_ITEMS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.hostcalls.models import PvmAccumulateOutput
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import (
    AccumulationStateComponents,
    AuthorizerQueuesState,
    EntropyState,
    PendingChanges,
    PrivilegedServicesState,
    ServiceAccount,
    ServicesState,
    TimeslotState,
    ValidatorQueueState,
)
from pyjamaz.state.components import Services
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


OLD_BLOB = b"previous service code"
OLD_HASH = blake2b_256_hash(OLD_BLOB)
OLD_KEY = bytes([7]) * 32
NEW_KEY = bytes([8]) * 32
NEW_BLOB = b"new service code"
NEW_HASH = blake2b_256_hash(NEW_BLOB)
SLOT = 43


def account(balance=100_000, *, populated=False):
    return ServiceAccount(
        code_hash=OLD_HASH if populated else NEW_HASH,
        balance=balance,
        gas_limit_accumulate=0,
        gas_limit_on_transfer=0,
        footprint_storage_bytes=100 if populated else 0,
        footprint_storage_items=2 if populated else 0,
        deposit_offset=0,
        creation_slot=1,
        last_accumulation_slot=1,
        parent_service=0,
        storage_items={OLD_KEY: b"old value"} if populated else {},
        preimages={OLD_HASH: OLD_BLOB} if populated else {},
        preimage_availability={(OLD_HASH, len(OLD_BLOB)): [1, 2]} if populated else {},
    )


def store_account_with_maps(services, service_id, value, *, save_to_tx=False):
    services.store_service_account(service_id, deepcopy(value), save_to_tx=save_to_tx)
    for key, item in value.storage_items.items():
        services.store_storage_item(service_id, key, item, save_to_tx=save_to_tx)
    for blob in value.preimages.values():
        services.store_preimage(service_id, blob, save_to_tx=save_to_tx)
    for (preimage_hash, length), availability in value.preimage_availability.items():
        services.store_preimage_availability(
            service_id, preimage_hash, length, availability, save_to_tx=save_to_tx
        )


def eject_populated_account(services, service_id):
    services.delete_service_account(service_id)
    services.delete_storage_item(service_id, OLD_KEY)
    services.delete_preimage(service_id, OLD_HASH)
    services.delete_preimage_availability(service_id, OLD_HASH, len(OLD_BLOB))


def setup_round(monkeypatch, initial_accounts, *, backing_only=False):
    storage = StateStorage(InMemoryStorageEngine())
    services = ServicesState()
    services.set_state_storage(storage)
    services.pending_changes = PendingChanges()
    for service_id, value in initial_accounts.items():
        store_account_with_maps(services, service_id, value, save_to_tx=True)
    if not backing_only:
        services.add_pending_changes()
    services.pending_changes = PendingChanges()

    state = AccumulationStateComponents(
        services=services,
        validator_queue=ValidatorQueueState(validators=[]),
        authorizer_queues=AuthorizerQueuesState(
            authorizer_queues=[
                [bytes(32)] * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for _ in range(CORE_COUNT)
            ]
        ),
        privileged_services=PrivilegedServicesState(
            manager=99,
            assigners=[99] * CORE_COUNT,
            delegator=99,
            registrar=99,
            always_accumulators={},
        ),
    )
    component = Services(BlockContext(), AppContext(state_storage=storage))
    monkeypatch.setattr("pyjamaz.state.components.USE_THREAD_POOL_ACCUMULATE", False)

    def run(actions):
        def invoke(*, accumulation_state, service_id, **kwargs):
            invocation_state = deepcopy(accumulation_state)
            invocation_state.services.pending_changes = PendingChanges()
            provisions = actions[service_id](invocation_state.services) or []
            return PvmAccumulateOutput(invocation_state, [], None, 0, provisions)

        monkeypatch.setattr(component, "single_step_accumulation", invoke)
        return asyncio.run(component.parallel_accumulation(
            accumulation_state=state,
            deferred_transfers=[],
            work_reports=[],
            auto_accumulate_services={service_id: 1 for service_id in actions},
            post_state_timeslot=TimeslotState(number=SLOT),
            post_state_entropy=EntropyState(entropy=[bytes(32)] * 4),
        ))

    return services, run


def persisted(services):
    """Read committed transaction data without consulting the pending delta."""
    view = ServicesState()
    view.set_state_storage(services.state_storage)
    view.pending_changes = PendingChanges()
    return view


@pytest.mark.parametrize("assigners", [(1, 2), (2, 1), (1, 1)])
def test_authorizer_queues_merge_independently_per_core(monkeypatch, assigners):
    services, _ = setup_round(monkeypatch, {1: account(), 2: account(), 3: account()})
    state = AccumulationStateComponents(
        services=services,
        validator_queue=ValidatorQueueState(validators=[]),
        authorizer_queues=AuthorizerQueuesState(
            authorizer_queues=[
                [bytes(32)] * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for _ in range(CORE_COUNT)
            ],
        ),
        privileged_services=PrivilegedServicesState(
            manager=99, assigners=list(assigners) + [99] * (CORE_COUNT - 2),
            delegator=99, registrar=99, always_accumulators={},
        ),
    )
    component = Services(BlockContext(), AppContext(state_storage=services.state_storage))
    updates = [[bytes([c + 1]) * 32] * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for c in range(2)]

    def invoke(*, accumulation_state, service_id, **kwargs):
        # Each service starts with its own snapshot of the same prior queues.
        snapshot = deepcopy(accumulation_state)
        snapshot.services.pending_changes = PendingChanges()
        for c, assigner in enumerate(assigners):
            if service_id == assigner:
                snapshot.authorizer_queues.authorizer_queues[c] = updates[c]
        return PvmAccumulateOutput(snapshot, [], None, 0, [])

    monkeypatch.setattr(component, "single_step_accumulation", invoke)
    output = asyncio.run(component.parallel_accumulation(
        accumulation_state=state, deferred_transfers=[], work_reports=[],
        auto_accumulate_services={1: 1, 2: 1, 3: 1},
        post_state_timeslot=TimeslotState(number=SLOT),
        post_state_entropy=EntropyState(entropy=[bytes(32)] * 4),
    ))

    expected = updates + [[bytes(32)] * MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for _ in range(CORE_COUNT - 2)]
    assert output.accumulation_state.authorizer_queues.authorizer_queues == expected


@pytest.mark.parametrize("registrar", [1, 3])
@pytest.mark.parametrize("accumulates", [False, True])
@pytest.mark.parametrize("backing_only", [False, True])
def test_foreign_eject_and_recreate_preserves_prior_account(
    monkeypatch, registrar, accumulates, backing_only
):
    original = account(populated=True)
    services, run = setup_round(
        monkeypatch, {registrar: account(), 2: original}, backing_only=backing_only
    )

    def recreate(state):
        eject_populated_account(state, 2)
        replacement = account(balance=123)
        replacement.creation_slot = SLOT
        state.store_service_account(2, replacement)
        state.store_preimage_availability(2, NEW_HASH, len(NEW_BLOB), [])

    def own_update(state):
        own = state.retrieve_service_account(2)
        own.balance += 7
        state.store_service_account(2, own)
        state.store_storage_item(2, NEW_KEY, b"own write")

    actions = {registrar: recreate}
    if accumulates:
        actions[2] = own_update
    run(actions)

    committed = persisted(services)
    actual = committed.retrieve_service_account(2)
    assert actual.code_hash == original.code_hash
    assert actual.balance == original.balance + (7 if accumulates else 0)
    assert actual.creation_slot == original.creation_slot
    assert actual.footprint_storage_bytes == original.footprint_storage_bytes
    assert committed.retrieve_storage_item(2, OLD_KEY) == b"old value"
    assert committed.retrieve_preimage(2, OLD_HASH) == OLD_BLOB
    assert committed.retrieve_preimage_availability(2, OLD_HASH, len(OLD_BLOB)) == [1, 2]
    with pytest.raises(StateKeyNoResult):
        committed.retrieve_preimage_availability(2, NEW_HASH, len(NEW_BLOB))
    if accumulates:
        assert committed.retrieve_storage_item(2, NEW_KEY) == b"own write"
    if not backing_only:
        detached = services.services[2]
        assert detached.balance == actual.balance
        assert detached.storage_items[OLD_KEY] == b"old value"
        assert detached.preimages == original.preimages
        assert detached.preimage_availability == original.preimage_availability


@pytest.mark.parametrize("ejector", [1, 3])
def test_ejection_wins_over_recipient_updates_and_pending_reapplication(monkeypatch, ejector):
    services, run = setup_round(monkeypatch, {ejector: account(), 2: account(populated=True)})

    def recipient(state):
        own = state.retrieve_service_account(2)
        own.balance += 7
        state.store_service_account(2, own)
        state.store_storage_item(2, NEW_KEY, b"own write")
        state.store_preimage(2, NEW_BLOB)
        state.store_preimage_availability(2, NEW_HASH, len(NEW_BLOB), [])

    run({ejector: lambda state: eject_populated_account(state, 2), 2: recipient})

    for _ in range(2):
        services.add_pending_changes()
        assert 2 not in services.services
        assert not services.service_exists(2)
        committed = persisted(services)
        assert not committed.service_exists(2)
        for key in (OLD_KEY, NEW_KEY):
            with pytest.raises(StateKeyNoResult):
                committed.retrieve_storage_item(2, key)
        for blob in (OLD_BLOB, NEW_BLOB):
            blob_hash = blake2b_256_hash(blob)
            with pytest.raises(StateKeyNoResult):
                committed.retrieve_preimage(2, blob_hash)
            with pytest.raises(StateKeyNoResult):
                committed.retrieve_preimage_availability(2, blob_hash, len(blob))


def test_deleted_service_id_can_be_created_in_a_later_round(monkeypatch):
    services, run = setup_round(monkeypatch, {1: account(), 2: account(populated=True)})
    run({1: lambda state: eject_populated_account(state, 2)})
    assert not services.service_exists(2)

    replacement = account(balance=456)
    replacement.storage_items = {NEW_KEY: b"new value"}
    replacement.preimages = {NEW_HASH: NEW_BLOB}
    replacement.preimage_availability = {(NEW_HASH, len(NEW_BLOB)): [SLOT]}
    run({1: lambda state: store_account_with_maps(state, 2, replacement)})

    assert services.services[2] == replacement
    committed = persisted(services)
    assert committed.retrieve_service_account(2).balance == replacement.balance
    assert committed.retrieve_storage_item(2, NEW_KEY) == b"new value"
    assert committed.retrieve_preimage(2, NEW_HASH) == NEW_BLOB
    with pytest.raises(StateKeyNoResult):
        committed.retrieve_preimage(2, OLD_HASH)


def test_foreign_provision_is_ignored_when_recipient_is_deleted(monkeypatch):
    target = account(populated=True)
    target.preimage_availability[(NEW_HASH, len(NEW_BLOB))] = []
    services, run = setup_round(monkeypatch, {1: account(), 2: target, 3: account()})

    def eject(state):
        eject_populated_account(state, 2)
        state.delete_preimage_availability(2, NEW_HASH, len(NEW_BLOB))

    run({1: lambda state: [(2, NEW_BLOB)], 3: eject})
    assert not persisted(services).service_exists(2)
    with pytest.raises(StateKeyNoResult):
        persisted(services).retrieve_preimage(2, NEW_HASH)


@pytest.mark.parametrize("new_recipient", [False, True])
def test_foreign_provision_uses_request_created_in_the_same_round(monkeypatch, new_recipient):
    recipient = 9 if new_recipient else 2
    initial = {1: account(), 2: account()}
    services, run = setup_round(monkeypatch, initial)

    def request(state):
        own = account() if new_recipient else state.retrieve_service_account(recipient)
        state.store_service_account(recipient, own)
        state.store_preimage_availability(recipient, NEW_HASH, len(NEW_BLOB), [])

    run({1: lambda state: [(recipient, NEW_BLOB)], 2: request})
    committed = persisted(services)
    assert committed.retrieve_preimage(recipient, NEW_HASH) == NEW_BLOB
    assert committed.retrieve_preimage_availability(recipient, NEW_HASH, len(NEW_BLOB)) == [SLOT]
    assert services.services[recipient].preimages[NEW_HASH] == NEW_BLOB


def test_foreign_provision_can_target_an_account_only_in_backing_storage(monkeypatch):
    target = account()
    target.preimage_availability[(NEW_HASH, len(NEW_BLOB))] = []
    services, run = setup_round(monkeypatch, {1: account(), 2: target}, backing_only=True)
    assert services.services == {}

    run({1: lambda state: [(2, NEW_BLOB)]})

    committed = persisted(services)
    assert committed.retrieve_preimage(2, NEW_HASH) == NEW_BLOB
    assert committed.retrieve_preimage_availability(2, NEW_HASH, len(NEW_BLOB)) == [SLOT]


def test_duplicate_new_service_ids_reject_before_committing(monkeypatch):
    services, run = setup_round(monkeypatch, {1: account(), 3: account()})
    transaction_before = deepcopy(services.state_storage.transaction)

    with pytest.raises(BlockValidationError, match="Conflicting new service account IDs"):
        run({
            1: lambda state: state.store_service_account(9, account(balance=123)),
            3: lambda state: state.store_service_account(9, account(balance=456)),
        })

    assert services.state_storage.transaction == transaction_before
    assert not services.service_exists(9)


def test_new_service_created_then_deleted_leaves_no_orphan_maps(monkeypatch):
    services, run = setup_round(monkeypatch, {1: account()})

    def create_then_delete(state):
        store_account_with_maps(state, 9, account(populated=True))
        state.delete_service_account(9)

    run({1: create_then_delete})

    committed = persisted(services)
    assert not committed.service_exists(9)
    with pytest.raises(StateKeyNoResult):
        committed.retrieve_storage_item(9, OLD_KEY)
    with pytest.raises(StateKeyNoResult):
        committed.retrieve_preimage(9, OLD_HASH)
    with pytest.raises(StateKeyNoResult):
        committed.retrieve_preimage_availability(9, OLD_HASH, len(OLD_BLOB))
