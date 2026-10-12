from collections import Counter
from types import SimpleNamespace

import pytest

from pyjamaz import graypaper_constants as gp_const
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.models.block import Header, TicketEnvelope
from pyjamaz.models.common import TicketBody, ValidatorData
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import (
    DisputesState, EntropyState, SafroleState, SlotSealerSeries, TimeslotState,
    ValidatorArchiveState, ValidatorPoolState, ValidatorQueueState,
)
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.state import components


def validators(count, prefix):
    return [
        ValidatorData(bytes(32), bytes([prefix]) + index.to_bytes(31, "little"), bytes(144), bytes(128))
        for index in range(count)
    ]


@pytest.mark.parametrize("cross_epoch", [False, True])
def test_guarantor_assignments_use_the_selected_validator_set(cross_epoch):
    current = ValidatorPoolState(validators(6, 1))
    previous = ValidatorArchiveState(validators(gp_const.VALIDATOR_COUNT, 2))
    slot = gp_const.EPOCH_TIMESLOTS + (
        gp_const.ROTATION_PERIOD_CORE - 1 if cross_epoch else 2 * gp_const.ROTATION_PERIOD_CORE
    )
    entropy = EntropyState([bytes([index]) * 32 for index in range(4)])
    context = BlockContext()

    context.set_guarantor_assignments(entropy, TimeslotState(slot), current)
    context.set_prev_guarantor_assignments(entropy, TimeslotState(slot), current, previous)

    assert [assignment.validator_ed25519 for assignment in context.guarantor_assignments] == [
        validator.ed25519 for validator in current.validators
    ]
    assert Counter(assignment.core_index for assignment in context.guarantor_assignments) == {0: 3, 1: 3}
    expected_previous = previous.validators if cross_epoch else current.validators
    assert [assignment.validator_ed25519 for assignment in context.prev_guarantor_assignments] == [
        validator.ed25519 for validator in expected_previous
    ]
    assert Counter(assignment.core_index for assignment in context.prev_guarantor_assignments) == {
        core: 3 for core in range(len(expected_previous) // 3)
    }


@pytest.mark.parametrize("threaded", [False, True])
@pytest.mark.parametrize("at_limit", [False, True])
def test_safrole_attempt_boundary_uses_pending_set_in_both_paths(monkeypatch, threaded, at_limit):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", threaded)
    # Six pending validators allow four Tiny attempts or 200 Full attempts.
    last_attempt, encoded_attempt = (3, b"\x03") if gp_const.EPOCH_TIMESLOTS == 12 else (199, b"\xc7")
    attempt = last_attempt + int(at_limit)
    entropy = EntropyState([bytes([index]) * 32 for index in range(4)])
    proof_inputs = []

    def verify(vrf_input, aux_data, signature):
        proof_inputs.append(vrf_input)
        assert aux_data == b""
        assert signature == bytes(784)
        return b"t" * 32

    monkeypatch.setattr(
        components, "jam_ring_context",
        lambda *_: SimpleNamespace(ring_vrf_verify=verify),
    )
    pending = validators(6, 1)
    pre_state = SafroleState(
        validators=pending,
        ring_commitment=bytes(144),
        slot_sealer_series=SlotSealerSeries(keys=[bytes(32)] * gp_const.EPOCH_TIMESLOTS),
        ticket_accumulator=[],
    )
    header = Header.default()
    header.timeslot = gp_const.EPOCH_TIMESLOTS + 1
    safrole = components.Safrole(BlockContext(), AppContext(), b"")

    def transition():
        return safrole.state_transition(
            header=header,
            extrinsic_tickets=[TicketEnvelope(attempt=attempt, signature=bytes(784))],
            pre_state_timeslot=TimeslotState(gp_const.EPOCH_TIMESLOTS),
            pre_state_safrole=pre_state,
            pre_state_validator_queue=ValidatorQueueState(pending),
            post_state_entropy=entropy,
            post_state_validator_pool=ValidatorPoolState(validators(gp_const.VALIDATOR_COUNT, 2)),
            post_state_disputes=DisputesState([], [], [], []),
        )

    if at_limit:
        with pytest.raises(StateTransitionError) as error:
            transition()
        assert error.value.custom_error_code == SafroleErrorCode.bad_ticket_attempt
        assert proof_inputs == []
    else:
        output = transition()
        assert output.post_state.ticket_accumulator == [TicketBody(id=b"t" * 32, attempt=attempt)]
        assert proof_inputs == [b"jam_ticket_seal" + entropy.entropy[2] + encoded_attempt]
