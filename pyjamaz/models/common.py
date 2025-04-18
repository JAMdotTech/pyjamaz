import typing
from dataclasses import dataclass, field
import socket
from typing import List, Dict
import ipaddress

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import H256, Array, U8, U32, Bytes, Null, U64, Vec, U16, Map, VarInt64
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.pvm.constants import ExitCondition, ExitReason

if typing.TYPE_CHECKING:
    from pyjamaz.models.state import ServicesState


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

    def get_metadata_ipaddress(self) -> str:
        """
        Extracts the IP address from the validator metadata

        Returns
        -------
        str
        """
        if self.metadata[4:16] == bytes(12):
            return str(ipaddress.IPv4Address(bytes(self.metadata[:4])))
        else:
            return socket.inet_ntop(socket.AF_INET6, self.metadata[:16])

    def get_metadata_port(self) -> int:
        """
        Extracts the port number from the validator metadata
        Returns
        -------
        int
        """
        return int.from_bytes(self.metadata[16:18], byteorder='little')


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
class Preimage(Serializable):
    metadata: bytes
    serialized_program: bytes

    @classmethod
    def extract(cls, data: bytes) -> "Preimage":
        jam_bytes = JamBytes(data)
        return Preimage(
            metadata=Bytes.decode(jam_bytes),
            serialized_program=jam_bytes.get_remaining_bytes(),
        )



@dataclass
class WorkItemExtrinsic(Serializable):
    """
    GP-0.6.4-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.

    Attributes
    ----------
    hash: H256
        GP-0.6.4-eq:14.3 (blackboard_H) | Blob hashes.
    len: U32
        GP-0.6.4-eq:14.3 (blackboard_N type derived from encoding appendix) | A validator index.
    """
    hash: bytes = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U32})


@dataclass
class ImportSegment(Serializable):
    """
    GP-0.6.4-eq:14.3 (bold_i) | Imported data segments consisting of the root of the segment tree and the index into it.

    Attributes
    ----------
    tree_root: H256
        GP-0.6.4-eq:14.3 (blackboard_H) | Root of the segment tree. # TODO what about H^[+] ?
    index: U16
        GP-0.6.4-eq:14.3 (blackboard_N type derived from encoding appendix) | Index into the segment tree.
    """
    tree_root: bytes = field(metadata={'codec': H256})
    index: int = field(metadata={'codec': U16})


@dataclass
class WorkItem(Serializable):
    """
    GP-0.6.4-eq:14.3 (blackboard_I) | Work item.

    Attributes
    ----------
    service: U32
        GP-0.6.4-eq:14.3 (s) | The index of a service to which it relates.
    code_hash: H256
        GP-0.6.4-eq:14.3 (c) | The hash of the code  of the service at the time of being reported.
    payload: Bytes
        GP-0.6.4-eq:14.3 (bold_y) | A payload blob.
    refine_gas_limit: U64
        GP-0.6.4-eq:14.3 (g) | The gas limit.
    accumulate_gas_limit: U64
        GP-0.6.4-eq:14.3 (a) | The gas limit.
    import_segments: Vec(ImportSegment)
        GP-0.6.4-eq:14.3 (bold_i) | Imported data segments.
    extrinsic: Vec(WorkItemExtrinsic)
        GP-0.6.4-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.
    export_count: U16
        GP-0.6.4-eq:14.3 (e) | The number of data segments exported by this work item.
    """
    service: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload: bytes = field(metadata={'codec': Bytes})
    refine_gas_limit: int = field(metadata={'codec': U64})
    accumulate_gas_limit: int = field(metadata={'codec': U64})
    import_segments: List[ImportSegment] = field(metadata={'codec': Vec(ImportSegment.to_codec_def())})
    extrinsic: List[WorkItemExtrinsic] = field(metadata={'codec': Vec(WorkItemExtrinsic.to_codec_def())})
    export_count: int = field(metadata={'codec': U16})


@dataclass
class Authorizer(Serializable):
    """
    GP-0.6.4-eq:14.2 (u & bold_p) | A tuple of the authorization code hash and the parameterization blob.

    Attributes
    ----------
    code_hash: H256
        GP-0.6.4-eq:14.2 (u) | The authorization code hash.
    params: Bytes
        GP-0.6.4-eq:14.2 (bold_p) | A parameterization blob.
    """
    code_hash: bytes = field(metadata={'codec': H256})
    params: bytes = field(metadata={'codec': Bytes})


@dataclass
class WorkPackage(Serializable):
    """
    GP-0.6.4-eq:14.2 (blackboard_P) | Work package.

    Attributes
    ----------
    authorization: Bytes
        GP-0.6.4-eq:14.2 (bold_j) | Authorization token blob.
    auth_code_host: U32
        GP-0.6.4-eq:14.2 (h) | Index of the service which hosts the authorization code.
    authorizer: Authorizer
        GP-0.5.0-eq:14.2 (u & bold_p) | A tuple of the authorization code hash and the parameterization blob.
    context: pyjamaz.models.common.RefinementContext
        GP-0.5.0-eq:14.2 (bold_x) | The refinement context.
    items: Vec(WorkItem)
        GP-0.5.0-eq:14.2 (bold_w) | A sequence of work items.
    """
    authorization: bytes = field(metadata={'codec': Bytes})
    auth_code_host: int = field(metadata={'codec': U32})
    authorizer: Authorizer = field(metadata={'codec': Authorizer.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    items: List[WorkItem] = field(metadata={'codec': Vec(WorkItem.to_codec_def())}) # TODO min 1, max constant_I (16)

    #TODO: implement bold_p_a & bold_p_c as mentioned in GP-0.6.4-eq:14.9
    #TODO: implement contraints as mentioned in GP-0.6.4-eq:14.4,14.5,14.7

    def hash(self):
        return blake2b_256_hash(self.to_jam_bytes().to_bytes())

    def authorizer_hash(self) -> bytes:
        """
        GP-0.6.4-eq:14.9 (blackboard_P_a) | Authorizer hash.
        """
        return blake2b_256_hash(self.authorizer.to_jam_bytes().to_bytes())

    @property
    def authorization_metadata(self) -> bytes:
        """
        GP-0.6.4-eq:14.9 (blackboard_P_m) | Authorization metadata.
        """
        return getattr(self, '_authorization_metadata', None)

    @authorization_metadata.setter
    def authorization_metadata(self, value: bytes) -> None:
        setattr(self, '_authorization_metadata', value)

    @property
    def authorization_code(self) -> bytes:
        """
        GP-0.6.4-eq:14.9 (blackboard_P_c) | Authorization code.
        """
        return getattr(self, '_authorization_code', None)

    def set_authorization_code(self, services_state: 'ServicesState') -> None:
        preimage = Preimage.extract(services_state.historical_preimage_lookup(
            service_account_id=self.auth_code_host,
            timeslot=self.context.lookup_anchor_slot,
            preimage_hash=self.authorizer.code_hash
        ))

        setattr(self, '_authorization_code', preimage.serialized_program)
        self.authorization_metadata = preimage.metadata


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
    bad_exports: None = field(default=None, metadata={'codec': Null})
    bad_code: None = field(default=None, metadata={'codec': Null})
    code_oversize: None = field(default=None, metadata={'codec': Null})

    _codec_enum = True

    @classmethod
    def from_exit_condition(cls, exit_condition: ExitCondition) -> "WorkExecResult":
        work_exec_result = WorkExecResult()
        # TODO WIP TBD merge WorkExecResult with ExitCondition, same according to GP
        if exit_condition.reason == ExitReason.out_of_gas:
            work_exec_result.out_of_gas = True
        elif exit_condition.reason == ExitReason.panic:
            work_exec_result.panic = True
        elif exit_condition.reason == ExitReason.bad_exports:
            work_exec_result.bad_exports = True
        elif exit_condition.reason == ExitReason.bad_code:
            work_exec_result.bad_code = True
        elif exit_condition.reason == ExitReason.code_oversize:
            work_exec_result.code_oversize = True
        else:
            raise ValueError(f"Unsupported exit reason {exit_condition.reason}")
        return work_exec_result






@dataclass
class RefineLoad(Serializable):
    """
    GP-0.6.4-eq:11.6 (blackboard_L) | Part of a work result (todo: integrate with WorkResult?)

    Attributes
    ----------
    gas_used: VarInt64
        GP-0.6.4-eq:11.6 (u)
    imports: VarInt64
        GP-0.6.4-eq:11.6 (i)
    extrinsic_count: VarInt64
        GP-0.6.4-eq:11.6 (x)
    extrinsic_size: VarInt64
        GP-0.6.4-eq:11.6 (z)
    exports: VarInt64
        GP-0.6.4-eq:11.6 (e)
    """
    gas_used: int = field(metadata={'codec': VarInt64})
    imports: int = field(metadata={'codec': VarInt64})
    extrinsic_count: int = field(metadata={'codec': VarInt64})
    extrinsic_size: int = field(metadata={'codec': VarInt64})
    exports: int = field(metadata={'codec': VarInt64})


@dataclass
class WorkResult(Serializable):
    """
    GP-0.6.4-eq:11.6 (blackboard_L) | A work result is the data conduit by which services' states may be altered through
    the computation done within a work-package.

    Attributes
    ----------
    service_id: U32
        GP-0.6.4-eq:11.6 (s) | The index of a service whose state is to be altered and thus whose refine code was
        already executed.
    code_hash: H256
        GP-0.6.4-eq:11.6 (c) | The hash of the code  of the service at the time of being reported.
    payload_hash: H256
        GP-0.6.4-eq:11.6 (y) | The hash of the payload within the work item which was executed in the refine stage to
        give this result.
    accumulate_gas: U64
        GP-0.6.4-eq:11.6 (g) | The gas prioritization ration used when determining how much gas should be allocated to
        execute of this item's accumulate.
    result: WorkExecResult
        GP-0.6.4-eq:11.6 (d) | Output or error of the execution of the code.
    """
    service_id: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload_hash: bytes = field(metadata={'codec': H256})
    accumulate_gas: int = field(metadata={'codec': U64})
    result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})
    refine_load: RefineLoad = field(metadata={'codec': RefineLoad.to_codec_def()})

    @classmethod
    def from_work_item(cls, work_item: WorkItem, result: WorkExecResult, gas_used: int) -> "WorkResult":
        """
        GP-0.6.4-eq:14.8 (function_C) | the item-to-result function
        """
        return cls(
            service_id=work_item.service,
            code_hash=work_item.code_hash,
            payload_hash=blake2b_256_hash(work_item.payload),
            accumulate_gas=work_item.accumulate_gas_limit,
            result=result,
            refine_load=RefineLoad(
                gas_used=gas_used,
                imports=len(work_item.import_segments),
                exports=work_item.export_count,
                extrinsic_count=len(work_item.extrinsic),
                extrinsic_size=sum([x.len for x in work_item.extrinsic])
            )
        )


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
class WorkReport(Serializable):
    """
    GP-0.6.4-eq:11.2 (blackboard_W) | A work report comprises several work outputs.

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
    auth_gas_used: VarInt64
        GP-0.6.4-eq:11.2 (g)
    """
    package_spec: WorkPackageSpec = field(metadata={'codec': WorkPackageSpec.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    core_index: int = field(metadata={'codec': U16})
    authorizer_hash: bytes = field(metadata={'codec': H256})
    auth_output: bytes = field(metadata={'codec': Bytes})
    segment_root_lookup: Dict[bytes, bytes] = field(metadata={'codec': Map(H256, H256)})
    results: List[WorkResult] = field(metadata={'codec': Vec(WorkResult.to_codec_def())})
    auth_gas_used: int = field(metadata={'codec': VarInt64})

    def dependency_count(self) -> int:
        """
        Returns the sum of segment-root lookups and prerequisites

        Returns
        -------
        int
        """
        return len(self.segment_root_lookup) + len(self.context.prerequisites)



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


@dataclass
# Todo: (Re)move, annotate, reference-GP
class TicketBody(Serializable):
    id: bytes = field(metadata={'codec': H256})
    attempt: int = field(metadata={'codec': U8})


@dataclass
class AccumulationOperand(Serializable):
    """
    GP-0.6.3-eq:12.18 (blackboard_O) | Operand to the PVM accumulation function
    """
    # h
    work_report_hash: bytes = field(metadata={'codec': H256})
    # e
    work_report_exports_root: bytes = field(metadata={'codec': H256})
    # a
    work_report_authorizer_hash: bytes = field(metadata={'codec': H256})
    # o
    work_report_auth_output: bytes = field(metadata={'codec': Bytes})
    # y
    work_result_payload_hash: bytes = field(metadata={'codec': H256})
    # d
    work_exec_result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})
