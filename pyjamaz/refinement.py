"""Work-report computation with the GP's explicit (p, c, l, v) arguments."""

from pyjamaz.availability import BundleData, build_availability_artifacts, validate_work_package
from pyjamaz.erasure import erasure_data_shards
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import CORE_COUNT, EC_SEGMENT_SIZE, MAXIMUM_SIZE_ENCODED_WORK_REPORT
from pyjamaz.hostcalls.invocation import pvm_invoke_is_authorized, pvm_invoke_refine
from pyjamaz.hostcalls.models import PvmIsAuthorizedOutput
from pyjamaz.models.common import WorkDigest, WorkExecResult, WorkPackage, WorkReport
from pyjamaz.models.state import ServicesState


class Refinement:
    """Bind the historical state and data availability assumed by GP section 14.

    Each execution owns its inputs and resulting bundle/exports. The runtime
    acquires and persists data; this class never reads or writes node storage.
    """

    def __init__(self, services: ServicesState, data: BundleData):
        self.services = services
        self.data = data
        self.bundle = b''
        self.exported_segments: list[bytes] = []
        self.artifacts = None

    def compute_work_report(self, package: WorkPackage, core_index: int,
                            mappings: dict[bytes, bytes], erasure_shards: int) -> WorkReport:
        # GP-0.8.0-eq:14.13: Xi(p,c,l,v) -> WorkReport or bottom (ProcessWorkpackageError).
        # package=p, core_index=c, mappings=l, erasure_shards=v.
        self.bundle = b''
        self.exported_segments = []
        self.artifacts = None
        self._validate_arguments(package, core_index, mappings, erasure_shards)
        authorization = self.authorize(package, core_index)
        return self._compute_authorized_report(package, core_index, mappings, erasure_shards, authorization)

    @staticmethod
    def _validate_arguments(package, core_index, mappings, erasure_shards) -> None:
        validate_work_package(package)
        if (isinstance(core_index, bool) or not isinstance(core_index, int)
                or not 0 <= core_index < CORE_COUNT):
            raise ProcessWorkpackageError("invalid core index")
        try:
            erasure_data_shards(erasure_shards)
        except ValueError as exc:
            raise ProcessWorkpackageError(str(exc)) from exc
        expected_mappings = {
            entry.tree_root for item in package.items for entry in item.import_segments
            if entry.is_work_package_hash
        }
        if mappings.keys() != expected_mappings:
            raise ProcessWorkpackageError("segment-root dictionary has unexpected keys")

    def authorize(self, package: WorkPackage, core_index: int) -> PvmIsAuthorizedOutput:
        """Evaluate Psi_I(p,c) against this execution's detached service state."""
        # GP-0.8.0-eq:14.13 / B.1: authorization precedes data acquisition and Psi_R.
        validate_work_package(package)
        if (isinstance(core_index, bool) or not isinstance(core_index, int)
                or not 0 <= core_index < CORE_COUNT):
            raise ProcessWorkpackageError("invalid core index")
        self.bundle = b''
        self.exported_segments = []
        self.artifacts = None
        package.set_authorization_code(self.services)
        authorization = pvm_invoke_is_authorized(package, core_index)
        trace = authorization.work_exec_result.ok
        if not isinstance(trace, bytes):
            raise ProcessWorkpackageError("Unauthorized")
        if len(trace) > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
            raise ProcessWorkpackageError("Oversized auth result")
        return authorization

    def _compute_authorized_report(self, package: WorkPackage, core_index: int,
                                   mappings: dict[bytes, bytes], erasure_shards: int,
                                   authorization: PvmIsAuthorizedOutput) -> WorkReport:
        """Finish Xi using the authorization from the same package/core/state attempt."""
        self._validate_arguments(package, core_index, mappings, erasure_shards)
        trace = authorization.work_exec_result.ok
        if not isinstance(trace, bytes) or len(trace) > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
            raise ProcessWorkpackageError("invalid authorization result")
        # GP-0.8.0-eq:14.15-14.16: verify X, S_l and J_l after successful Psi_I.
        bundle = self.data.assemble_bundle(package, mappings)
        extrinsics = [self.data.extrinsic_data(item) for item in package.items]
        imports = [self.data.import_segments(mappings, item) for item in package.items]

        digests = []
        exports = []
        output_size = len(trace)
        export_offset = 0
        for index, item in enumerate(package.items):
            output = pvm_invoke_refine(
                core_index=core_index, work_item_index=index, work_package=package,
                authorizer_output=trace, work_items_import_segments=imports,
                export_segment_offset=export_offset, services_state=self.services, extrinsics=extrinsics,
            )
            # GP-0.8.0-eq:14.13, I(p,j): failure precedence and exactly m_e zero exports.
            result = output.work_exec_result
            item_exports = output.export_segments
            if output_size + len(result.ok or b'') > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
                result = WorkExecResult(digest_oversize=True)
            elif len(item_exports) != item.export_count:
                result = WorkExecResult(bad_exports=True)
            if result.ok is None:
                item_exports = [bytes(EC_SEGMENT_SIZE)] * item.export_count
            else:
                output_size += len(result.ok)
            digests.append(WorkDigest.from_work_item(item, result, output.gas_used))
            exports.extend(item_exports)
            export_offset += item.export_count

        # GP-0.8.0-eq:14.17: s = A(H(p), B(p,l), concat(exports), v).
        artifacts = build_availability_artifacts(package.hash(), bundle, exports, erasure_shards)
        spec = artifacts.spec
        report = WorkReport(
            package_spec=spec, context=package.context, core_index=core_index,
            authorizer_hash=package.authorizer_hash(), auth_output=trace,
            auth_gas_used=authorization.gas_used, segment_root_lookup=dict(mappings), results=digests,
        )
        self.bundle = bundle
        self.exported_segments = exports
        self.artifacts = artifacts
        return report
