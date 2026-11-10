import asyncio
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pyjamaz import app as app_module, graypaper_constants as gp_const, signing
from pyjamaz.app import PyjamazApp
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import (
    EntropyState, SafroleState, SlotSealerSeries, TimeslotState,
    ValidatorPoolState, ValidatorQueueState,
)
from pyjamaz.runtime import extrinsics
from pyjamaz.runtime.extrinsics import BlockExtrinsicCollector
from pyjamaz.runtime.pipelines.accumulate import AccumulatePipeline
from pyjamaz.state.components import ValidatorPool


AUTHOR_KEY = b"\xff" * 32


def validator_set(count, prefix, author_index=None):
    keys = [bytes([prefix]) + index.to_bytes(31, "little") for index in range(count)]
    if author_index is not None:
        keys[author_index] = AUTHOR_KEY
    return [ValidatorData(key, key, bytes(144), bytes(128)) for key in keys]


def pending_state(validators):
    return SafroleState(
        validators=validators,
        ring_commitment=bytes(144),
        slot_sealer_series=SlotSealerSeries(keys=[bytes(32)] * gp_const.EPOCH_TIMESLOTS),
        ticket_accumulator=[],
    )


def bare_app():
    app = PyjamazApp.__new__(PyjamazApp)
    app.config = SimpleNamespace(
        keys=SimpleNamespace(bandersnatch=SimpleNamespace(public_key=AUTHOR_KEY, private_key=bytes(32))),
        ring_data=b"ring-data",
        create_traces=False,
    )
    app.block_extrinsic = BlockExtrinsicCollector(app.config.ring_data)
    app.working_state = SimpleNamespace(
        timeslot=TimeslotState(gp_const.EPOCH_TIMESLOTS + 1),
        validator_pool=ValidatorPoolState(validator_set(min(9, gp_const.VALIDATOR_COUNT), 1, 1)),
        safrole=pending_state(validator_set(6, 2, 3)),
        validator_queue=ValidatorQueueState(validator_set(min(12, gp_const.VALIDATOR_COUNT), 3, 5)),
        entropy=EntropyState([bytes([index]) * 32 for index in range(4)]),
        services=SimpleNamespace(),
        disputes=SimpleNamespace(),
        state_root=b"s" * 32,
    )
    app.generate_entropy_source = Mock(return_value=bytes(96))
    app.state_transition = AsyncMock()
    app.add_ancestor_block = AsyncMock()
    return app


@pytest.mark.parametrize("epoch_gap", [0, 1, 3], ids=["same-epoch", "next-epoch", "skipped-epochs"])
@pytest.mark.parametrize("pending_member", [True, False], ids=["pending-member", "leaving-validator"])
def test_block_author_and_ticket_signer_use_their_own_validator_sets(monkeypatch, epoch_gap, pending_member):
    app = bare_app()
    timeslot = (1 + epoch_gap) * gp_const.EPOCH_TIMESLOTS + 2
    if epoch_gap:
        pending = pending_state(validator_set(
            min(12, gp_const.VALIDATOR_COUNT), 3, 5 if pending_member else None,
        ))
        expected_header_index, expected_ticket_index = 3, 5
    else:
        app.working_state.safrole = pending_state(validator_set(6, 2, 3 if pending_member else None))
        pending = app.working_state.safrole
        expected_header_index, expected_ticket_index = 1, 3

    sign = Mock(return_value=bytes(784))
    ring = Mock(return_value=SimpleNamespace(ring_vrf_sign=sign))
    monkeypatch.setattr(app_module, "SOLO_MODE", False)
    monkeypatch.setattr(signing, "jam_ring_context", ring)
    monkeypatch.setattr(extrinsics, "vrf_output", lambda key, message: sha256(message).digest())

    block = asyncio.run(app.produce_block(timeslot, b"p" * 32, pending, app.working_state.entropy))

    assert block.header.author_index == expected_header_index
    app.state_transition.assert_awaited_once_with(block, produce=True)
    app.add_ancestor_block.assert_awaited_once_with(block)
    if pending_member:
        ring.assert_called_once_with(app.config.ring_data, [v.bandersnatch for v in pending.validators])
        assert sign.call_count == gp_const.ticket_entries(len(pending.validators))
        assert all(call.args[0] == expected_ticket_index for call in sign.call_args_list)
        assert app.block_extrinsic.own_ticket_count() == sign.call_count
        assert len(block.extrinsic.tickets) == min(sign.call_count, gp_const.MAXIMUM_EXTRINSIC_TICKETS)
    else:
        ring.assert_not_called()
        sign.assert_not_called()
        assert block.extrinsic.tickets == []


@pytest.mark.parametrize("epoch_gap", [1, 3], ids=["next-epoch", "skipped-epochs"])
def test_epoch_preview_uses_rotated_validator_pool_for_safrole(epoch_gap):
    async def run():
        app = bare_app()
        old_pool = app.working_state.validator_pool
        parent_pending = app.working_state.safrole
        new_pending = pending_state(app.working_state.validator_queue.validators)
        safrole_transition = Mock(return_value=SimpleNamespace(post_state=new_pending))
        pool_transition = Mock(wraps=ValidatorPool(BlockContext(), AppContext()).state_transition)
        app.components = SimpleNamespace(
            entropy=SimpleNamespace(state_transition=Mock(return_value=SimpleNamespace(
                post_state=app.working_state.entropy,
            ))),
            validator_pool=SimpleNamespace(state_transition=pool_transition),
            safrole=SimpleNamespace(state_transition=safrole_transition),
        )
        app.should_produce_block = Mock(return_value=False)
        pipeline = AccumulatePipeline(app)
        timeslot = (1 + epoch_gap) * gp_const.EPOCH_TIMESLOTS + 2
        await pipeline.notify_timeslot(timeslot)
        worker = asyncio.create_task(pipeline._timeslot_worker())
        try:
            await asyncio.wait_for(pipeline._timeslot_queue.join(), timeout=2)
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

        pool_transition.assert_called_once()
        safrole_transition.assert_called_once()
        selected_pool = safrole_transition.call_args.kwargs["post_state_validator_pool"]
        assert selected_pool.validators == parent_pending.validators
        assert selected_pool.validators != old_pool.validators
        assert app.working_state.validator_pool is old_pool
        app.should_produce_block.assert_called_once_with(timeslot, new_pending)

    asyncio.run(run())
