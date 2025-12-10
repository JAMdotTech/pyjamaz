import typing
from typing import List, Set

from pyjamaz.models.common import WorkReport
from pyjamaz.models.state import AccumulationQueueWorkPackage


def work_report_dependencies(work_report: WorkReport) -> AccumulationQueueWorkPackage:
    """
    GP-0.7.1-eq:12.6 (D) | Create a dependency graph of work report dependencies

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
    GP-0.7.1-eq:12.7 (E) | Queue editing function

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
    GP-0.7.1-eq:12.9 (P) | Extracts hashes from given work reports

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
    GP-0.7.1-eq:12.8 (Q) | Accumulate priority queue function

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


