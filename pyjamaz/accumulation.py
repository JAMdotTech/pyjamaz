import logging
import typing
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Set, Dict

from pyjamaz.graypaper_constants import CORE_COUNT

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import WorkReport, AccumulationOperand
from pyjamaz.models.state import AccumulationQueueWorkPackage, AccumulationStateComponents, DeferredTransfer, \
    BeefyCommitmentMap, TimeslotState, EntropyState

from pyjamaz.hostcalls.invocation import pvm_invoke_accumulate
from pyjamaz.settings import USE_THREAD_POOL, THREAD_POOL_MAX_WORKERS
from pyjamaz.utils import substitute_if_nothing, sum_dict_values

if typing.TYPE_CHECKING:
    from pyjamaz.hostcalls.models import PvmAccumulateOutput

def work_report_dependencies(work_report: WorkReport) -> AccumulationQueueWorkPackage:
    """
    GP-0.6.1-eq:12.6 (D) | Create a dependency graph of work report dependencies

    Parameters
    ----------
    work_report: WorkReport

    Returns
    -------
    AccumulationQueueWorkPackage
    """
    return AccumulationQueueWorkPackage(
        report=work_report,
        dependencies=sorted(work_report.context.prerequisites + list(work_report.segment_root_lookup.keys()))
    )


def edit_queue(
        work_report_queue: List[AccumulationQueueWorkPackage],
        accumulated_packages: List[bytes]
) -> List[AccumulationQueueWorkPackage]:
    """
    GP-0.6.1-eq:12.7 (E) | Queue editing function

    Parameters
    ----------
    work_report_queue: List[AccumulationQueueWorkPackage]
    accumulated_packages: List[bytes]

    Returns
    -------
    List[AccumulationQueueWorkPackage]

    """
    modified_queue = []
    for queue_item in work_report_queue:

        if queue_item.report.package_spec.hash not in accumulated_packages:
            modified_dependencies = set(queue_item.dependencies).difference(accumulated_packages)
            modified_queue.append(
                AccumulationQueueWorkPackage(report=queue_item.report, dependencies=sorted(modified_dependencies - set(accumulated_packages)))
            )

    return modified_queue


def work_report_mapping(work_reports: List[WorkReport]) -> Set[bytes]:
    """
    GP-0.6.1-eq:12.9 (P) | Extracts hashes from given work reports

    Parameters
    ----------
    work_reports: List[WorkReport]

    Returns
    -------
    List[bytes]
    """
    return {w.package_spec.hash for w in work_reports}


def priority_queue(work_report_queue: List[AccumulationQueueWorkPackage]) -> List[WorkReport]:
    """
    GP-0.6.1-eq:12.8 (Q) | Accumulate priority queue function

    Parameters
    ----------
    work_report_queue: List[AccumulationQueueWorkPackage]

    Returns
    -------
    List[WorkReport]
    """

    g = [acc_work_package.report for acc_work_package in work_report_queue if len(acc_work_package.dependencies) == 0]

    if len(g) == 0:
        return []
    else:
        return g + priority_queue(edit_queue(work_report_queue, work_report_mapping(g)))


def transfers_service_mapping(
        deferred_transfers: List[DeferredTransfer],
        service_id: int
) -> List[DeferredTransfer]:
    """
    GP-0.6.5-eq:12.27 (R) | Maps a sequence of deferred transfers to a service

    Parameters
    ----------
    deferred_transfers: List[DeferredTransfer]
    service_id: int

    Returns
    -------
    List[DeferredTransfer]
    """
    transfers = [t for t in deferred_transfers if t.receiver == service_id]
    return sorted(transfers, key=lambda t: t.sender)


@dataclass
class ParallelAccumulationOutput:
    accumulation_state: AccumulationStateComponents
    deferred_transfers: List[DeferredTransfer]
    accumulation_commitment: BeefyCommitmentMap
    accumulation_gas_utilized: Dict[int, int]


@dataclass
class FullAccumulationOutput:
    """
    GP-0.7.0-eq:12.24
    """
    # n
    nr_work_results_accumulated: int
    # e'
    post_accumulation_state: AccumulationStateComponents
    # bold_t
    deferred_transfers: List[DeferredTransfer]
    # θ
    accumulation_commitment: BeefyCommitmentMap
    # bold_u
    accumulation_gas_utilized: Dict[int, int]


def full_sequential_accumulation(
        gas_limit: int,
        work_reports: List[WorkReport],
        accumulation_state: AccumulationStateComponents,
        auto_accumulate_services: Dict[int, int],
        post_state_timeslot: TimeslotState,
        post_state_entropy: EntropyState
) -> FullAccumulationOutput:
    """
    GP-0.7.0-eq:12.16 ∆+ | full sequential accumulation function

    Parameters
    ----------
    gas_limit: int
    work_reports: List[WorkReport]
    accumulation_state: AccumulationStateComponents
    auto_accumulate_services: Dict[int, int]
    post_state_timeslot: TimeslotState

    TODO how to deal with post_state_timeslot and post_state_entropy, not according to GP?

    Returns
    -------
    FullAccumulationOutput
    """

    gas_used = 0
    i = 0

    for i, work_report in enumerate(work_reports, start=1):
        gas_used += sum([r.accumulate_gas for r in work_report.results])
        if gas_used > gas_limit:
            i -= 1
            break

    if i == 0:
        return FullAccumulationOutput(
            nr_work_results_accumulated=0,
            post_accumulation_state=accumulation_state,
            deferred_transfers=[],
            accumulation_commitment=BeefyCommitmentMap(beefy_commitment_map={}),
            accumulation_gas_utilized={}
        )

    output = parallel_accumulation(
        accumulation_state=accumulation_state,
        work_reports=work_reports[:i],
        auto_accumulate_services=auto_accumulate_services,
        post_state_timeslot=post_state_timeslot,
        post_state_entropy=post_state_entropy
    )

    second_output = full_sequential_accumulation(
        gas_limit=gas_limit - sum([u for u in output.accumulation_gas_utilized.values()]),
        work_reports=work_reports[i:],
        accumulation_state=output.accumulation_state,
        auto_accumulate_services={},
        post_state_timeslot=post_state_timeslot,
        post_state_entropy=post_state_entropy
    )

    output.accumulation_commitment.beefy_commitment_map.update(
        second_output.accumulation_commitment.beefy_commitment_map
    )

    # Update gas statistics
    output.accumulation_gas_utilized = sum_dict_values(
        output.accumulation_gas_utilized, second_output.accumulation_gas_utilized
    )

    return FullAccumulationOutput(
        nr_work_results_accumulated=i + second_output.nr_work_results_accumulated,
        post_accumulation_state=accumulation_state,
        deferred_transfers=output.deferred_transfers + second_output.deferred_transfers,
        accumulation_commitment=output.accumulation_commitment,
        accumulation_gas_utilized=output.accumulation_gas_utilized,
    )


def parallel_accumulation(
        accumulation_state: AccumulationStateComponents,
        work_reports: List[WorkReport],
        auto_accumulate_services: Dict[int, int],
        post_state_timeslot: TimeslotState,
        post_state_entropy: EntropyState
) -> ParallelAccumulationOutput:
    """
    GP-0.6.5-eq:12.17 ∆* | parallel accumulation function

    Parameters
    ----------
    accumulation_state: AccumulationStateComponents
    work_reports: List[WorkReport]
    auto_accumulate_services: Dict[int, int]
    post_state_timeslot: TimeslotState

    Returns
    -------
    ParallelAccumulationOutput
    """
    # s
    service_ids = list(
        dict.fromkeys([r.service_id for w in work_reports for r in w.results] + list(auto_accumulate_services.keys()))
    )

    # u
    accumulation_gas_utilized = {}
    # b
    beefy_commitment_map = {}
    # t
    deferred_transfers = []

    logging.debug(f'Services to accumulate: {service_ids}')

    outputs = []

    if USE_THREAD_POOL:

        logging.debug(f'Using ThreadPool max_workers={THREAD_POOL_MAX_WORKERS}')

        with ThreadPoolExecutor(max_workers=THREAD_POOL_MAX_WORKERS) as tp:
            futs = {
                tp.submit(
                    single_step_accumulation,
                    accumulation_state=accumulation_state,
                    post_state_timeslot=post_state_timeslot,
                    post_state_entropy=post_state_entropy,
                    work_reports=work_reports,
                    auto_accumulate_services=auto_accumulate_services,
                    service_id=service_id,
                ): service_id
                for service_id in service_ids
            }

            for fut in as_completed(futs):
                output = fut.result()
                service_id = futs[fut]
                outputs.append((service_id, output))
    else:
        # Process services
        for service_id in service_ids:

            output = single_step_accumulation(
                accumulation_state=accumulation_state,
                post_state_timeslot=post_state_timeslot,
                post_state_entropy=post_state_entropy,
                work_reports=work_reports,
                auto_accumulate_services=auto_accumulate_services,
                service_id=service_id
            )

            outputs.append((service_id, output))

    for service_id, output in outputs:
            # Update gas usage
            accumulation_gas_utilized[service_id] = output.gas_used

            # Update transfers
            deferred_transfers += output.deferred_transfers

            # Process provided pre-images
            for s, i in output.preimages:
                availability = output.state_context.services.retrieve_preimage_availability(s, blake2b_256_hash(i), len(i))
                if availability == []:
                    output.state_context.services.store_preimage_availability(
                        s, blake2b_256_hash(i), len(i), [post_state_timeslot.number]
                    )
                    output.state_context.services.store_preimage(s, i)

            # Update services state with output
            accumulation_state.services.services.update(output.state_context.services.services)

            if output.accumulation_output is not None:
                beefy_commitment_map.update({service_id: output.accumulation_output})

            # TODO Needs review
            if service_id == accumulation_state.privileged_services.manager:
                # Process privilege services (m', a*, v*, z')
                accumulation_state.privileged_services.manager = output.state_context.privileged_services.manager # m'
                accumulation_state.privileged_services.assigners = output.state_context.privileged_services.assigners # a*
                accumulation_state.privileged_services.delegator = output.state_context.privileged_services.delegator # v*
                accumulation_state.privileged_services.always_accumulators = output.state_context.privileged_services.always_accumulators # z'

            # Process assigners (a')
            for c in range(CORE_COUNT):
                if service_id == accumulation_state.privileged_services.assigners[c]:
                    accumulation_state.privileged_services.assigners[c] = output.state_context.privileged_services.assigners[c]

            # Process delegator (v')
            if service_id == accumulation_state.privileged_services.delegator:
                accumulation_state.privileged_services.delegator = output.state_context.privileged_services.delegator  # v'

            # Process validator queue (i')
            if service_id == accumulation_state.privileged_services.delegator:
                accumulation_state.validator_queue = output.state_context.validator_queue

            # Process authorizer queue (q')
            for c in range(CORE_COUNT):
                if service_id == accumulation_state.privileged_services.assigners[c]:
                    accumulation_state.authorizer_queues = output.state_context.authorizer_queues

    return ParallelAccumulationOutput(
        accumulation_state=accumulation_state,
        deferred_transfers=deferred_transfers,
        accumulation_commitment=BeefyCommitmentMap(beefy_commitment_map=beefy_commitment_map),
        accumulation_gas_utilized=accumulation_gas_utilized
    )


def single_step_accumulation(
        accumulation_state: AccumulationStateComponents,
        post_state_timeslot: TimeslotState,
        post_state_entropy: EntropyState,
        work_reports: List[WorkReport],
        auto_accumulate_services: Dict[int, int],
        service_id: int
) -> 'PvmAccumulateOutput':
    """
    GP-0.6.1-eq:12.19 ∆1 | single step accumulation function

    Parameters
    ----------
    accumulation_state: AccumulationStateComponents
    post_state_timeslot: TimeslotState
    work_reports: List[WorkReport]
    auto_accumulate_services: Dict[int, int]
    service_id: int

    Returns
    -------
    PvmAccumulateOutput
    """
    g = substitute_if_nothing(auto_accumulate_services.get(service_id), 0)
    i = []
    for w in work_reports:
        for r in w.results:
            if r.service_id == service_id:
                g += r.accumulate_gas

                i.append(
                    AccumulationOperand(
                        work_report_hash=w.package_spec.hash,
                        work_report_exports_root=w.package_spec.exports_root,
                        work_report_authorizer_hash=w.authorizer_hash,
                        work_report_auth_output=w.auth_output,
                        work_result_payload_hash=r.payload_hash,
                        work_result_gas_limit=r.accumulate_gas,
                        work_exec_result=r.result,
                    )
                )

    return pvm_invoke_accumulate(
        state_context=accumulation_state,
        timeslot=post_state_timeslot.number,
        service_id=service_id,
        gas_limit=g,
        operands=i,
        post_entropy=post_state_entropy
    )
