from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyjamaz import graypaper_constants as gp_const
from pyjamaz.models.block import TicketEnvelope
from pyjamaz.models.common import TicketBody
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.runtime import extrinsics


def ticket_id(value):
    return value.to_bytes(32, "big")


def ticket(value=0, *, attempt=0):
    return TicketEnvelope(attempt=attempt, signature=value.to_bytes(784, "big"))


@pytest.fixture
def collector():
    return extrinsics.BlockExtrinsicCollector(b"ring-data")


@pytest.fixture(params=[6, 9], ids=["six-validators", "nine-validators"])
def attempt_bound(request):
    if request.param == 9:
        if gp_const.VALIDATOR_COUNT < 9:
            pytest.skip("Nine validators exceed the Tiny validator maximum")
        return 9, 134
    # Known GP configurations: E=12 in Tiny and E=600 in Full.
    return 6, 4 if gp_const.EPOCH_TIMESLOTS == 12 else 200


def test_received_ticket_accepts_last_attempt_for_pending_set(collector, attempt_bound):
    validator_count, limit = attempt_bound
    ring = SimpleNamespace(ring_vrf_verify=Mock(return_value=ticket_id(1)))
    entropy = b"e" * 32
    envelope = ticket(attempt=limit - 1)

    body = collector.create_ticket_body(
        envelope, ring, entropy, validator_count=validator_count,
    )

    assert body == TicketBody(id=ticket_id(1), attempt=limit - 1)
    ring.ring_vrf_verify.assert_called_once_with(
        b"jam_ticket_seal" + entropy + bytes([limit - 1]), b"", bytes(784),
    )


@pytest.mark.parametrize("negative", [False, True], ids=["upper-bound", "negative"])
def test_received_invalid_attempt_is_rejected_before_verification(collector, attempt_bound, negative):
    validator_count, limit = attempt_bound
    ring = SimpleNamespace(ring_vrf_verify=Mock())

    with pytest.raises(ValueError) as error:
        collector.create_ticket_body(
            ticket(attempt=-1 if negative else limit), ring, bytes(32),
            validator_count=validator_count,
        )

    assert error.value.args == (SafroleErrorCode.bad_ticket_attempt,)
    ring.ring_vrf_verify.assert_not_called()
    assert collector.tickets_queue == {}


def test_received_ticket_uses_jam_ring_wrapper_and_unpadded_validator_count(
    monkeypatch, collector, attempt_bound,
):
    validator_count, limit = attempt_bound
    public_keys = [ticket_id(index) for index in range(validator_count)]
    ring = SimpleNamespace(ring_vrf_verify=Mock(return_value=ticket_id(123)))
    make_ring = Mock(return_value=ring)
    monkeypatch.setattr(extrinsics, "jam_ring_context", make_ring)
    envelope = ticket(attempt=limit - 1)

    collector.add_ticket(envelope, public_keys, b"e" * 32)

    make_ring.assert_called_once_with(b"ring-data", public_keys)
    ring.ring_vrf_verify.assert_called_once()
    assert collector.tickets_queue == {ticket_id(123): envelope}


def test_own_attempt_limit_ignores_peer_queue_and_rejects_equality(
    monkeypatch, collector, attempt_bound,
):
    validator_count, limit = attempt_bound
    collector.own_tickets_next = [ticket_id(index) for index in range(limit - 1)]
    # Peers can fill the shared queue without consuming this validator's attempts.
    collector.tickets_queue = {
        ticket_id(1000 + index): ticket(index) for index in range(limit + 1)
    }
    ring = SimpleNamespace(ring_vrf_sign=Mock(return_value=bytes(784)))
    keypair = SimpleNamespace(private_key=b"private-key")
    entropy = b"e" * 32
    derive_id = Mock(return_value=ticket_id(999))
    monkeypatch.setattr(extrinsics, "vrf_output", derive_id)

    assert collector.can_add_own_ticket(0, validator_count=validator_count)
    collector.add_own_ticket(ring, entropy, keypair, 0, validator_count=validator_count)

    assert collector.own_tickets_next[-1] == ticket_id(999)
    assert collector.own_ticket_count() == limit
    assert collector.tickets_queue[ticket_id(999)].attempt == limit - 1
    assert len(collector.tickets_queue) == limit + 2
    ring.ring_vrf_sign.assert_called_once_with(
        0, keypair.private_key, b"jam_ticket_seal" + entropy + bytes([limit - 1]), b"",
    )
    assert not collector.can_add_own_ticket(0, validator_count=validator_count)

    # The attempt limit must also hold after every queued envelope was collected.
    collector.tickets_queue.clear()
    with pytest.raises(ValueError):
        collector.add_own_ticket(ring, entropy, keypair, 0, validator_count=validator_count)
    assert collector.own_ticket_count() == limit
    assert collector.tickets_queue == {}
    assert ring.ring_vrf_sign.call_count == 1
    assert derive_id.call_count == 1


def test_own_ticket_generation_stops_at_epoch_submission_cutoff(collector):
    epoch_start = 3 * gp_const.EPOCH_TIMESLOTS
    cutoff = epoch_start + gp_const.TICKET_SUBMISSION_END_SLOT

    assert collector.can_add_own_ticket(cutoff - 1, validator_count=6)
    assert not collector.can_add_own_ticket(cutoff, validator_count=6)
    assert not collector.can_add_own_ticket(epoch_start + gp_const.EPOCH_TIMESLOTS - 1, validator_count=6)
    assert collector.can_add_own_ticket(epoch_start + gp_const.EPOCH_TIMESLOTS, validator_count=6)


def test_collection_excludes_duplicates_and_non_winners_and_limits_extrinsic(collector):
    accumulator = [
        TicketBody(id=ticket_id(1000 + index), attempt=0)
        for index in range(gp_const.EPOCH_TIMESLOTS)
    ]
    candidates = {
        ticket_id(index): ticket(index)
        for index in range(gp_const.MAXIMUM_EXTRINSIC_TICKETS + 1, 0, -1)
    }
    collector.tickets_queue = {
        ticket_id(1000): ticket(1000),  # Already present in the accumulator.
        ticket_id(10000): ticket(10000),  # Cannot survive the lowest-E selection.
        **candidates,
    }

    collected = collector.collect_tickets(accumulator)

    assert collected == [
        candidates[ticket_id(index)] for index in range(1, gp_const.MAXIMUM_EXTRINSIC_TICKETS + 1)
    ]
    remaining_id = ticket_id(gp_const.MAXIMUM_EXTRINSIC_TICKETS + 1)
    assert collector.tickets_queue == {remaining_id: candidates[remaining_id]}
    assert accumulator == [
        TicketBody(id=ticket_id(1000 + index), attempt=0)
        for index in range(gp_const.EPOCH_TIMESLOTS)
    ]


def test_collection_at_cutoff_emits_nothing_and_preserves_queue(collector):
    envelope = ticket(1)
    collector.tickets_queue = {ticket_id(1): envelope}

    assert collector.collect_tickets(submission_allowed=False) == []
    assert collector.tickets_queue == {ticket_id(1): envelope}
    assert collector.collect_tickets() == [envelope]
    assert collector.tickets_queue == {}
