from typing import List, Set, Tuple
from pyjamaz.models.common import WorkReport
from pyjamaz.models.state import AccumulationQueueWorkPackage


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
    for work_report, dependencies in work_report_queue:
        modified_dependencies = dependencies.difference(accumulated_packages)
        modified_queue.append(
            AccumulationQueueWorkPackage(report=work_report, dependencies=modified_dependencies)
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
