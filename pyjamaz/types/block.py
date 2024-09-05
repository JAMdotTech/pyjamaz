from dataclasses import dataclass, field
from math import floor
from typing import List, Optional

from jamcodec.types import H256, U32, Option, Vec, Array, U8, U16, Bool, H512, Bytes, U64, Enum, Null
from pyjamaz.graypaper_constants import VALIDATOR_COUNT, EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.types.common import OpaqueHash, BandersnatchKey, ByteArray784

from jamcodec.mixins import Serializable


@dataclass
class TicketBody(Serializable):
    id: OpaqueHash = field(metadata={'codec': H256})  # OpaqueHash
    attempt: int = field(metadata={'codec': U8})   # U8


@dataclass
class EpochMark(Serializable):
    entropy: OpaqueHash = field(metadata={'codec': H256})
    validators: List[BandersnatchKey] = field(metadata={'codec': Array(H256, VALIDATOR_COUNT)})


@dataclass
class TicketEnvelope(Serializable):
    """
    GP-0.3.6-eq:73 (bold_E_T) | Single item in the tickets extrinsic. Manages selection of validators for permissioning
    of block authoring

    Attributes
    ----------
    attempt: U16
        GP-0.3.6-eq:73 (r) |
        An entry index
    signature: H512
        GP-0.3.6-eq:73 (p) |
        Proof of a ticket's validity
    """
    attempt: int = field(metadata={'codec': U8})
    signature: ByteArray784 = field(metadata={'codec': Array(U8, 784)})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks(Serializable):
    epoch_mark: Optional[EpochMark] = field(default=None, metadata={'codec': Option(EpochMark.to_codec_def())})   # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))})  # Tickets signal. OPTIONAL

@dataclass
class Judgement(Serializable):
    """
    GP-0.3.6-eq:97 (third element of the tuple in bold_v) | An individual judgements coming from a validator

    Attributes
    ----------
    vote: Bool
        GP-0.3.6-eq:97 ({T/F}}) |
        A vote
    index: U16
        GP-0.3.6-eq:97 (blackboard_N_V) |
         A validator index
    signature: H512
        GP-0.3.6-eq:97 (blackboard_E) |
        A Ed25519 signature corresponding to the validator index
    """
    vote: bool = field(metadata={'codec': Bool()})
    index: int = field(metadata={'codec': U16})
    signature: bytes =  field(metadata={'codec': H512})

@dataclass
class Verdict(Serializable):
    """
    GP-0.3.6-eq:97 (bold_v) | A compilation of judgements coming from exactly two-thirds plus one of either the active
    validator set or the previous epoch's validator set

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:97 (blackboard_H in bold_v) |
        A work-report hash
    age: U32
        GP-0.3.6-eq:97 (second element of the tuple in bold_v) |
        Determines whether the current or the previous validator set applies to this verdict
    votes: Vec(fault)
        GP-0.3.6-eq:97 (third element of the tuple in bold_v) | A set of judgements by two-thirds plus one of either the current
        or the previous validator set
    """
    target: bytes = field(metadata={'codec': H256})
    age: int = field(metadata={'codec': U32})
    # Todo: change array size to use constants: 1+(floor(VALIDATOR_COUNT/3)*2)
    votes: List[Judgement] = field(metadata={'codec': Array(Judgement.to_codec_def(), 1+(floor(VALIDATOR_COUNT/3)*2))})

@dataclass
class Culprit(Serializable):
    """
    GP-0.3.6-eq:97 (bold_c) | Proof of misbahaviour of one or more validators by guaranteeing a work-report found to be
    invalid. This is considered an offence

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:97 (blackboard_H) |
        A work-report hash
    key: H256
        GP-0.3.6-eq:97 (blackboard_H_E) |
        A validator Ed25519 public key
    signature: H512
        GP-0.3.6-eq:97 (blackboard_E) |
        A Ed25519 signature corresponding to the validator's Ed25519 public key
    """
    target: bytes = field(metadata={'codec': H256})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

@dataclass
class Fault(Serializable):
    """
    GP-0.3.6-eq:97 (bold_f) | Proof of misbahaviour of one or more validators by signing a judgement found to be
    contradiction to a work-report's validity. This is considered an offence

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:97 (blackboard_H) |
        A work-report hash
    vote: Bool
        GP-0.3.6-eq:97 ({T/F}) |
        A vote
    key: H256
        GP-0.3.6-eq:97 (blackboard_H_E) |
        A validator Ed25519 public key
    signature: H512
        GP-0.3.6-eq:97 (blackboard_E) |
        A Ed25519 signature corresponding to the validator's Ed25519 public key

    """
    target: bytes = field(metadata={'codec': H256})
    vote: bool = field(metadata={'codec': Bool()})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

@dataclass
class Disputes(Serializable):
    """
    GP-0.3.6-eq:97 (bold_E_D) | judgements by validators on disputes

    Attributes
    ----------
    verdicts: Vec(verdict)
        GP-0.3.6-eq:97 (bold_v) |
        Compilations of judgements coming from exactly two-thirds plus one of either the active validator set or the
        previous epoch's validator set
    culprits: Vec(culprit)
        GP-0.3.6-eq:97 (bold_c) |
        Proofs of misbahaviour of one or more validators by guaranteeing a work-report found to be invalid. This is
        considered an offence
    faults: Vec(fault)
        GP-0.3.6-eq:97 (bold_f) |
        Proofs of misbahaviour of one or more validators by signing a judgement found to be contradiction to a
        work-report's validity. This is considered an offence
    """
    verdicts: List[Verdict] = field(metadata={'codec': Vec(Verdict.to_codec_def())})
    culprits: List[Culprit] = field(metadata={'codec': Vec(Culprit.to_codec_def())})
    faults: List[Fault] = field(metadata={'codec': Vec(Fault.to_codec_def())})

@dataclass
class Preimage(Serializable):
    """
    GP-0.3.6-eq:153 (bold_E_P) | Single item in the preimages extrinsic. A preimage is a pair of service indices and
    data

    Attributes
    ----------
    requester: U32
        GP-0.3.6-eq:153 (blackboard_N_S) |
        A service index
    blob: Bytes
        GP-0.3.6-eq:153 (blackboard_Y) |
        Arbitrary length data
    """
    requester: int = field(metadata={'codec': U32})
    blob: bytes = field(metadata={'codec': Bytes})

@dataclass
class Assurance(Serializable):
    """
    GP-0.3.6-eq:123 (bold_E_A) | Single item in the assurances extrinsic. Assurance by individual validator concerning
    which of the input data of workloads they have correctly received and are storing locally

    Attributes
    ----------
    anchor: H256
        GP-0.3.6-eq:123 (a) |
        Anchor to the parent_hash of the block
    bitfield: 1 Byte (incorrect for full-test-vectors)
        GP-0.3.6-eq:123 (f) |
        A sequence of binary values (bitstring) one per core.
    validator_index: U16
        GP-0.3.6-eq:123 (v) |
        A validator index
    signature: H512
        GP-0.3.6-eq:123 (s) |
        A Ed25519 signature corresponding to the validator index
    """
    anchor: bytes = field(metadata={'codec': H256})
    # Todo: check GP section 3.7.3 for boolean bitstring representation and check JAM-codec support
    bitfield: bytes = field(metadata={'codec': Array(U8, 1)})
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class WorkExecResult(Serializable):
    """
    GP-0.3.6-eq:121 (o) | Work result output or error of the execution of the code in the refine stage. Either a byte
    sequence in case it was successful or one of the possible errors

    Attributes
    ----------
    ok: Bytes
        GP-0.3.6-eq:121 (blackboard_Y) |
        The index of a service whose state is to be altered and thus whose refine code was already executed
    out_of_gas: None
        GP-0.3.6-eq:122 (sign_INFINITY) |
        Out of gas error
    panic: None
        GP-0.3.6-eq:121 (sign_LIGHTNING) |
        Panic error
    bad_code: None
        GP-0.3.6-eq:121 (BAD) |
        Bad code error
    code_oversize: None
        GP-0.3.6-eq:121 (BIG) |
        Code oversize error
    """
    ok: Bytes = field(default=None, metadata={'codec': Bytes})
    # TODO: find a way to parse null from JSON
    out_of_gas: Null = field(default=None, metadata={'codec': Null})
    panic: Null = field(default=None, metadata={'codec': Null})
    bad_code: Null = field(default=None, metadata={'codec': Null})
    code_oversize: Null = field(default=None, metadata={'codec': Null})

    _codec_type_def = Enum(
        ok=Bytes,
        out_of_gas=Null,
        panic=Null,
        bad_code=Null,
        code_oversize=Null
    )

    # def serialize(self) -> dict:
    #     if self.ok is not None:
    #         return {'ok': self.ok.serialize()}
    #     elif self.out_of_gas is not None:
    #         return {'out_of_gas': self.out_of_gas.serialize()}
    #     elif self.panic is not None:
    #         return {'panic': self.panic.serialize()}
    #     elif self.bad_code is not None:
    #         return {'bad_code': self.bad_code.serialize()}
    #     elif self.code_oversize is not None:
    #         return {'code_oversize': self.code_oversize.serialize()}


@dataclass
class WorkResult(Serializable):
    """
    GP-0.3.6-eq:121 (blackboard_L) | A work result is the data conduit by which services' states may be altered through
    the computation done within a work-package.

    Attributes
    ----------
    service: H256
        GP-0.3.6-eq:121 (s) |
        The index of a service whose state is to be altered and thus whose refine code was already executed
    code_hash: H256
        GP-0.3.6-eq:121 (c) |
        The hash of the code  of the service at the time of being reported
    payload_hash: H256
        GP-0.3.6-eq:121 (l) |
        The hash of the payload within the work item which was executed in the refine stage to give this result
    gas_ratio: U64
        GP-0.3.6-eq:121 (g) |
        The gas prioritization ration used when determining how much gas should be allocated to execute of this item's
        accumulate
    result: WorkExecResult
        GP-0.3.6-eq:121 (o) |
        Output or error of the execution of the code
    """
    service: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload_hash: bytes = field(metadata={'codec': H256})
    gas_ratio: int = field(metadata={'codec': U64})
    result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})


@dataclass
class RefinementContext(Serializable):
    """
    GP-0.3.6-eq:119 (blackboard_X) | A refinement context describes the context of the chain at the point that the
    report's corresponding work-package was evaluated.

    Attributes
    ----------
    anchor: H256
        GP-0.3.6-eq:119 (a) |
        The anchor header_hash
    state_root: H256
        GP-0.3.6-eq:119 (s) |
        The anchor header's block associated posterior state-root
    beefy_root: H256
        GP-0.3.6-eq:119 (b) |
        The anchor header's block associated posterior beefy-root
    lookup_anchor: H256
        GP-0.3.6-eq:119 (l) |
        The lookup-anchor header_hash
    lookup_anchor_slot: U32
        GP-0.3.6-eq:119 (t) |
        The lookup-anchor header's associated timeslot
    prerequisite: Option(H256)
        GP-0.3.6-eq:119 (p) |
        An optional prerequisite work-package
    """
    anchor: bytes = field(metadata={'codec': H256})
    state_root: bytes = field(metadata={'codec': H256})
    beefy_root: bytes = field(metadata={'codec': H256})
    lookup_anchor: bytes = field(metadata={'codec': H256})
    lookup_anchor_slot: int = field(metadata={'codec': U32})
    prerequisite: Optional[bytes] = field(metadata={'codec': Option(H256)})


@dataclass
class WorkPackageSpec(Serializable):
    """
    GP-0.3.6-eq:120 (blackboard_S) | Availability specification are used to ensure correct reconstruction  and auditing
    the purported ramifications of any reported work-package.

    Attributes
    ----------
    hash: H256
        GP-0.3.6-eq:120 (h) |
        The work-package hash
    len: U16
        GP-0.3.6-eq:120 (l) |
        The work bundle length
    root: H256
        GP-0.3.6-eq:120 (u) |
        The erasure-root
    segments: H256
        GP-0.3.6-eq:120 (e) |
        The segment root
    """
    hash: bytes = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U32})
    root: bytes = field(metadata={'codec': H256})
    segments: bytes = field(metadata={'codec': H256})


@dataclass
class WorkReport(Serializable):
    """
    GP-0.3.6-eq:117 (bold_E_G) | A work report comprises several work outputs

    Attributes
    ----------
    package_spec: WorkPackageSpec
        GP-0.3.6-eq:117 (s) |
        The work package specification
    context: RefinementContext
        GP-0.3.6-eq:117 (x) |
        The refinement context
    core_index: U16
        GP-0.3.6-eq:117 (c) |
        The core-index
    authorizer_hash: H256
        GP-0.3.6-eq:117 (a) |
        The authorizer hash
    auth_output: Bytes
        GP-0.3.6-eq:117 (o) |
        The output
    results: Vec(WorkResult)
        GP-0.3.6-eq:117 (r) |
        The results of the evaluation of each of the items inn the work package
    """
    package_spec: WorkPackageSpec = field(metadata={'codec': WorkPackageSpec.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    core_index: int = field(metadata={'codec': U16})
    authorizer_hash: bytes = field(metadata={'codec': H256})
    auth_output: bytes = field(metadata={'codec': Bytes})
    results: List[WorkResult] = field(metadata={'codec': Vec(WorkResult.to_codec_def())})


@dataclass
class Credential(Serializable):
    """
    GP-0.3.6-eq:136 | Single item in the signatures attribute of a guarantee comprising a validator index and its
    Ed25519 signature.

    Attributes
    ----------
    validator_index: U16
        GP-0.3.6-eq:136 (blackboard_N_V) |
        A validator index
    signature: H512
        GP-0.3.6-eq:136 (blackboard_E) |
        A Ed25519 signature corresponding to the validator index
    """
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class Guarantee(Serializable):
    """
    GP-0.3.6-eq:136 (bold_E_G) | Single item in the guarantees extrinsic. Report of newly completed workload whose
    accuracy is guaranteed by specific validators

    Attributes
    ----------
    report: WorkReport
        GP-0.3.6-eq:136 (w) |
        A work report
    slot: U32
        GP-0.3.6-eq:136 (t) |
        A timeslot
    signatures: Vec(Credential)
        GP-0.3.6-eq:136 (a) |
        a set of credentials
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    slot: int = field(metadata={'codec': U32})
    # Todo: consider renaming to 'credentials'
    signatures: List[Credential] = field(metadata={'codec': Vec(Credential.to_codec_def())})


@dataclass
class Header(Serializable):
    """
    GP-0.3.6-eq:37 (bold_H) | The header is a collection of metadata primarily concerned with cryptographic references
    to the blockchain ancestors and the operands and results of the present transition.

    Attributes
    ----------
    parent: H256
        GP-0.3.6-eq:38 (bold_H_p) |
        Hash of the header of the block's parent
    parent_state_root: H256
        GP-0.3.6-eq:42 (bold_H_r) |
        Merkle root of the block's parent posterior state
    extrinsic_hash: H256
        GP-0.3.6-eq:40 (bold_H_x) |
        Hash of the block's extrinsic data
    timeslot: U32
        GP-0.3.6-eq:41,45 (bold_H_t,blackboard_N=U32) |
        Block's timeslot
    epoch_marker: EpochMark
        GP-0.3.6-eq:44 (bold_H_e) |
        Optional block's epoch marker; fallback keys and entropy for next epoch
    tickets_marker: Option(Array(TicketBody,EPOCH_TIMESLOTS))
        GP-0.3.6-eq:44 (bold_H_w) |
        Optional block's winning tickets marker; provides a series of 600 slot sealing tickets for the next epoch
    offenders_marker: Vec(H256)
        GP-0.3.6-eq:44 (bold_H_o) |
        List of Ed25519 keys for offenders
    author_index: U16
        GP-0.3.6-eq:43 (bold_H_i) |
        Index to identify the block author into th posterior state of the current validator set (kappa)
    entropy_source: Array(U8, 96)
        GP-0.3.6-eq:61 (bold_H_v) |
        Entropy-yielding VRF signature
    seal: Array(U8, 96)
        GP-0.3.6-eq:59,60 (bold_H_s) |
        Seal signature
    """
    parent: bytes = field(metadata={'codec': H256})
    parent_state_root: bytes = field(metadata={'codec': H256})
    extrinsic_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})
    epoch_marker: Optional[EpochMark] = field(metadata={'codec': Option(EpochMark.to_codec_def())})
    tickets_marker: Optional[TicketsMark] = field(metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))})
    offenders_marker: List[bytes] = field(metadata={'codec': Vec(H256)})
    author_index: int = field(metadata={'codec': U16})
    entropy_source: bytes = field(metadata={'codec': Array(U8, 96)})
    seal: bytes = field(metadata={'codec': Array(U8, 96)})

    def generate_header_hash(self) -> bytes:
        return blake2b_256_hash(self.to_jam_bytes().to_bytes())

    # Todo: new function for derived author_key from validator set; GP-0.3.6-eq:43 (bold_H_a)
    # def generate_author_bandersnatch_key(self) -> bytes:
    #    pass

@dataclass
class Extrinsic(Serializable):
    """
    GP-0.3.6-eq:14 (bold_E) | Extrinsic data is input data external to the system.
    Extrinsic data is split into several discrete portions.

    Attributes
    ----------
    tickets: Vec(TicketEnvelope)
        GP-0.3.6-eq:73 (bold_E_T) |
        Manages selection of validators for permissioning of block authoring
    disputes: Disputes
        GP-0.3.6-eq:97 (bold_E_D) |
        Votes by validators on disputes
    preimages: Vec(Preimage)
        GP-0.3.6-eq:153 (bold_E_P) |
        Static data presently being requested to be available for workloads to be able to fetch on demand
    assurances: Vec(Assurance)
        GP-0.3.6-eq:123 (bold_E_A) |
        Assurances by each validator concerning which of the input data of workloads they have correctly received and are storing locally
    guarantees: Vec(Guarantee)
        GP-0.3.6-eq:136 (bold_E_G) |
        Reports of newly completed workloads whose accuracy is guaranteed by specific validators
    """
    tickets: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})
    disputes: Disputes = field(metadata={'codec': Disputes.to_codec_def()})
    preimages: List[Preimage] = field(metadata={'codec': Vec(Preimage.to_codec_def())})
    assurances: List[Assurance] = field(metadata={'codec': Vec(Assurance.to_codec_def())})
    guarantees: List[Guarantee] = field(metadata={'codec': Vec(Guarantee.to_codec_def())})

    # TODO TEMP unclear, move when Extrinsic is fully defined
    #work_report_hashes: Optional[List[bytes]] = field(metadata={'codec': Option(Vec(H256))})
    #accumulate_root: Optional[bytes] = field(metadata={'codec': Option(H256)})


@dataclass
class Block(Serializable):
    """
    GP-0.3.6-eq:13 (bold_b) | The header is a collection of metadata primarily concerned with cryptographic references to the blockchain
    ancestors and the operands and results of the present transition.

    Attributes
    ----------
    header: Header
        GP-0.3.6-eq:37 (bold_H) | Collection of metadata primarily concerned with cryptographic references to the
        blockchain ancestors and the operands and results of the present transition
    extrinsic: Extrinsic
        GP-0.3.6-eq:14 (bold_E) |
        Extrinsic data is input data external to the system
    """
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    extrinsic: Extrinsic = field(metadata={'codec': Extrinsic.to_codec_def()})
