from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE
from pyjamaz.merkle import WellBalancedMerkleTree
from pyjamaz.models.common import WorkReport, WorkPackage, WorkDigest, WorkExecResult, WorkPackageSpec
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm_interface.invocation import pvm_invoke_is_authorized, pvm_invoke_refine
from pyjamaz.utils import flatten_list


def work_result_computation(
        work_package: WorkPackage,
        core_index: int,
        services_state: ServicesState,
        extrinsics: dict[bytes, bytes]
) -> WorkReport:
    """
    GP-0.6.4-eq:14.11 (function Ξ) | the work result computation function.

    TODO WIP
    """

    segment_root_lookup_keys = {h for w in work_package.items for (h, n) in w.import_segments}

    auth_output = pvm_invoke_is_authorized(work_package, core_index)

    if type(auth_output.exit_condition.value) is not bytes:
        raise ProcessWorkpackageError("Unauthorized")

    refine_outputs = []

    for j in range(len(work_package.items)):

        work_item = work_package.items[j]

        export_segment_offset = sum([w.export_count for k, w in enumerate(work_package.items) if k < j])

        refine_output = pvm_invoke_refine(
            work_item_index=j,
            work_package=work_package,
            authorizer_output=auth_output.exit_condition.value,
            work_items_import_segments=[], # TODO
            export_segment_offset=export_segment_offset,
            services_state=services_state,
            extrinsics=extrinsics
        )

        if len(refine_output.export_segments) == work_item.export_count:
            work_exec_result = refine_output.work_exec_result
            export_segments = refine_output.export_segments
        elif not refine_output.work_exec_result.ok:
            work_exec_result = refine_output.work_exec_result
            export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)
        else:
            work_exec_result = WorkExecResult(bad_exports=True)
            export_segments = [bytes(EC_SEGMENT_SIZE)] * len(refine_output.export_segments)

        work_result = WorkDigest.from_work_item(
            work_item=work_package.items[j],
            result=work_exec_result,
            gas_used=refine_output.gas_used
        )

        refine_outputs.append((work_result, export_segments))

    # TODO inefficient: refactor refine_outputs to work_results and all_export_segments ?
    all_export_segments = flatten_list([o[1] for o in refine_outputs])

    # TODO finish implementation
    package_spec = WorkPackageSpec(
        hash=work_package.hash(),
        length=work_package.to_jam_bytes().length,
        erasure_root=bytes(32),
        exports_root=WellBalancedMerkleTree(all_export_segments).root(), # TODO replace with ConstantDepthMerkleTree
        exports_count=len(all_export_segments),
    )

    return WorkReport(
        package_spec=package_spec,
        context=work_package.context,
        core_index=core_index,
        authorizer_hash=work_package.authorizer_hash(),
        auth_output=auth_output.exit_condition.value,
        segment_root_lookup={}, # TODO
        results=[o[0] for o in refine_outputs],
        auth_gas_used=auth_output.gas_used
    )
