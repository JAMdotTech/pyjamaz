from dataclasses import dataclass
from typing import List, Set, Optional, Dict
from pyjamaz.models.common import WorkReport, AccumulationOperand
from pyjamaz.models.state import AccumulationQueueWorkPackage, AccumulationStateComponents, DeferredTransfer, \
    BeefyCommitmentMap, TimeslotState


def work_report_dependencies(work_report: WorkReport) -> AccumulationQueueWorkPackage:
    """
    GP-0.5.4-eq:12.6 (D) | Create a dependency graph of work report dependencies

    Parameters
    ----------
    work_report

    Returns
    -------
    AccumulationQueueWorkPackage
    """
    return AccumulationQueueWorkPackage(
        report=work_report,
        dependencies=set(work_report.context.prerequisites + list(work_report.segment_root_lookup.keys()))
    )


def edit_queue(
        work_report_queue: List[AccumulationQueueWorkPackage],
        accumulated_packages: List[bytes]
) -> List[AccumulationQueueWorkPackage]:
    """
    GP-0.5.4-eq:12.7 (E) | Queue editing function

    Parameters
    ----------
    work_report_queue
    accumulated_packages

    Returns
    -------
    List[AccumulationQueueWorkPackage]

    """
    modified_queue = []
    for queue_item in work_report_queue:
        modified_dependencies = set(queue_item.dependencies).difference(accumulated_packages)

        if queue_item.report.package_spec.hash not in accumulated_packages:
            modified_queue.append(
                AccumulationQueueWorkPackage(report=queue_item.report, dependencies=modified_dependencies)
            )

    return modified_queue


def work_report_mapping(work_reports: List[WorkReport]) -> Set[bytes]:
    """
    GP-0.5.4-eq:12.9 (P) | Extracts hashes from given work reports

    Parameters
    ----------
    work_reports

    Returns
    -------
    List[bytes]
    """
    return {w.package_spec.hash for w in work_reports}


def priority_queue(work_report_queue: List[AccumulationQueueWorkPackage]) -> List[WorkReport]:
    """
    GP-0.5.4-eq:12.8 (Q) | Accumulate priority queue function

    Parameters
    ----------
    work_report_queue

    Returns
    -------
    List[WorkReport]
    """
    if len(work_report_queue) == 0:
        return []

    g = [acc_work_package.report for acc_work_package in work_report_queue]

    return g + priority_queue(edit_queue(work_report_queue, work_report_mapping(g)))


@dataclass
class PvmAccumulateOutput:
    state_context: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_output: Optional[bytes]
    gas_used: int


@dataclass
class ParallelAccumulationOutput:
    total_gas_utilized: int
    accumulation_state: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_commitment: BeefyCommitmentMap

@dataclass
class FullAccumulationOutput:
    nr_work_results_accumulated: int
    post_accumulation_state: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_commitment: BeefyCommitmentMap


def pvm_invoke_accumulate(
        state_context: AccumulationStateComponents,
        timeslot: int,
        service_id: int,
        gas_limit: int,
        operands: List[AccumulationOperand]
) -> PvmAccumulateOutput:
    """
    GP-0.5.4-eq:B.8 (Ψ_A) | Accumulate output function

    TODO stub

    Parameters
    ----------
    state_context
    timeslot
    service_id
    gas_limit
    operands

    Returns
    -------
    PvmAccumulateOutput
    """

    return PvmAccumulateOutput(
        state_context=state_context,
        deferred_transfers=[],
        accumulation_output=None,
        gas_used=gas_limit
    )

def full_sequential_accumulation(
        gas_limit: int,
        work_reports: List[WorkReport],
        accumulation_state: AccumulationStateComponents,
        auto_accumulate_services: Dict[int, int],
        post_state_timeslot: TimeslotState
) -> FullAccumulationOutput:
    """
    GP-0.5.4-eq:12.16 ∆+ | full sequential accumulation function


    TODO how to deal with post_state_timeslot ?

    Returns
    -------
    FullAccumulationOutput
    """

    gas_used = 0
    i = 0

    for i, work_report in enumerate(work_reports, start=1):
        gas_used += sum([r.accumulate_gas for r in work_report.results])
        if gas_used > gas_limit:
            break

    if i == 0:
        return FullAccumulationOutput(
            nr_work_results_accumulated=0,
            post_accumulation_state=accumulation_state,
            deferred_transfers=[],
            accumulation_commitment=BeefyCommitmentMap(beefy_commitment_map={}),
        )

    output = parallel_accumulation(
        accumulation_state=accumulation_state,
        work_reports=work_reports[:i],
        auto_accumulate_services=auto_accumulate_services,
        post_state_timeslot=post_state_timeslot,
    )

    second_output = full_sequential_accumulation(
        gas_limit=gas_limit - output.total_gas_utilized,
        work_reports=work_reports[i:],
        accumulation_state=output.accumulation_state,
        auto_accumulate_services={},
        post_state_timeslot=post_state_timeslot
    )

    output.accumulation_commitment.beefy_commitment_map.update(
        second_output.accumulation_commitment.beefy_commitment_map
    )

    return FullAccumulationOutput(
        nr_work_results_accumulated=i + second_output.nr_work_results_accumulated,
        post_accumulation_state=accumulation_state,
        deferred_transfers=output.deferred_transfers + second_output.deferred_transfers,
        accumulation_commitment=output.accumulation_commitment,
    )


def parallel_accumulation(
        accumulation_state: AccumulationStateComponents,
        work_reports: List[WorkReport],
        auto_accumulate_services: Dict[int, int],
        post_state_timeslot: TimeslotState
) -> ParallelAccumulationOutput:
    """
    GP-0.5.4-eq:12.17 ∆* | parallel accumulation function

    Returns
    -------
    ParallelAccumulationOutput
    """
    # s
    service_ids = set([r.service_id for w in work_reports for r in w.results] + list(auto_accumulate_services.keys()))
    # u
    total_gas_utilized = 0
    # b
    beefy_commitment_map = {}
    # t
    deferred_transfers = []

    # TODO parallelize
    # async def process_service_accumulation():
    #
    # tasks = [
    #     single_step_accumulation("A", service_id),
    #     single_step_accumulation("B", 'c'),
    #     single_step_accumulation("C", 'x'),
    # ]
    #
    # for task in asyncio.as_completed(tasks):
    #     result = await task
    #     print("Processed:", result)

    # Process services
    for service_id in service_ids:
        output = single_step_accumulation(
            accumulation_state=accumulation_state,
            post_state_timeslot=post_state_timeslot,
            work_reports=work_reports,
            auto_accumulate_services=auto_accumulate_services,
            service_id=service_id
        )
        total_gas_utilized += output.gas_used

        deferred_transfers += output.deferred_transfers

        # TODO naive implementation
        accumulation_state.services.services[service_id] = output.state_context.services.services[service_id]

        if output.accumulation_output is not None:
            beefy_commitment_map.update({service_id: output.accumulation_output})

    # Process privilege services (x')
    output = single_step_accumulation(
        accumulation_state=accumulation_state,
        post_state_timeslot=post_state_timeslot,
        work_reports=work_reports,
        auto_accumulate_services=auto_accumulate_services,
        service_id=accumulation_state.privileged_services.empower_service
    )
    accumulation_state.privileged_services = output.state_context.privileged_services

    # Process validator queue (i')
    output = single_step_accumulation(
        accumulation_state=accumulation_state,
        post_state_timeslot=post_state_timeslot,
        work_reports=work_reports,
        auto_accumulate_services=auto_accumulate_services,
        service_id=accumulation_state.privileged_services.empower_service
    )
    accumulation_state.validator_queue = output.state_context.validator_queue

    # Process authorizer queue (q')
    output = single_step_accumulation(
        accumulation_state=accumulation_state,
        post_state_timeslot=post_state_timeslot,
        work_reports=work_reports,
        auto_accumulate_services=auto_accumulate_services,
        service_id=accumulation_state.privileged_services.empower_service
    )
    accumulation_state.authorizer_queues = output.state_context.authorizer_queues

    return ParallelAccumulationOutput(
        total_gas_utilized=total_gas_utilized,
        accumulation_state=accumulation_state,
        deferred_transfers=deferred_transfers,
        accumulation_commitment=BeefyCommitmentMap(beefy_commitment_map=beefy_commitment_map),
    )


def single_step_accumulation(
        accumulation_state: AccumulationStateComponents,
        post_state_timeslot: TimeslotState,
        work_reports: List[WorkReport],
        auto_accumulate_services: Dict[int, int],
        service_id: int
) -> PvmAccumulateOutput:
    """
    GP-0.5.4-eq:12.19 ∆1 | single step accumulation function

    Returns
    -------
    PvmAccumulateOutput
    """
    # GP-0.5.4-eq:I.3 (function_U)
    g = auto_accumulate_services.get(service_id, 0)
    p = []
    for w in work_reports:
        for r in w.results:
            if r.service_id == service_id:
                g += r.accumulate_gas
                p.append(
                    AccumulationOperand(
                        work_item_result=r.result,
                        work_item_payload_hash=r.payload_hash,
                        work_report_hash=w.package_spec.hash,
                        work_report_auth_output=w.auth_output,
                    )
                )

    return pvm_invoke_accumulate(
        state_context=accumulation_state,
        timeslot=post_state_timeslot.number,
        service_id=service_id,
        gas_limit=g,
        operands=p
    )
