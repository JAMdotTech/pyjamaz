"""GP-0.8.0-eq:6.36: submitted tickets must survive accumulator truncation."""

from types import SimpleNamespace

import pytest

from pyjamaz import graypaper_constants as gp_const
from pyjamaz.exceptions import StateTransitionError
from pyjamaz.models.block import Header, TicketEnvelope
from pyjamaz.models.common import TicketBody, ValidatorData
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import (
    DisputesState, EntropyState, SafroleState, SlotSealerSeries, TimeslotState,
    ValidatorPoolState, ValidatorQueueState,
)
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.state import components


E = gp_const.EPOCH_TIMESLOTS


@pytest.mark.parametrize('threaded', [False, True])
@pytest.mark.parametrize('prior_count,scores,epoch_change,rejected', [
    (E, [1, 2], False, False),
    (E, [1, E * 10 + 1], False, True),
    (E - 2, [E * 10 + 1, E * 10 + 2], False, False),
    (E - 1, [E * 10 + 1], False, False),
    (E - 1, [E * 10 + 1, E * 10 + 2], False, True),
    (E, [], False, False),
    (E, [E * 10 + 1, E * 10 + 2], True, False),
])
def test_submitted_tickets_must_be_retained(
    monkeypatch, threaded, prior_count, scores, epoch_change, rejected,
):
    monkeypatch.setattr(components, 'USE_THREAD_POOL_SAFROLE', threaded)
    ring = SimpleNamespace(
        commitment=bytes(144), ring_vrf_verify=lambda data, aux, proof: proof[:32],
    )
    monkeypatch.setattr(components, 'jam_ring_context', lambda *args: ring)
    validators = [ValidatorData(bytes([i + 1]) * 32, bytes(32), bytes(144), bytes(128)) for i in range(6)]
    prior = [TicketBody(((i + 1) * 10).to_bytes(32, 'big'), 0) for i in range(prior_count)]
    submitted = [TicketBody(score.to_bytes(32, 'big'), 0) for score in scores]
    pre_state = SafroleState(
        validators=validators, ring_commitment=bytes(144), ticket_accumulator=prior,
        slot_sealer_series=SlotSealerSeries(keys=[bytes(32)] * E),
    )
    header = Header.default()
    header.timeslot = E if epoch_change else E + 1
    safrole = components.Safrole(BlockContext(), AppContext(), b'')

    def transition():
        return safrole.state_transition(
            header=header,
            extrinsic_tickets=[TicketEnvelope(0, ticket.id + bytes(752)) for ticket in submitted],
            pre_state_timeslot=TimeslotState(E - 1 if epoch_change else E),
            pre_state_safrole=pre_state,
            pre_state_validator_queue=ValidatorQueueState(validators),
            post_state_entropy=EntropyState([bytes(32)] * 4),
            post_state_validator_pool=ValidatorPoolState(validators),
            post_state_disputes=DisputesState([], [], [], []),
        )

    if rejected:
        with pytest.raises(StateTransitionError) as error:
            transition()
        assert error.value.custom_error_code == SafroleErrorCode.ticket_not_retained
    else:
        output = transition()
        assert all(ticket in output.post_state.ticket_accumulator for ticket in submitted)
        if epoch_change:
            assert output.post_state.ticket_accumulator == submitted

