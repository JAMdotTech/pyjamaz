"""State transitions and service reads must preserve retained input snapshots."""

import asyncio
from copy import deepcopy

import pytest

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.models.block import Header
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import (
    AccumulationStateComponents,
    AuthorizerPoolsState,
    AuthorizerQueuesState,
    EntropyState,
    PendingChanges,
    PrivilegedServicesState,
    RecentBlock,
    RecentHistoryState,
    ReportedWorkPackage,
    SafroleState,
    ServiceAccount,
    ServiceActivityRecord,
    ServicesState,
    SlotSealerSeries,
    StatisticsState,
    StorageItemMap,
    TimeslotState,
    ValidatorArchiveState,
    ValidatorPoolState,
    ValidatorQueueState,
)
from pyjamaz.state.components import (
    AuthorizerPools, RecentHistory, Services, Statistics, ValidatorArchive, ValidatorPool,
)
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


HASH = b'h' * 32
OTHER_HASH = b'x' * 32


def account():
    return ServiceAccount(
        code_hash=HASH, balance=100_000, gas_limit_accumulate=0, gas_limit_on_transfer=0,
        footprint_storage_bytes=10, footprint_storage_items=1, deposit_offset=0,
        creation_slot=1, last_accumulation_slot=1, parent_service=0,
        storage_items={HASH: b'value'}, preimages={HASH: b'preimage'},
        preimage_availability={(HASH, 8): [1, 2]},
    )


def validator(key=HASH):
    return ValidatorData(key, key, bytes(144), bytes(128))


def services_state():
    state = ServicesState()
    state.set_state_storage(StateStorage(InMemoryStorageEngine()))
    state.pending_changes = PendingChanges(service_accounts={7: account(), 8: None})
    return state


def test_pending_account_reads_are_independent_until_stored():
    services = services_state()
    expected = deepcopy(services.pending_changes)
    first = services.retrieve_service_account(7)
    second = services.retrieve_service_account(7)

    first.balance += 1
    first.storage_items[HASH] = b'changed'
    first.preimages.clear()
    first.preimage_availability[(HASH, 8)].append(3)
    first.preimage_availability[(OTHER_HASH, 8)] = []

    assert services.pending_changes == expected
    assert second == expected.service_accounts[7]
    services.store_service_account(7, first)
    assert services.retrieve_service_account(7).balance == first.balance
    assert second.balance == expected.service_accounts[7].balance
    with pytest.raises(StateKeyNoResult):
        services.retrieve_service_account(8)


def test_storage_backed_account_copy_keeps_its_cache_isolated():
    original = account()
    original.storage_items = StorageItemMap(7, InMemoryStorageEngine())
    original.storage_items.cache[HASH] = b'value'

    cloned = original.copy()
    cloned.storage_items.cache[HASH] = b'changed'
    cloned.preimage_availability[(HASH, 8)].append(3)

    assert original.storage_items.cache == {HASH: b'value'}
    assert original.preimage_availability == {(HASH, 8): [1, 2]}


def test_history_transitions_preserve_input_records_and_mmr_peaks():
    original = RecentHistoryState(
        recent_blocks=[RecentBlock(
            header_hash=HASH, beefy_root=HASH, state_root=HASH,
            reported=[ReportedWorkPackage(HASH, HASH)],
        )],
        accumulation_output_log=[HASH],
    )
    before = deepcopy(original)
    header = Header.default()
    header.timeslot = 2
    header.parent_state_root = OTHER_HASH
    component = RecentHistory(BlockContext(), AppContext())
    intermediate = component.state_transition_intermediate(header, original).intermediate_state
    intermediate_before = deepcopy(intermediate)
    result = component.state_transition(header, [], intermediate, OTHER_HASH).post_state

    assert original == before
    assert intermediate == intermediate_before
    assert result.recent_blocks[0].state_root == OTHER_HASH
    assert result.accumulation_output_log != intermediate.accumulation_output_log
    result.recent_blocks[0].reported[0].exports_root = OTHER_HASH
    result.recent_blocks[0].reported.append(ReportedWorkPackage(OTHER_HASH, OTHER_HASH))
    result.accumulation_output_log.clear()
    assert original == before
    assert intermediate == intermediate_before


@pytest.mark.parametrize('epoch_change', [False, True])
def test_validator_transitions_copy_both_prior_and_rotated_entries(epoch_change):
    pool = ValidatorPoolState([validator()])
    archive = ValidatorArchiveState([validator()])
    safrole = SafroleState([validator(OTHER_HASH)], bytes(144), SlotSealerSeries(keys=[]), [])
    before = deepcopy((pool, archive, safrole))
    header = Header.default()
    header.timeslot = gp_const.EPOCH_TIMESLOTS if epoch_change else 1
    timeslot = TimeslotState(0)
    new_pool = ValidatorPool(BlockContext(), AppContext()).state_transition(
        header, timeslot, pool, safrole,
    ).post_state
    new_archive = ValidatorArchive(BlockContext(), AppContext()).state_transition(
        header, timeslot, archive, pool,
    ).post_state

    assert new_pool.validators == (safrole.validators if epoch_change else pool.validators)
    assert new_archive.validators == (pool.validators if epoch_change else archive.validators)
    new_pool.validators[0].ed25519 = bytes(32)
    new_archive.validators[0].metadata = b'a' * 128
    new_pool.validators.clear()
    assert (pool, archive, safrole) == before


@pytest.mark.parametrize('epoch_change', [False, True])
def test_statistics_updates_preserve_prior_records(epoch_change):
    original = StatisticsState.default()
    original.vals_current[0].blocks = 5
    original.cores[0].gas_used = 25
    original.services[7] = ServiceActivityRecord(provided_count=2)
    before = deepcopy(original)
    header = Header.default()
    header.timeslot = gp_const.EPOCH_TIMESLOTS if epoch_change else 1
    context = BlockContext(reporters=[], available_work_reports=[], accumulation_statistics={})
    result = Statistics(context, AppContext()).state_transition(
        [], [], [], [], TimeslotState(0), TimeslotState(header.timeslot),
        ValidatorPoolState([validator() for _ in range(gp_const.VALIDATOR_COUNT)]), original, header,
    ).post_state

    assert original == before
    assert result.vals_current[0].blocks == (1 if epoch_change else 6)
    assert result.vals_last[0].blocks == (5 if epoch_change else 0)
    assert result.cores[0].gas_used == 0
    assert result.services == {}
    result.vals_last[0].blocks += 1
    result.cores[0].gas_used = 99
    assert original == before


def test_authorizer_pool_updates_preserve_the_input_lists():
    pools = AuthorizerPoolsState([[HASH] for _ in range(gp_const.CORE_COUNT)])
    queues = AuthorizerQueuesState([
        [OTHER_HASH] * gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for _ in range(gp_const.CORE_COUNT)
    ])
    before = deepcopy((pools, queues))
    result = AuthorizerPools(BlockContext(), AppContext()).state_transition(
        Header.default(), [], queues, pools,
    ).post_state

    assert result.authorizer_pools == [[HASH, OTHER_HASH] for _ in range(gp_const.CORE_COUNT)]
    result.authorizer_pools[0].clear()
    assert (pools, queues) == before


def test_accumulation_outputs_and_invocation_savepoints_are_independent():
    services = services_state()
    queues = AuthorizerQueuesState([
        [HASH] * gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS for _ in range(gp_const.CORE_COUNT)
    ])
    validators = ValidatorQueueState([validator()])
    privileges = PrivilegedServicesState(7, [7] * gp_const.CORE_COUNT, 7, 7, {})
    context = BlockContext(accumulatable_work_reports=[])
    component = Services(context, AppContext(state_storage=services.state_storage))
    output = asyncio.run(component.state_transition_accumulation(
        [], privileges, services, validators, queues, TimeslotState(1), EntropyState([HASH] * 4),
    ))
    output.post_state_validator_queue.validators[0].ed25519 = OTHER_HASH
    output.post_state_authorizer_queues.authorizer_queues[0][0] = OTHER_HASH
    assert validators.validators[0].ed25519 == HASH
    assert queues.authorizer_queues[0][0] == HASH

    state = AccumulationStateComponents(services, validators, queues, privileges)
    invocation = state.to_invocation_context(7, HASH, 1)
    current = invocation.context.state_context
    saved = invocation.savepoint_context.state_context
    current.services.pending_changes.service_accounts[7].preimage_availability[(HASH, 8)].append(3)
    current.validator_queue.validators[0].ed25519 = OTHER_HASH
    current.authorizer_queues.authorizer_queues[0][0] = OTHER_HASH
    current.privileged_services.assigners[0] = 8

    assert saved == state
    assert saved.services.pending_changes == state.services.pending_changes
    assert current.services.state_storage is saved.services.state_storage is services.state_storage
