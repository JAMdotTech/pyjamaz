"""Safrole verification preserves extrinsic order and drains shared-pool work."""

from concurrent.futures import Future, ThreadPoolExecutor, wait as wait_for_futures
from threading import Event
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


def envelope(score, attempt=0):
    return TicketEnvelope(attempt, score.to_bytes(32, "big") + bytes(752))


@pytest.fixture
def transition(monkeypatch):
    def verify(data, aux, proof):
        if proof[:32] == bytes([255]) * 32:
            raise ValueError("invalid ring proof")
        return proof[:32]

    monkeypatch.setattr(
        components, "jam_ring_context",
        lambda *_: SimpleNamespace(ring_vrf_verify=verify),
    )
    validators = [
        ValidatorData(bytes([index + 1]) * 32, bytes(32), bytes(144), bytes(128))
        for index in range(6)
    ]

    def run(tickets, prior=()):
        header = Header.default()
        header.timeslot = gp_const.EPOCH_TIMESLOTS + 1
        safrole = components.Safrole(BlockContext(), AppContext(), b"")
        return safrole.state_transition(
            header=header,
            extrinsic_tickets=tickets,
            pre_state_timeslot=TimeslotState(gp_const.EPOCH_TIMESLOTS),
            pre_state_safrole=SafroleState(
                validators=validators,
                ring_commitment=bytes(144),
                ticket_accumulator=list(prior),
                slot_sealer_series=SlotSealerSeries(keys=[bytes(32)] * gp_const.EPOCH_TIMESLOTS),
            ),
            pre_state_validator_queue=ValidatorQueueState(validators),
            post_state_entropy=EntropyState([bytes(32)] * 4),
            post_state_validator_pool=ValidatorPoolState(validators),
            post_state_disputes=DisputesState([], [], [], []),
        )

    return run


class RecordingFuture(Future):
    def __init__(self, index, events):
        super().__init__()
        self.index = index
        self.events = events

    def result(self, timeout=None):
        self.events.append(("result", self.index))
        return super().result(timeout)

    def cancel(self):
        self.events.append(("cancel", self.index))
        return super().cancel()


class ReverseCompletionExecutor:
    """Complete a whole submitted batch backwards, without scheduler timing."""

    def __init__(self, batch_size):
        self.batch_size = batch_size
        self.jobs = []
        self.events = []

    def submit(self, function, *args):
        future = RecordingFuture(len(self.jobs), self.events)
        self.jobs.append((future, function, args))
        if len(self.jobs) % self.batch_size == 0:
            for queued, callback, callback_args in reversed(self.jobs[-self.batch_size:]):
                try:
                    queued.set_result(callback(*callback_args))
                except BaseException as error:
                    queued.set_exception(error)
                self.events.append(("completed", queued.index))
        return future


@pytest.mark.parametrize("scores,rejected", [([1, 2], False), ([2, 1], True)])
def test_ticket_order_uses_extrinsic_order_despite_reverse_completion(
    monkeypatch, transition, scores, rejected,
):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    executor = ReverseCompletionExecutor(2)
    monkeypatch.setattr(components, "_get_safrole_ticket_executor", lambda: executor)

    if rejected:
        with pytest.raises(StateTransitionError) as error:
            transition([envelope(score) for score in scores])
        assert error.value.custom_error_code == SafroleErrorCode.bad_ticket_order
    else:
        output = transition([envelope(score) for score in scores])
        assert output.post_state.ticket_accumulator == [
            TicketBody(score.to_bytes(32, "big"), 0) for score in scores
        ]

    assert [event for event in executor.events if event[0] == "completed"] == [
        ("completed", 1), ("completed", 0),
    ]
    assert [event for event in executor.events if event[0] == "result"] == [
        ("result", 0), ("result", 1),
    ]


@pytest.mark.parametrize("threaded", [False, True])
@pytest.mark.parametrize("first,second,expected", [
    ("duplicate", "proof", SafroleErrorCode.duplicate_ticket),
    ("proof", "attempt", SafroleErrorCode.bad_ticket_proof),
    ("attempt", "duplicate", SafroleErrorCode.bad_ticket_attempt),
])
def test_multiple_ticket_errors_preserve_sequential_precedence(
    monkeypatch, transition, threaded, first, second, expected,
):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", threaded)
    executor = ReverseCompletionExecutor(2)
    monkeypatch.setattr(components, "_get_safrole_ticket_executor", lambda: executor)
    bad_proof_score = int.from_bytes(bytes([255]) * 32, "big")
    tickets = {
        "duplicate": envelope(1),
        "proof": envelope(bad_proof_score),
        "attempt": envelope(2, gp_const.ticket_entries(6)),
    }

    with pytest.raises(StateTransitionError) as error:
        transition(
            [tickets[first], tickets[second]],
            prior=[TicketBody((1).to_bytes(32, "big"), 0)],
        )

    assert error.value.custom_error_code == expected
    if threaded:
        assert [event for event in executor.events if event[0] == "result"] == [("result", 0)]
    else:
        assert executor.jobs == []


def test_failure_cancels_queued_work_and_waits_for_running_work(monkeypatch, transition):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    events = []
    futures = [RecordingFuture(index, events) for index in range(3)]
    original_error = StateTransitionError(SafroleErrorCode.bad_ticket_proof)
    futures[0].set_exception(original_error)
    assert futures[1].set_running_or_notify_cancel()
    submitted = iter(futures)
    monkeypatch.setattr(
        components, "_get_safrole_ticket_executor",
        lambda: SimpleNamespace(submit=lambda *_: next(submitted)),
    )

    def drain(submitted_futures):
        assert list(submitted_futures) == futures
        assert futures[1].running()
        assert futures[2].cancelled()
        events.append(("wait", None))
        futures[1].set_exception(ValueError("later worker error must not replace the first"))

    monkeypatch.setattr(components, "wait", drain)

    with pytest.raises(StateTransitionError) as error:
        transition([envelope(score) for score in (1, 2, 3)])

    assert error.value is original_error
    assert futures[1].done()
    assert futures[2].cancelled()
    assert [event for event in events if event[0] == "result"] == [("result", 0)]
    assert {event for event in events if event[0] == "cancel"} == {
        ("cancel", 0), ("cancel", 1), ("cancel", 2),
    }
    assert events[-1] == ("wait", None)


def test_real_workers_finish_before_verification_error_escapes(monkeypatch, transition):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    second_started, release_second, second_finished, wait_entered = (Event() for _ in range(4))
    original_error = StateTransitionError(SafroleErrorCode.bad_ticket_proof)

    def verify(data, aux, proof):
        if proof[:32] == (1).to_bytes(32, "big"):
            assert second_started.wait(10), "second proof never started"
            raise original_error
        second_started.set()
        try:
            assert release_second.wait(10), "second proof was never released"
            return proof[:32]
        finally:
            second_finished.set()

    def drain(futures):
        wait_entered.set()
        return wait_for_futures(futures)

    monkeypatch.setattr(
        components, "jam_ring_context", lambda *_: SimpleNamespace(ring_vrf_verify=verify),
    )
    monkeypatch.setattr(components, "wait", drain)
    with ThreadPoolExecutor(max_workers=2) as workers, ThreadPoolExecutor(max_workers=1) as caller:
        monkeypatch.setattr(components, "_get_safrole_ticket_executor", lambda: workers)
        result = caller.submit(transition, [envelope(1), envelope(2)])
        try:
            assert wait_entered.wait(10), "transition never began draining workers"
            assert not second_finished.is_set()
            assert not result.done()
        finally:
            release_second.set()

        with pytest.raises(StateTransitionError) as error:
            result.result(timeout=10)
        assert error.value is original_error
        assert second_finished.is_set()


def test_submission_failure_still_waits_for_already_running_work(monkeypatch, transition):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    events = []
    running = RecordingFuture(0, events)
    assert running.set_running_or_notify_cancel()
    submission_error = RuntimeError("executor could not accept another job")
    submissions = 0

    def submit(*_):
        nonlocal submissions
        submissions += 1
        if submissions == 1:
            return running
        raise submission_error

    monkeypatch.setattr(
        components, "_get_safrole_ticket_executor", lambda: SimpleNamespace(submit=submit),
    )

    def drain(futures):
        assert list(futures) == [running]
        assert running.running()
        events.append(("wait", None))
        running.set_result(TicketBody((1).to_bytes(32, "big"), 0))

    monkeypatch.setattr(components, "wait", drain)

    with pytest.raises(RuntimeError) as error:
        transition([envelope(1), envelope(2)])

    assert error.value is submission_error
    assert running.done()
    assert events == [("cancel", 0), ("wait", None)]


@pytest.mark.parametrize("threaded,count", [(False, 2), (True, 0), (True, 1)])
def test_sequential_setting_and_small_batches_do_not_acquire_pool(
    monkeypatch, transition, threaded, count,
):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", threaded)

    def unexpected_executor():
        pytest.fail("this transition should verify tickets without acquiring the executor")

    monkeypatch.setattr(components, "_get_safrole_ticket_executor", unexpected_executor)
    output = transition([envelope(score) for score in range(1, count + 1)])
    assert output.post_state.ticket_accumulator == [
        TicketBody(score.to_bytes(32, "big"), 0) for score in range(1, count + 1)
    ]


def test_executor_is_reused_between_safrole_instances(monkeypatch, transition):
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    monkeypatch.setattr(components, "_safrole_ticket_executor", None)
    monkeypatch.setattr(components, "SAFROLE_THREAD_POOL_MAX_WORKERS", 3)
    constructed = []

    def construct_executor(*args, **kwargs):
        executor = ReverseCompletionExecutor(2)
        constructed.append((args, kwargs, executor))
        return executor

    monkeypatch.setattr(components, "ThreadPoolExecutor", construct_executor)
    first = transition([envelope(1), envelope(2)])
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", False)
    sequential = transition([envelope(3), envelope(4)])
    assert len(constructed[0][2].jobs) == 2
    monkeypatch.setattr(components, "USE_THREAD_POOL_SAFROLE", True)
    second = transition([envelope(5), envelope(6)])

    assert [ticket.id for ticket in first.post_state.ticket_accumulator] == [
        score.to_bytes(32, "big") for score in (1, 2)
    ]
    assert [ticket.id for ticket in sequential.post_state.ticket_accumulator] == [
        score.to_bytes(32, "big") for score in (3, 4)
    ]
    assert [ticket.id for ticket in second.post_state.ticket_accumulator] == [
        score.to_bytes(32, "big") for score in (5, 6)
    ]
    assert len(constructed) == 1
    args, kwargs, executor = constructed[0]
    assert kwargs.get("max_workers", args[0] if args else None) == 3
    assert len(executor.jobs) == 4
