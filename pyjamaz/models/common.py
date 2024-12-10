from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import H256, Array, U8, U32, Bytes, Null, U64, Vec, U16


@dataclass
class ValidatorData(Serializable):
    """
    GP-0.5.0-eq:6.7,6.8 (blackboard_K, blackboard_Y_336) | Collection of validator keys and metadata.

    Attributes
    ----------

    bandersnatch: H256
        GP-0.5.0-eq:6.9 (k_b | blackboard_H_B) | A validator's Bandersnatch key.
    ed25519: H256
        GP-0.5.0-eq:6.10 (k_e | blackboard_H_E) | A validator's Edwards 25519 key.
    bls: H256
        GP-0.5.0-eq:6.11 (k_BLS | blackboard_Y_BLS) | A validator's BLS key.
    metadata: H256
        GP-0.5.0-eq:6.12 (k_m | blackboard_Y_128) | Metadata for arbitrary data storage.
    """
    bandersnatch: bytes = field(metadata={'codec': H256})
    ed25519: bytes = field(metadata={'codec': H256})
    bls: bytes = field(metadata={'codec': Array(U8, 144)})
    metadata: bytes = field(metadata={'codec': Array(U8, 128)})


@dataclass
class WorkExecResult(Serializable):
    """
    GP-0.5.0-eq:11.6 (o) | Work result output or error of the execution of the code in the refine stage. Either a byte
    sequence in case it was successful or one of the possible errors

    Attributes
    ----------
    ok: Bytes
        GP-0.5.0-eq:11.6 (blackboard_Y) | The index of a service whose state is to be altered and thus whose refine
        code was already executed.
    out_of_gas: None
        GP-0.5.0-eq:11.7 (sign_INFINITY) | Out of gas error.
    panic: None
        GP-0.5.0-eq:11.7 (sign_LIGHTNING) | Panic error.
    bad_code: None
        GP-0.5.0-eq:11.7 (BAD) | Bad code error.
    code_oversize: None
        GP-0.5.0-eq:11.7 (BIG) | Code oversize error.
    """
    # TODO: JSON labels for out_of_gas (out-of-gas), bad_code (bad-code) and code_oversize (code-oversize) don't match
    ok: bytes = field(default=None, metadata={'codec': Bytes})
    out_of_gas: None = field(default=None, metadata={'codec': Null})
    panic: None = field(default=None, metadata={'codec': Null})
    bad_code: None = field(default=None, metadata={'codec': Null})
    code_oversize: None = field(default=None, metadata={'codec': Null})

    _codec_enum = True


@dataclass
class WorkResult(Serializable):
    """
    GP-0.5.0-eq:11.6 (blackboard_L) | A work result is the data conduit by which services' states may be altered through
    the computation done within a work-package.

    Attributes
    ----------
    service_id: U32
        GP-0.5.0-eq:11.6 (s) | The index of a service whose state is to be altered and thus whose refine code was
        already executed.
    code_hash: H256
        GP-0.5.0-eq:11.6 (c) | The hash of the code  of the service at the time of being reported.
    payload_hash: H256
        GP-0.5.0-eq:11.6 (l) | The hash of the payload within the work item which was executed in the refine stage to
        give this result.
    gas: U64
        GP-0.5.0-eq:11.6 (g) | The gas prioritization ration used when determining how much gas should be allocated to
        execute of this item's accumulate.
    result: WorkExecResult
        GP-0.5.0-eq:11.6 (o) | Output or error of the execution of the code.
    """
    service_id: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload_hash: bytes = field(metadata={'codec': H256})
    gas: int = field(metadata={'codec': U64})
    result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})


@dataclass
class RefinementContext(Serializable):
    """
    GP-0.5.0-eq:11.4 (blackboard_X) | A refinement context describes the context of the chain at the point that the
    report's corresponding work-package was evaluated.

    Attributes
    ----------
    anchor: H256
        GP-0.5.0-eq:11.4 (a) | The anchor header_hash.
    state_root: H256
        GP-0.5.0-eq:11.4 (s) | The anchor header's block associated posterior state-root.
    beefy_root: H256
        GP-0.5.0-eq:11.4 (b) | The anchor header's block associated posterior beefy-root.
    lookup_anchor: H256
        GP-0.5.0-eq:11.4 (l) | The lookup-anchor header_hash.
    lookup_anchor_slot: U32
        GP-0.5.0-eq:11.4 (t) | The lookup-anchor header's associated timeslot.
    prerequisites: Vec(H256)
        GP-0.5.0-eq:11.4 (bold_p) | An optional prerequisite work-package.
    """
    anchor: bytes = field(metadata={'codec': H256})
    state_root: bytes = field(metadata={'codec': H256})
    beefy_root: bytes = field(metadata={'codec': H256})
    lookup_anchor: bytes = field(metadata={'codec': H256})
    lookup_anchor_slot: int = field(metadata={'codec': U32})
    prerequisites: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class WorkPackageSpec(Serializable):
    """
    GP-0.5.0-eq:11.5 (blackboard_S) | Availability specification are used to ensure correct reconstruction and auditing
    the purported ramifications of any reported work-package.

    Attributes
    ----------
    hash: H256
        GP-0.5.0-eq:11.5 (h) | The work-package hash.
    length: U32
        GP-0.5.0-eq:11.5 (l) | The work bundle length.
    erasure_root: H256
        GP-0.5.0-eq:11.5 (u) | The erasure-root.
    exports_root: H256
        GP-0.5.0-eq:11.5 (e) | The segment-root.
    exports_count: U16
        GP-0.5.0-eq:11.5 (n) | The segment-count.
    """
    hash: bytes = field(metadata={'codec': H256})
    length: int = field(metadata={'codec': U32})
    erasure_root: bytes = field(metadata={'codec': H256})
    exports_root: bytes = field(metadata={'codec': H256})
    exports_count: int = field(metadata={'codec': U16})


@dataclass
class SegmentRootLookupItem(Serializable):
    """
    GP-0.5.0-eq:11.2 (bold_l) | The segment root lookup dictionary.

    Attributes
    ----------
    work_package_hash: H256
        GP-0.5.0-eq:11.2 (bold_l_key) | The segment_tree_lookup_item key.
    segment_tree_root: H256
        GP-0.5.0-eq:11.2 (bold_l_value) | The segment_tree_lookup_item key.
    """
    work_package_hash: bytes = field(metadata={'codec': H256})
    segment_tree_root: bytes = field(metadata={'codec': H256})


@dataclass
class WorkReport(Serializable):
    """
    GP-0.5.0-eq:11.2 (blackboard_W) | A work report comprises several work outputs.

    Attributes
    ----------
    package_spec: WorkPackageSpec
        GP-0.5.0-eq:11.2 (s) | The work package specification.
    context: RefinementContext
        GP-0.5.0-eq:11.2 (x) | The refinement context.
    core_index: U16
        GP-0.5.0-eq:11.2 (c) | The core-index.
    authorizer_hash: H256
        GP-0.5.0-eq:11.2 (a) | The authorizer hash.
    auth_output: Bytes
        GP-0.5.0-eq:11.2 (bold_o) | The output.
    segment_root_lookup: Vec(SegmentRootLookupItem)
        GP-0.5.0-eq:11.2 (bold_l) | The segment root lookup dictionary.
    results: Vec(WorkResult)
        GP-0.5.0-eq:11.2 (bold_r) | The results of the evaluation of each of the items inn the work package.
    """
    package_spec: WorkPackageSpec = field(metadata={'codec': WorkPackageSpec.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    core_index: int = field(metadata={'codec': U16})
    authorizer_hash: bytes = field(metadata={'codec': H256})
    auth_output: bytes = field(metadata={'codec': Bytes})
    # TODO: GP-0.5.0 states this needs to be a dictionary
    # segment_root_lookup: Dict[bytes, bytes] = field(metadata={'codec': Map(H256, H256)})
    segment_root_lookup: List[SegmentRootLookupItem] = field(metadata={'codec': Vec(SegmentRootLookupItem.to_codec_def())})
    results: List[WorkResult] = field(metadata={'codec': Vec(WorkResult.to_codec_def())})


@dataclass
class Assurance(Serializable):
    """
    GP-0.3.8-eq:116 (ρ[c]) | An assurance for a single core.

    Attributes
    ----------
    report: WorkReport
        GP-0.5.0-eq:11.1 (w) | A work report.
    timeout: U32
        GP-0.5.0-eq:11.1 (t) | A timeslot.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    timeout: int = field(metadata={'codec': U32})
