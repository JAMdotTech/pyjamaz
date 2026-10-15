"""GP-0.8.0 equation 12.17: report admission and gas across accumulation rounds."""

import asyncio
from types import SimpleNamespace

import pytest

from pyjamaz.models.common import DeferredTransfer
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import BeefyCommitmentMap, EntropyState, ParallelAccumulationOutput, TimeslotState
from pyjamaz.state.components import Services


def report(*gas_limits):
    return SimpleNamespace(results=[SimpleNamespace(accumulate_gas=g) for g in gas_limits])


def transfer(gas_limit, *, sender=1, receiver=2):
    return DeferredTransfer(sender, receiver, 1, bytes(128), gas_limit)


def accumulate(monkeypatch, reports, transfers, always, round_outputs):
    """Run real selection/recursion, stubbing only parallel execution results."""
    component = Services(BlockContext(), AppContext())
    original = component.full_sequential_accumulation
    calls, budgets = [], []

    async def observe(**kwargs):
        budgets.append(kwargs["gas_limit"])
        return await original(**kwargs)

    async def parallel(**kwargs):
        assert len(calls) < len(round_outputs), "Unexpected extra accumulation round"
        spent, outgoing = round_outputs[len(calls)]
        calls.append(kwargs)
        return ParallelAccumulationOutput(
            accumulation_state=kwargs["accumulation_state"],
            deferred_transfers=outgoing,
            accumulation_commitment=BeefyCommitmentMap(),
            accumulation_gas_utilized={42: spent},
        )

    monkeypatch.setattr(component, "full_sequential_accumulation", observe)
    monkeypatch.setattr(component, "parallel_accumulation", parallel)
    result = asyncio.run(component.full_sequential_accumulation(
        gas_limit=100,
        deferred_transfers=transfers,
        work_reports=reports,
        accumulation_state=object(),
        auto_accumulate_services=always,
        post_state_timeslot=TimeslotState(1),
        post_state_entropy=EntropyState([bytes(32)] * 4),
    ))
    assert len(calls) == len(round_outputs)
    return result, calls, budgets


@pytest.mark.parametrize(
    "transfer_limits, always, report_limits, selected, spent",
    [
        ([15, 15], {}, [(71,)], 0, 30),
        ([], {1: 20, 2: 10}, [(71,)], 0, 30),
        ([30], {1: 10}, [(30, 30)], 1, 100),
        ([30], {1: 10}, [(30, 31)], 0, 40),
        ([30], {}, [(71,), (10,)], 0, 30),
        ([30], {1: 70}, [(0,), (1,)], 1, 100),
    ],
    ids=["transfer-reserve", "always-reserve", "exact-fit", "one-over", "ordered-prefix", "zero-gas"],
)
def test_report_prefix_reserves_all_other_allowances(
    monkeypatch, transfer_limits, always, report_limits, selected, spent,
):
    reports = [report(*limits) for limits in report_limits]
    incoming = [transfer(limit) for limit in transfer_limits]
    result, calls, _ = accumulate(monkeypatch, reports, incoming, always, [(spent, [])])

    assert calls[0]["work_reports"] == reports[:selected]
    assert calls[0]["deferred_transfers"] == incoming
    assert calls[0]["auto_accumulate_services"] == always
    assert result.nr_work_results_accumulated == selected
    assert result.processed_transfers == incoming


def test_unused_always_allowance_is_available_to_later_reports(monkeypatch):
    reports = [report(70)]
    result, calls, budgets = accumulate(monkeypatch, reports, [], {42: 40}, [(10, []), (70, [])])

    assert [call["work_reports"] for call in calls] == [[], reports]
    assert [call["auto_accumulate_services"] for call in calls] == [{42: 40}, {}]
    assert budgets == [100, 90, 20]
    assert result.nr_work_results_accumulated == 1
    assert result.accumulation_gas_utilized == {42: 80}


def test_consumed_incoming_transfer_is_not_credited_again(monkeypatch):
    reports = [report(70), report(81)]
    incoming = [transfer(30)]
    result, calls, budgets = accumulate(monkeypatch, reports, incoming, {}, [(20, [])])

    assert calls[0]["work_reports"] == reports[:1]
    assert budgets == [100, 80]
    assert result.nr_work_results_accumulated == 1
    assert result.processed_transfers == incoming


def test_new_outgoing_transfer_is_credited_and_reserved_in_next_round(monkeypatch):
    reports = [report(80), report(50)]
    outgoing = [transfer(30)]
    result, calls, budgets = accumulate(monkeypatch, reports, [], {}, [(50, outgoing), (60, [])])

    assert [call["work_reports"] for call in calls] == [reports[:1], reports[1:]]
    assert [call["deferred_transfers"] for call in calls] == [[], outgoing]
    # 100 + 30 forwarded - 50 charged = 80; reserve 30, leaving exactly 50.
    assert budgets == [100, 80, 20]
    assert result.nr_work_results_accumulated == 2
    assert result.processed_transfers == outgoing
    assert result.accumulation_gas_utilized == {42: 110}
