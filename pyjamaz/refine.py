from pyjamaz.models.common import WorkReport, WorkPackage, WorkResult, WorkExecResult
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm_interface.invocation import pvm_invoke_is_authorized, pvm_invoke_refine


def work_result_computation(work_package: WorkPackage, core_index: int, services_state: ServicesState) -> WorkReport:
    """
    GP-0.6.4-eq:14.11 (function Ξ) | the work result computation function.

    TODO WIP
    """

    segment_root_lookup_keys = {h for w in work_package.items for (h, n) in w.import_segments}

    auth_output = pvm_invoke_is_authorized(work_package, core_index)

    if type(auth_output.exit_condition.value) is not bytes:
        raise ValueError("unauthorized") # TODO

    # TODO check gas_used auth_output.gas_limit

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
            services_state=services_state
        )

        if len(refine_output.export_segments) == work_item.export_count:
            result = WorkExecResult.from_exit_condition(refine_output.exit_condition)
            work_result = WorkResult.from_work_item(
                work_item=work_package.items[j],
                result=result,
                gas_used=refine_output.gas_used
            )
        elif type(refine_output.exit_condition.value) is not bytes: # TODO
            raise NotImplementedError("TODO")
        else:
            exit_condition = ExitCondition(reason=ExitReason.bad_exports) # TODO
            raise NotImplementedError("TODO")

        refine_outputs.append((work_result, refine_output.exit_condition))

    return WorkReport(
        package_spec=None, # TODO
        context=work_package.context,
        core_index=core_index,
        authorizer_hash=work_package.authorizer_hash(),
        auth_output=auth_output.exit_condition.value,
        segment_root_lookup={}, # TODO
        results=[o[0] for o in refine_outputs],
        auth_gas_used=auth_output.gas_used
    )
