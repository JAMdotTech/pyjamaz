import typing
from base64 import b32encode
from dataclasses import dataclass, field
import socket
from typing import List, Dict
import ipaddress

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import H256, Array, U8, U32, Bytes, Null, U64, Vec, U16, Map, VarInt64, String

from pyjamaz.exceptions import BlockValidationError
from pyjamaz.graypaper_constants import MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE, SIZE_TRANSFER_MEMO
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import WellBalancedMerkleTree
from pyjamaz.pvm.constants import ExitCondition, ExitReason

if typing.TYPE_CHECKING:
    from pyjamaz.models.state import ServicesState


@dataclass
class ValidatorData(Serializable):
    """
    GP-0.7.1-eq:6.7,6.8 (blackboard_K, blackboard_B_336) | Collection of validator keys and metadata.

    Attributes
    ----------

    bandersnatch: H256
        GP-0.7.1-eq:6.9 (k_b | blackboard_H_~) | A validator's Bandersnatch key.
    ed25519: H256
        GP-0.7.1-eq:6.10 (k_e | blackboard_H_-) | A validator's Edwards 25519 key.
    bls: H256
        GP-0.7.1-eq:6.11 (k_l | blackboard_B_BLS) | A validator's BLS key.
    metadata: H256
        GP-0.7.1-eq:6.12 (k_m | blackboard_B_128) | Metadata for arbitrary data storage.
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

    def get_connection_dns(self) -> str:
        dns = b32encode(self.ed25519)
        return f"e{dns}@{self.get_metadata_ipaddress()}:{self.get_metadata_port()}"


@dataclass
class RefinementContext(Serializable):
    """
    GP-0.7.1-eq:11.4 (blackboard_C) | A refinement context describes the context of the chain at the point that the
    report's corresponding work-package was evaluated.

    Attributes
    ----------
    anchor: H256
        GP-0.7.1-eq:11.4 (a) | The anchor header_hash.
    state_root: H256
        GP-0.7.1-eq:11.4 (s) | The anchor header's block associated posterior state-root.
    beefy_root: H256
        GP-0.7.1-eq:11.4 (b) | The anchor header's block associated posterior beefy-root.
    lookup_anchor: H256
        GP-0.7.1-eq:11.4 (l) | The lookup-anchor header_hash.
    lookup_anchor_slot: U32
        GP-0.7.1-eq:11.4 (t) | The lookup-anchor header's associated timeslot.
    prerequisites: Vec(H256)
        GP-0.7.1-eq:11.4 (bold_p) | An optional prerequisite work-package.
    """
    anchor: bytes = field(metadata={'codec': H256})
    state_root: bytes = field(metadata={'codec': H256})
    beefy_root: bytes = field(metadata={'codec': H256})
    lookup_anchor: bytes = field(metadata={'codec': H256})
    lookup_anchor_slot: int = field(metadata={'codec': U32})
    prerequisites: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class Preimage:
    metadata: bytes
    metadata_version: int
    program_name: str
    program_version: str
    program_license: str
    program_authors: List[str]
    serialized_program: bytes

    @classmethod
    def extract(cls, data: bytes) -> "Preimage":
        jam_bytes = JamBytes(data)
        metadata = Bytes.decode(jam_bytes)
        try:
            metadata_bytes = JamBytes(metadata)
            metadata_version = U8.decode(metadata_bytes)
            program_name = String.decode(metadata_bytes)
            program_version = String.decode(metadata_bytes)
            program_license = String.decode(metadata_bytes)
            program_authors = Vec(String).decode(metadata_bytes)
        except Exception:
            metadata_version = None
            program_name = metadata.decode("utf-8")
            program_license = None
            program_authors = None
            program_version = None

        return Preimage(
            metadata=metadata,
            metadata_version=metadata_version,
            program_name=program_name,
            program_version=program_version,
            program_license=program_license,
            program_authors=program_authors,
            serialized_program=jam_bytes.get_remaining_bytes(),
        )



@dataclass
class WorkItemExtrinsic(Serializable):
    """
    GP-0.7.1-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.

    Attributes
    ----------
    hash: H256
        GP-0.7.1-eq:14.3 (blackboard_H) | Blob hashes.
    len: U32
        GP-0.7.1-eq:14.3 (blackboard_N type derived from encoding appendix) | A validator index.
    """
    hash: bytes = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U32})

    @classmethod
    def from_blob(cls, blob: bytes) -> "WorkItemExtrinsic":
        return WorkItemExtrinsic(
            hash=blake2b_256_hash(blob),
            len=len(blob)
        )


@dataclass
class ImportSegment(Serializable):
    """
    GP-0.7.1-eq:14.3 (bold_i) | Imported data segments consisting of the root of the segment tree and the index into it.

    Attributes
    ----------
    tree_root: H256
        GP-0.7.1-eq:14.3 (blackboard_H) | Root of the segment tree. # TODO what about H^[+] ?
    index: U16
        GP-0.7.1-eq:14.3 (blackboard_N type derived from encoding appendix) | Index into the segment tree.
    """
    tree_root: bytes = field(metadata={'codec': H256})
    index: int = field(metadata={'codec': U16})


@dataclass
class WorkItem(Serializable):
    """
    GP-0.7.1-eq:14.3 (blackboard_W) | Work item.

    Attributes
    ----------
    service: U32
        GP-0.7.1-eq:14.3 (s) | The index of a service to which it relates.
    code_hash: H256
        GP-0.7.1-eq:14.3 (c) | The hash of the code  of the service at the time of being reported.
    refine_gas_limit: U64
        GP-0.7.1-eq:14.3 (g) | The gas limit.
    accumulate_gas_limit: U64
        GP-0.7.1-eq:14.3 (a) | The gas limit.
    export_count: U16
        GP-0.7.1-eq:14.3 (e) | The number of data segments exported by this work item.
    payload: Bytes
        GP-0.7.1-eq:14.3 (bold_y) | A payload blob.
    import_segments: Vec(ImportSegment)
        GP-0.7.1-eq:14.3 (bold_i) | Imported data segments.
    extrinsic: Vec(WorkItemExtrinsic)
        GP-0.7.1-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.
    """
    service: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    refine_gas_limit: int = field(metadata={'codec': U64})
    accumulate_gas_limit: int = field(metadata={'codec': U64})
    export_count: int = field(metadata={'codec': U16})
    payload: bytes = field(metadata={'codec': Bytes})
    import_segments: List[ImportSegment] = field(metadata={'codec': Vec(ImportSegment.to_codec_def())})
    extrinsic: List[WorkItemExtrinsic] = field(metadata={'codec': Vec(WorkItemExtrinsic.to_codec_def())})

    def add_extrinsic(self, extrinsic_data: bytes):
        self.extrinsic.append(WorkItemExtrinsic(hash=blake2b_256_hash(extrinsic_data), len=len(extrinsic_data)))


@dataclass
class WorkPackage(Serializable):
    """
    GP-0.7.1-eq:14.2 (blackboard_P) | Work package.

    Attributes
    ----------
    auth_code_host: U32
        GP-0.7.1-eq:14.2 (h) | Index of the service which hosts the authorization code.
    auth_code_hash: H256
        GP-0.7.1-eq:14.2 (u) | The authorization code hash.
    context: pyjamaz.models.common.RefinementContext
        GP-0.7.1-eq:14.2 (bold_c) | The refinement context.
    authorization: Bytes
        GP-0.7.1-eq:14.2 (bold_j) | Authorization token blob.
    authorizer_config: bytes
        GP-0.7.1-eq:14.2 (bold_f) | A parameterization blob.
    items: Vec(WorkItem)
        GP-0.7.1-eq:14.2 (bold_w) | A sequence of work items.
    """
    auth_code_host: int = field(metadata={'codec': U32})
    auth_code_hash: bytes = field(metadata={'codec': H256})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    authorization: bytes = field(metadata={'codec': Bytes})
    authorizer_config: bytes = field(metadata={'codec': Bytes})
    items: List[WorkItem] = field(metadata={'codec': Vec(WorkItem.to_codec_def())}) # TODO min 1, max constant_I (16)

    #TODO: implement contraints as mentioned in GP-0.7.1-eq:14.4,14.5,14.7

    def hash(self) -> bytes:
        return blake2b_256_hash(self.to_jam_bytes().to_bytes())

    def authorizer_hash(self) -> bytes:
        """
        GP-0.7.1-eq:14.10 (bold_p_a) | Authorizer hash.
        """
        return blake2b_256_hash(self.auth_code_hash + self.authorizer_config)

    @property
    def authorization_metadata(self) -> str:
        """
        GP-0.7.1-eq:14.10 (bold_p_m) | Authorization metadata.
        """
        return getattr(self, '_authorization_metadata', None)

    @authorization_metadata.setter
    def authorization_metadata(self, value: str) -> None:
        setattr(self, '_authorization_metadata', value)

    @property
    def authorization_code(self) -> bytes:
        """
        GP-0.7.1-eq:14.1 (bold_p_c) | Authorization code.
        """
        return getattr(self, '_authorization_code', None)

    def set_authorization_code(self, services_state: 'ServicesState') -> None:
        preimage_blob = services_state.historical_preimage_lookup(
            service_account_id=self.auth_code_host,
            timeslot=self.context.lookup_anchor_slot,
            preimage_hash=self.auth_code_hash
        )
        if preimage_blob:
            preimage = Preimage.extract(preimage_blob)

            setattr(self, '_authorization_code', preimage.serialized_program)
            self.authorization_metadata = preimage.program_name

    def add_work_item(self, work_item: WorkItem) -> None:
        # Check contraints
        if sum([len(w.extrinsic) for w in self.items + [work_item]]) > MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE:
            raise BlockValidationError(f"Too many extrinsics in this work package (max {MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE})")
        self.items.append(work_item)


@dataclass
class WorkExecResult(Serializable):
    """
    GP-0.7.1-eq:11.7 (function_O = blackboard_E u blackboard_B) | Work result output or error of the execution of the code in the refine stage.
    Either a byte sequence in case it was successful or one of the possible errors

    Attributes
    ----------
    ok: Bytes
        GP-0.7.1-eq:11.6 (blackboard_B) | The index of a service whose state is to be altered and thus whose refine
        code was already executed.
    out_of_gas: None
        GP-0.7.1-eq:11.7 (sign_INFINITY) | Out of gas error.
    panic: None
        GP-0.7.1-eq:11.7 (sign_LIGHTNING) | Panic error.
    bad_exports: None
        GP-0.7.1-eq:11.7 (sign_CIRCLED_CIRCLE) | Bad exports error.
    digest_oversize: None
        GP-0.7.1-eq:11.7 (sign_CIRCLED_DASH) | Digest oversize error.
    bad_code: None
        GP-0.7.1-eq:11.7 (BAD) | Bad code error.
    code_oversize: None
        GP-0.7.1-eq:11.7 (BIG) | Code oversize error.
    """
    # TODO: JSON labels for out_of_gas (out-of-gas), bad_code (bad-code) and code_oversize (code-oversize) don't match
    ok: bytes = field(default=None, metadata={'codec': Bytes})
    out_of_gas: bool = field(default=None, metadata={'codec': Null})
    panic: bool = field(default=None, metadata={'codec': Null})
    bad_exports: bool = field(default=None, metadata={'codec': Null})
    digest_oversize: bool = field(default=None, metadata={'codec': Null})
    bad_code: bool = field(default=None, metadata={'codec': Null})
    code_oversize: bool = field(default=None, metadata={'codec': Null})

    _codec_enum = True

    @classmethod
    def from_exit_condition(cls, exit_condition: ExitCondition) -> "WorkExecResult":
        work_exec_result = WorkExecResult()

        if exit_condition.reason == ExitReason.out_of_gas:
            work_exec_result.out_of_gas = True
        elif exit_condition.reason == ExitReason.panic:
            work_exec_result.panic = True
        elif exit_condition.reason == ExitReason.halt:
            work_exec_result.ok = exit_condition.value
        else:
            raise ValueError(f"Unsupported exit reason {exit_condition.reason}")
        return work_exec_result


@dataclass
class RefineLoad(Serializable):
    """
    GP-0.7.1-eq:11.6 (blackboard_D) | Part of a work result (todo: integrate with WorkResult?)

    Attributes
    ----------
    gas_used: VarInt64
        GP-0.7.1-eq:11.6 (u)
    imports: VarInt64
        GP-0.7.1-eq:11.6 (i)
    extrinsic_count: VarInt64
        GP-0.7.1-eq:11.6 (x)
    extrinsic_size: VarInt64
        GP-0.7.1-eq:11.6 (z)
    exports: VarInt64
        GP-0.7.1-eq:11.6 (e)
    """
    gas_used: int = field(metadata={'codec': VarInt64})
    imports: int = field(metadata={'codec': VarInt64})
    extrinsic_count: int = field(metadata={'codec': VarInt64})
    extrinsic_size: int = field(metadata={'codec': VarInt64})
    exports: int = field(metadata={'codec': VarInt64})


@dataclass
class WorkDigest(Serializable):
    """
    GP-0.7.1-eq:11.6 (blackboard_D) | A work digest is the data conduit by which services' states may be altered
    through the computation done within a work-package.

    Attributes
    ----------
    service_id: U32
        GP-0.7.1-eq:11.6 (s) | The index of a service whose state is to be altered and thus whose refine code was
        already executed.
    code_hash: H256
        GP-0.7.1-eq:11.6 (c) | The hash of the code of the service at the time of being reported.
    payload_hash: H256
        GP-0.7.1-eq:11.6 (y) | The hash of the payload within the work item which was executed in the refine stage to
        give this result.
    accumulate_gas: U64
        GP-0.7.1-eq:11.6 (g) | The gas prioritization ration used when determining how much gas should be allocated to
        execute of this item's accumulate.
    result: WorkExecResult
        GP-0.7.1-eq:11.6 (bold_l) | Output or error of the execution of the code.
    refine_load: RefineLoad
        GP-0.7.1-eq:11.6 (bold_l) | Integrate RefineLoad for attributes: u, i, x, z, & e
    """
    # TODO: Integrate RefineLoad for attributes: u, i, x, z, & e
    service_id: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload_hash: bytes = field(metadata={'codec': H256})
    accumulate_gas: int = field(metadata={'codec': U64})
    result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})
    refine_load: RefineLoad = field(metadata={'codec': RefineLoad.to_codec_def()})

    @classmethod
    def from_work_item(cls, work_item: WorkItem, result: WorkExecResult, gas_used: int) -> "WorkDigest":
        """
        GP-0.7.0-eq:14.9 (function_C) | the item-to-result function
        """
        # Rename to WorkDigest
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
    GP-0.7.1-eq:11.5 (blackboard_Y) | Availability specifications are used to ensure correct reconstruction and
    auditing the purported ramifications of any reported work-package.

    Attributes
    ----------
    hash: H256
        GP-0.7.1-eq:11.5 (p) | The work-package hash.
    length: U32
        GP-0.7.1-eq:11.5 (l) | The work bundle length.
    erasure_root: H256
        GP-0.7.1-eq:11.5 (u) | The erasure-root.
    exports_root: H256
        GP-0.7.1-eq:11.5 (e) | The segment-root.
    exports_count: U16
        GP-0.7.1-eq:11.5 (n) | The segment-count.
    """
    hash: bytes = field(metadata={'codec': H256})
    length: int = field(metadata={'codec': U32})
    erasure_root: bytes = field(metadata={'codec': H256})
    exports_root: bytes = field(metadata={'codec': H256})
    exports_count: int = field(metadata={'codec': U16})

    @classmethod
    def create_from_work_package(cls,
                                 work_package: WorkPackage, extrinsic_data: List[bytes], imported_segments: List[bytes],
                                 justification_data: List[bytes], exported_segments: List[bytes],
                                 ) -> "WorkPackageSpec":
        """
        GP-0.7.1-eq:14.17 function_A | creates an availability specifier from a workpackage
        # TODO finish implementation
        """
        # serialized_auditable_work_package = work_package.serialize_to_auditable()

        return WorkPackageSpec(
            hash=work_package.hash(),
            length=work_package.to_jam_bytes().length,
            erasure_root=bytes(32),
            exports_root=WellBalancedMerkleTree(exported_segments).root(), # TODO replace with ConstantDepthMerkleTree
            exports_count=len(exported_segments),
        )



@dataclass
class WorkReport(Serializable):
    """
    GP-0.7.0-eq:11.2 (blackboard_R) | A work report comprises several work outputs.

    Attributes
    ----------
    package_spec: WorkPackageSpec
        GP-0.7.1-eq:11.2 (s) | The work package specification.
    context: RefinementContext
        GP-0.7.01-eq:11.2 (bold_c) | The refinement context.
    core_index: VarInt64
        GP-0.7.1-eq:11.2 (c) | The core-index.
    authorizer_hash: H256
        GP-0.7.1-eq:11.2 (a) | The authorizer hash.
    auth_gas_used: VarInt64
        GP-0.7.1-eq:11.2 (g)
    auth_output: Bytes
        GP-0.7.1-eq:11.2 (bold_t) | The output.
    segment_root_lookup: Map(H256, H256)
        GP-0.7.1-eq:11.2 (bold_l) | The segment root lookup dictionary.
    results: Vec(WorkDigest)
        GP-0.7.1-eq:11.2 (bold_d) | The results of the evaluation of each of the items in the work package.
    """
    package_spec: WorkPackageSpec = field(metadata={'codec': WorkPackageSpec.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    core_index: int = field(metadata={'codec': VarInt64})
    authorizer_hash: bytes = field(metadata={'codec': H256})
    auth_gas_used: int = field(metadata={'codec': VarInt64})
    auth_output: bytes = field(metadata={'codec': Bytes})
    segment_root_lookup: Dict[bytes, bytes] = field(metadata={'codec': Map(H256, H256)})
    results: List[WorkDigest] = field(metadata={'codec': Vec(WorkDigest.to_codec_def())})

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
    GP-0.7.1-eq:11.1 (ρ[C]) | An assurance for a single core.

    Attributes
    ----------
    report: WorkReport
        GP-0.7.1-eq:11.1 (bold_r) | A work report.
    timeout: U32
        GP-0.7.1-eq:11.1 (t) | A timeslot.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    timeout: int = field(metadata={'codec': U32})


@dataclass
class TicketBody(Serializable):
    # y
    id: bytes = field(metadata={'codec': H256})
    # e
    attempt: int = field(metadata={'codec': U8})


@dataclass
class AccumulationOperand(Serializable):
    """
    GP-0.7.1-eq:12.13 (blackboard_U) | Operand to the PVM accumulation function.

    Attributes
    ----------
    work_report_hash: H256
        GP-0.7.1-eq:12.13 (p) | [description].
    work_report_exports_root: H256
        GP-0.7.1-eq:12.13 (e) | [description].
    work_report_authorizer_hash: H256
        GP-0.7.1-eq:12.13 (a) | [description].
    work_result_payload_hash: H256
        GP-0.7.1-eq:12.13 (y) | [description].
    work_result_gas_limit: VarInt64
        GP-0.7.1-eq:12.13 (g) | [description].
    work_exec_result: WorkExecResult
        GP-0.7.1-eq:12.13 (bold_l) | [description].
    work_report_auth_output: Bytes
        GP-0.7.1-eq:12.13 (bold_t) | [description].
    """
    # TODO: check order of work_exec_result & work_report_auth_output (swapped in 0.7.0)
    work_report_hash: bytes = field(metadata={'codec': H256})
    work_report_exports_root: bytes = field(metadata={'codec': H256})
    work_report_authorizer_hash: bytes = field(metadata={'codec': H256})
    work_result_payload_hash: bytes = field(metadata={'codec': H256})
    work_result_gas_limit: int = field(metadata={'codec': VarInt64})
    work_exec_result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})
    work_report_auth_output: bytes = field(metadata={'codec': Bytes})


@dataclass
class DeferredTransfer(Serializable):
    """
    GP-0.7.1-eq:12.14 (blackboard_X) | A single deferred transfer.

    Attributes
    ----------
    sender: U32
        GP-0.7.1-eq:12.14 (s) | Sender of a deferred transfer.
    receiver: U32
        GP-0.7.1-eq:12.14 (d) | Receiver of a deferred transfer (destination).
    amount: U64
        GP-0.7.1-eq:12.14 (a) | Balance to be transferred (amount) of the deferred transfer.
    memo: Array(U8, SIZE_TRANSFER_MEMO)
        GP-0.7.1-eq:12.14 (m) | Constant length memo blob of the deferred transfer.
    gas_limit: U64
        GP-0.7.1-eq:12.14 (g) | Gas limit of the deferred transfer.
    """
    sender: int = field(metadata={'codec': U32})
    receiver: int = field(metadata={'codec': U32})
    amount: int = field(metadata={'codec': U64})
    memo: bytes = field(metadata={'codec': Array(U8, SIZE_TRANSFER_MEMO)})
    gas_limit: int = field(metadata={'codec': U64})


@dataclass
class AccumulationInput(Serializable):
    """
    GP-0.7.1-eq:12.15 (blackboard_I)
    """
    accumulation_operand: AccumulationOperand = field(default=None, metadata={'codec': AccumulationOperand.to_codec_def()})
    deferred_transfer: DeferredTransfer = field(default=None, metadata={'codec': DeferredTransfer.to_codec_def()})

    _codec_enum = True
