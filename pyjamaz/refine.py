from typing import List

from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_SIZE_ENCODED_WORK_REPORT
from pyjamaz.models.common import WorkReport, WorkPackage, WorkDigest, WorkExecResult, WorkPackageSpec
from pyjamaz.models.state import ServicesState
from pyjamaz.hostcalls.invocation import pvm_invoke_is_authorized, pvm_invoke_refine
from pyjamaz.utils import flatten_list


def work_result_computation(
        work_package: WorkPackage,
        core_index: int,
        services_state: ServicesState,
        extrinsics: List[List[bytes]]
) -> WorkReport:
    """
    GP-0.7.1-eq:14.12 (function Ξ) | the work result computation function.

    TODO WIP
    """

    segment_root_lookup_keys = {h for w in work_package.items for (h, n) in w.import_segments}

    auth_output = pvm_invoke_is_authorized(work_package, core_index)

    if type(auth_output.work_exec_result.ok) is not bytes:
        raise ProcessWorkpackageError("Unauthorized")

    if len(auth_output.work_exec_result.ok) > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
        raise ProcessWorkpackageError("Oversized auth result")

    refine_outputs = []

    total_digest_size = len(auth_output.work_exec_result.ok)

    for j in range(len(work_package.items)):

        work_item = work_package.items[j]

        export_segment_offset = sum([w.export_count for k, w in enumerate(work_package.items) if k < j])

        refine_output = pvm_invoke_refine(
            work_item_index=j,
            work_package=work_package,
            authorizer_output=auth_output.work_exec_result.ok,
            work_items_import_segments=[], # TODO
            export_segment_offset=export_segment_offset,
            services_state=services_state,
            extrinsics=extrinsics
        )

        if total_digest_size + len(refine_output.work_exec_result.ok or b'') > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
            work_exec_result = WorkExecResult(digest_oversize=True)
            export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

        elif len(refine_output.export_segments) != work_item.export_count:
            work_exec_result = WorkExecResult(bad_exports=True)
            export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

        elif refine_output.work_exec_result.ok is None:
            work_exec_result = refine_output.work_exec_result
            export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

        else:
            work_exec_result = refine_output.work_exec_result
            export_segments = refine_output.export_segments
            total_digest_size += len(refine_output.work_exec_result.ok)

        work_result = WorkDigest.from_work_item(
            work_item=work_package.items[j],
            result=work_exec_result,
            gas_used=refine_output.gas_used
        )

        refine_outputs.append((work_result, export_segments))

    # TODO inefficient: refactor refine_outputs to work_results and all_export_segments ?
    all_export_segments = flatten_list([o[1] for o in refine_outputs])

    package_spec = WorkPackageSpec.create_from_work_package(work_package, [], [], [], all_export_segments)

    return WorkReport(
        package_spec=package_spec,
        context=work_package.context,
        core_index=core_index,
        authorizer_hash=work_package.authorizer_hash(),
        auth_output=auth_output.work_exec_result.ok,
        segment_root_lookup={}, # TODO
        results=[o[0] for o in refine_outputs],
        auth_gas_used=auth_output.gas_used
    )
