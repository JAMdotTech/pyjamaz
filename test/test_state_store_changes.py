import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from pyjamaz.app import AppConfig, PyjamazApp
from pyjamaz.graypaper_constants import COMMON_ERA
from pyjamaz.models.state import BeefyCommitmentMap, JamState
from pyjamaz.state.base import StateComponent
from pyjamaz.storage import InMemoryStorageEngine


GENESIS, LEFT, RIGHT, CHILD = [bytes([n]) * 32 for n in range(1, 5)]


@pytest.fixture
def app():
    app = PyjamazApp(AppConfig(
        ring_data=b"", storage_engine=InMemoryStorageEngine(), common_era=COMMON_ERA,
    ))
    app.working_state = JamState.create_genesis_state()
    asyncio.run(app.store_jam_state())
    app.state_storage.set_finalized_block_hash(GENESIS)
    app.working_state = app.retrieve_jam_state()
    return app


def test_equal_components_skip_encoding_but_keep_service_store(app, monkeypatch):
    previous = app.working_state
    app.working_state = deepcopy(previous)
    encode = AsyncMock(side_effect=AssertionError("Unchanged component was encoded"))
    services = AsyncMock()
    monkeypatch.setattr(StateComponent, "store_state", encode)
    monkeypatch.setattr(app.components.services, "store_state", services)
    app.state_storage.set_block_hash(LEFT, GENESIS)
    # Service writes already in the transaction must survive the component store.
    app.state_storage.put(b"s" * 31, b"service data")

    asyncio.run(app.store_jam_state(previous))

    encode.assert_not_awaited()
    services.assert_awaited_once_with(app.working_state.services)
    assert app.state_storage.transaction == {b"s" * 31: b"service data"}


def test_nested_changes_match_a_full_store(app):
    previous = app.working_state
    app.working_state = deepcopy(previous)
    app.working_state.authorizer_queues.authorizer_queues[0][0] = b"q" * 32
    app.working_state.validator_pool.validators[0].ed25519 = b"v" * 32
    app.working_state.safrole.slot_sealer_series.keys[0] = b"k" * 32
    app.working_state.privileged_services.always_accumulators[42] = 123
    app.working_state.recent_accumulation_outputs = BeefyCommitmentMap({(42, b"o" * 32)})
    app.state_storage.set_block_hash(LEFT, GENESIS)
    asyncio.run(app.store_jam_state(previous))
    assert set(app.state_storage.transaction) == {
        component._state_key_constructor_component() for component in (
            app.components.authorizer_queues, app.components.validator_pool,
            app.components.safrole, app.components.privileged_services,
            app.components.recent_accumulation_output,
        )
    }
    app.state_storage.commit()
    sparse_state = app.state_storage.as_dict()
    sparse_root = app.state_storage.state_root()

    app.state_storage.set_block_hash(RIGHT, GENESIS)
    asyncio.run(app.store_jam_state())
    assert len(app.state_storage.transaction) == 16
    app.state_storage.commit()
    assert app.state_storage.as_dict() == sparse_state
    assert app.state_storage.state_root() == sparse_root


def test_comparison_follows_parent_selection_and_rejected_candidates(app):
    parent = app.working_state
    app.working_state = deepcopy(parent)
    app.working_state.authorizer_queues.authorizer_queues[0][0] = b"l" * 32
    app.state_storage.set_block_hash(LEFT, GENESIS)
    asyncio.run(app.store_jam_state(parent))
    app.state_storage.commit()
    left_root = app.state_storage.state_root()

    app.state_storage.select_block_hash(GENESIS)
    parent = app.retrieve_jam_state()
    app.working_state = deepcopy(parent)
    app.working_state.timeslot.number = 1
    app.state_storage.set_block_hash(RIGHT, GENESIS)
    asyncio.run(app.store_jam_state(parent))
    app.state_storage.commit()
    assert app.retrieve_jam_state().authorizer_queues == parent.authorizer_queues

    app.state_storage.select_block_hash(LEFT)
    parent = app.retrieve_jam_state()
    app.working_state = deepcopy(parent)
    app.working_state.timeslot.number = 2
    app.state_storage.set_block_hash(CHILD, LEFT)
    asyncio.run(app.store_jam_state(parent))
    # A rejected candidate must not leave any comparison cache behind.
    app.state_storage.discard_candidate(CHILD, LEFT)
    app.working_state = app.retrieve_jam_state()
    assert app.working_state.state_root == left_root

    parent = app.working_state
    app.working_state = deepcopy(parent)
    app.working_state.timeslot.number = 2
    app.state_storage.set_block_hash(CHILD, LEFT)
    asyncio.run(app.store_jam_state(parent))
    assert set(app.state_storage.transaction) == {
        app.components.timeslot._state_key_constructor_component()
    }
    app.state_storage.commit()
    assert app.retrieve_jam_state().timeslot.number == 2
    assert app.retrieve_jam_state().authorizer_queues == parent.authorizer_queues
