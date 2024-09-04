from dataclasses import dataclass, field
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
    XXX

    Attributes
    ----------
    vote: Bool
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    index: U16
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signature: H512
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    vote: bool = field(metadata={'codec': Bool()})
    index: int = field(metadata={'codec': U16})
    signature: bytes =  field(metadata={'codec': H512})

@dataclass
class Verdict(Serializable):
    """
    XXX

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    age: U32
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    votes: Vec(fault)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    target: bytes = field(metadata={'codec': H256})
    age: int = field(metadata={'codec': U32})
    votes: List[Judgement] = field(metadata={'codec': Vec(Judgement.to_codec_def())})

@dataclass
class Culprit(Serializable):
    """
    XXX

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    key: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signature: H512
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    target: bytes = field(metadata={'codec': H256})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

@dataclass
class Fault(Serializable):
    """
    XXX

    Attributes
    ----------
    target: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    vote: Bool
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    key: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signature: H512
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    target: bytes = field(metadata={'codec': H256})
    vote: bool = field(metadata={'codec': Bool()})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

@dataclass
class Disputes(Serializable):
    """
    XXX

    Attributes
    ----------
    verdicts: Vec(verdict)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    culprits: Vec(culprit)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    faults: Vec(fault)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    verdicts: List[Verdict] = field(metadata={'codec': Vec(Verdict.to_codec_def())})
    culprits: List[Culprit] = field(metadata={'codec': Vec(Culprit.to_codec_def())})
    faults: List[Fault] = field(metadata={'codec': Vec(Fault.to_codec_def())})

@dataclass
class Preimage(Serializable):
    """
    XXX

    Attributes
    ----------
    requester: U32
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    blob: Bytes
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    requester: int = field(metadata={'codec': U32})
    blob: bytes = field(metadata={'codec': Bytes})

@dataclass
class Assurance(Serializable):
    """
    XXX

    Attributes
    ----------
    anchor: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    bitfield: 1 Byte
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    validator_index: U16
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signature: H512
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    anchor: bytes = field(metadata={'codec': H256})
    bitfield: bytes = field(metadata={'codec': Array(U8, 1)})
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class WorkExecResult(Serializable):
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
    XXX

    Attributes
    ----------
    service: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    code_hash: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    payload_hash: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    gas_ratio: U64
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    service: int = field(metadata={'codec': U32})
    code_hash: bytes = field(metadata={'codec': H256})
    payload_hash: bytes = field(metadata={'codec': H256})
    gas_ratio: int = field(metadata={'codec': U64})
    result: WorkExecResult = field(metadata={'codec': WorkExecResult.to_codec_def()})


@dataclass
class RefinementContext(Serializable):
    """
    XXX

    Attributes
    ----------
    anchor: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    state_root: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    beefy_root: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    lookup_anchor: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    lookup_anchor_slot: U32
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    prerequisite: Option(H256)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
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
    XXX

    Attributes
    ----------
    hash: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    len: U16
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    root: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    segments: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    hash: bytes = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U32})
    root: bytes = field(metadata={'codec': H256})
    segments: bytes = field(metadata={'codec': H256})


@dataclass
class WorkReport(Serializable):
    """
    XXX

    Attributes
    ----------
    package_spec: WorkPackageSpec
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    context: RefinementContext
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    core_index: U16
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    authorizer_hash: H256
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    auth_output: Bytes
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    results: Vec(WorkResult)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
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
    XXX

    Attributes
    ----------
    validator_index: U16
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signature: H512
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class Guarantee(Serializable):
    """
    XXX

    Attributes
    ----------
    report: WorkReport
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    slot: U32
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    signatures: Vec(Credential)
        GP-0.3.6-eq:XXX (XXX) |
        XXX
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    slot: int = field(metadata={'codec': U32})
    signatures: List[Credential] = field(metadata={'codec': Vec(Credential.to_codec_def())})


@dataclass
class Header(Serializable):
    """
    The header is a collection of metadata primarily concerned with cryptographic references to the blockchain
    ancestors and the operands and results of the present transition.

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


@dataclass
class Extrinsic(Serializable):
    """
    Extrinsic data is split into several portions. Extrinsic data is input data external to the system.

    Attributes
    ----------
    tickets: Vec(Ticket)
        GP-0.3.6-eq:14 (bold_E_t) |
        Manages selection of validators for permissioning of block authoring
    disputes: Disputes
        GP-0.3.6-eq:14 (bold_E_d) |
        Votes by validators on disputes
    preimages: Vec(Preimage)
        GP-0.3.6-eq:14 (bold_E_p) |
        Static data presently being requested to be available for workloads to be able to fetch on demand
    assurances: Vec(Assurance)
        GP-0.3.6-eq:14 (bold_E_a) |
        Assurances by each validator concerning which of the input data of workloads they have correctly received and are storing locally
    guarantees: Vec(Guarantee)
        GP-0.3.6-eq:14 (bold_E_g) |
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
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    extrinsic: Extrinsic = field(metadata={'codec': Extrinsic.to_codec_def()})
