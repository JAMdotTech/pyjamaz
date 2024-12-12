from dataclasses import dataclass, field
from functools import cached_property

from bandersnatch_vrfs import ietf_vrf_verify
from math import floor
from typing import List, Optional

from jamcodec.types import H256, U32, Option, Vec, Array, U8, U16, Bool, H512, Bytes, U64, BitArray
from pyjamaz.graypaper_constants import VALIDATOR_COUNT, EPOCH_TIMESLOTS, CORE_COUNT
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import RefinementContext, WorkReport
from pyjamaz.signing import Ed25519Keypair

from jamcodec.mixins import Serializable


# TODO: move and annotate Marker DataClasses
@dataclass
# Todo: (Re)move, annotate, reference-GP
class TicketBody(Serializable):
    id: bytes = field(metadata={'codec': H256})
    attempt: int = field(metadata={'codec': U8})


@dataclass
# Todo: (Re)move, annotate, reference-GP GP-0.5.0-eq:5.10
class EpochMark(Serializable):
    entropy: bytes = field(metadata={'codec': H256})
    tickets_entropy: bytes = field(metadata={'codec': H256})
    validators: List[bytes] = field(metadata={'codec': Array(H256, VALIDATOR_COUNT)})


@dataclass
class TicketEnvelope(Serializable):
    """
    GP-0.5.0-eq:6.29 (bold_E_T) | Single item in the tickets extrinsic. Manages selection of validators for
    permissioning of block authoring

    Attributes
    ----------
    attempt: U16
        GP-0.5.0-eq:6.29 (r) | An entry index
    signature: Array(U8,784)
        GP-0.5.0-eq:6.29 (p) | Proof of a ticket's validity
    """
    attempt: int = field(metadata={'codec': U8})
    signature: bytes = field(metadata={'codec': Array(U8, 784)})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")

    def generate_vrf_input(self, entropy: bytes) -> bytes:
        """
        GP-0.5.0-eq:6.31

        Parameters
        ----------
        entropy

        Returns
        -------
        bytes
        """
        #
        vrf_input_data = b"jam_ticket_seal"  # GP-0.5.0-eq:6.20
        vrf_input_data += entropy
        vrf_input_data += int.to_bytes(self.attempt, byteorder='little', length=1)

        return vrf_input_data


# Todo: (Re)move, annotate, reference-GP
TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
# Todo: (Re)move, annotate, reference-GP
class OutputMarks(Serializable):
    # New epoch signal. OPTIONAL
    epoch_mark: Optional[EpochMark] = field(
        default=None,
        metadata={'codec': Option(EpochMark.to_codec_def())}
    )   # New epoch signal. OPTIONAL
    # Tickets signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(
        default=None,
        metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )  # Tickets signal. OPTIONAL
    offenders_mark: List[bytes] = field(
        default_factory=list,
        metadata={'codec': Vec(H256)}
    )


@dataclass
class Judgement(Serializable):
    """
    GP-0.5.0-eq:10.2 (third element of the tuple in bold_v) | An individual judgements coming from a validator

    Attributes
    ----------
    vote: Bool
        GP-0.5.0-eq:10.2 ({T/F}) | A vote
    index: U16
        GP-0.5.0-eq:10.2 (blackboard_N_V) | A validator index
    signature: H512
        GP-0.5.0-eq:10.2 (blackboard_E) | A Ed25519 signature corresponding to the validator index
    """
    vote: bool = field(metadata={'codec': Bool()})
    index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})

    def get_signing_context(self) -> bytes:
        """
        GP-0.5.0-eq:10.4

        Returns
        -------
        bytes
        """
        return b'jam_valid' if self.vote else b'jam_invalid'


@dataclass
class Verdict(Serializable):
    """
    GP-0.5.0-eq:10.2 (bold_v) | A compilation of judgements coming from exactly two-thirds plus one of either the active
    validator set or the previous epoch's validator set

    Attributes
    ----------
    target: H256
        GP-0.5.0-eq:10.2 (blackboard_H in bold_v) | A work-report hash
    age: U32
        GP-0.5.0-eq:10.2 (second element of the tuple in bold_v) | Determines whether the current or the previous
        validator set applies to this verdict
    votes: Vec(fault)
        GP-0.5.0-eq:10.2 (third element of the tuple in bold_v) | A set of judgements by two-thirds plus one of either
        the current or the previous validator set
    """
    target: bytes = field(metadata={'codec': H256})
    age: int = field(metadata={'codec': U32})
    # Todo: change array size to use constants: 1+(floor(VALIDATOR_COUNT/3)*2)
    votes: List[Judgement] = field(metadata={'codec': Array(Judgement.to_codec_def(), 1+(floor(VALIDATOR_COUNT/3)*2))})

    @cached_property
    def total_positive_votes(self) -> int:
        """
        GP-0.5.0-eq:10.12

        Parameters
        ----------

        Returns
        -------
        int
        """
        return sum([v.vote for v in self.votes])

    def is_good(self) -> bool:
        return self.total_positive_votes == VALIDATOR_COUNT * 2 / 3 + 1

    def is_bad(self) -> bool:
        return self.total_positive_votes == 0

    def is_wonky(self) -> bool:
        return self.total_positive_votes == VALIDATOR_COUNT / 3


@dataclass
class Culprit(Serializable):
    """
    GP-0.5.0-eq:10.2 (bold_c) | Proof of misbehaviour of one or more validators by guaranteeing a work-report found to
    be invalid. This is considered an offence.

    Attributes
    ----------
    target: H256
        GP-0.5.0-eq:10.2 (blackboard_H) | A work-report hash
    key: H256
        GP-0.5.0-eq:10.2 (blackboard_H_E) | A validator Ed25519 public key
    signature: H512
        GP-0.5.0-eq:10.2 (blackboard_E) | A Ed25519 signature corresponding to the validator's Ed25519 public key
    """
    target: bytes = field(metadata={'codec': H256})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

    def has_valid_signature(self) -> bool:
        keypair = Ed25519Keypair.from_public_key(self.key)
        return keypair.verify(b'jam_guarantee' + self.target, self.signature)


@dataclass
class Fault(Serializable):
    """
    GP-0.5.0-eq:10.2 (bold_f) | Proof of misbehaviour of one or more validators by signing a judgement found to be
    contradiction to a work-report's validity. This is considered an offence.

    Attributes
    ----------
    target: H256
        GP-0.5.0-eq:10.2 (blackboard_H) | A work-report hash
    vote: Bool
        GP-0.5.0-eq:10.2 ({T/F}) | A vote
    key: H256
        GP-0.5.0-eq:10.2 (blackboard_H_E) | A validator Ed25519 public key
    signature: H512
        GP-0.5.0-eq:10.2 (blackboard_E) | A Ed25519 signature corresponding to the validator's Ed25519 public key

    """
    target: bytes = field(metadata={'codec': H256})
    vote: bool = field(metadata={'codec': Bool()})
    key: bytes = field(metadata={'codec': H256})
    signature: bytes = field(metadata={'codec': H512})

    def has_valid_signature(self) -> bool:
        keypair = Ed25519Keypair.from_public_key(self.key)
        return keypair.verify(b'jam_valid' if self.vote else b'jam_invalid' + self.target, self.signature)


@dataclass
class ExtrinsicDisputes(Serializable):
    """
    GP-0.5.0-eq:10.2 (bold_E_D) | judgements by validators on disputes.

    Attributes
    ----------
    verdicts: Vec(verdict)
        GP-0.5.0-eq:10.2 (bold_v) | Compilations of judgements coming from exactly two-thirds plus one of either the
        active validator set or the previous epoch's validator set.
    culprits: Vec(culprit)
        GP-0.5.0-eq:10.2 (bold_c) | Proofs of misbehaviour of one or more validators by guaranteeing a work-report
        found to be invalid. This is considered an offence.
    faults: Vec(fault)
        GP-0.5.0-eq:10.2 (bold_f) | Proofs of misbehaviour of one or more validators by signing a judgement found to be
        contradiction to a work-report's validity. This is considered an offence.
    """
    verdicts: List[Verdict] = field(metadata={'codec': Vec(Verdict.to_codec_def())})
    culprits: List[Culprit] = field(metadata={'codec': Vec(Culprit.to_codec_def())})
    faults: List[Fault] = field(metadata={'codec': Vec(Fault.to_codec_def())})


@dataclass
class Preimage(Serializable):
    """
    GP-0.5.0-eq:12.28 (bold_E_P) | Single item in the preimages extrinsic. A preimage is a pair of service indices and
    data.

    Attributes
    ----------
    requester: U32
        GP-0.5.0-eq:12.28 (blackboard_N_S) | A service index.
    blob: Bytes
        GP-0.5.0-eq:12.28 (blackboard_Y) | Arbitrary length data.
    """
    requester: int = field(metadata={'codec': U32})
    blob: bytes = field(metadata={'codec': Bytes})


@dataclass
class Assurance(Serializable):
    """
    GP-0.5.0-eq:11.8 (bold_E_A) | Single item in the assurances extrinsic. Assurance by individual validator concerning
    which of the input data of workloads they have correctly received and are storing locally.

    Attributes
    ----------
    anchor: H256
        GP-0.5.0-eq:11.8 (a) | Anchor to the parent_hash of the block.
    bitfield: BitArray(constant_C)
        GP-0.5.0-eq:11.8 (f) | A sequence of binary values (bitstring) one per core.
    validator_index: U16
        GP-0.5.0-eq:11.8 (v) | A validator index.
    signature: H512
        GP-0.5.0-eq:11.8 (s) | A Ed25519 signature corresponding to the validator index.
    """
    anchor: bytes = field(metadata={'codec': H256})
    bitfield: List[bool] = field(metadata={'codec': BitArray(CORE_COUNT)})
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class Credential(Serializable):
    """
    GP-0.5.0-eq:11.22 (a) | Single item in the signatures attribute of a guarantee comprising a validator index and its
    Ed25519 signature.

    Attributes
    ----------
    validator_index: U16
        GP-0.5.0-eq:11.22 (blackboard_N_V) | A validator index.
    signature: H512
        GP-0.5.0-eq:11.22 (blackboard_E) | A Ed25519 signature corresponding to the validator index.
    """
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class Guarantee(Serializable):
    """
    GP-0.5.0-eq:11.22 (bold_E_G) | Single item in the guarantees extrinsic. Report of newly completed workload whose
    accuracy is guaranteed by specific validators.

    Attributes
    ----------
    report: pyjamaz.models.common.WorkReport
        GP-0.5.0-eq:11.22 (w) | A work report.
    slot: U32
        GP-0.5.0-eq:11.22 (t) | A timeslot.
    signatures: Vec(Credential)
        GP-0.5.0-eq:11.22 (a) | A set of credentials.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    slot: int = field(metadata={'codec': U32})
    # Todo: consider renaming to 'credentials'
    signatures: List[Credential] = field(metadata={'codec': Vec(Credential.to_codec_def())})


@dataclass
class Header(Serializable):
    """
    GP-0.5.0-eq:5.1 (bold_H) | The header is a collection of metadata primarily concerned with cryptographic references
    to the blockchain ancestors and the operands and results of the present transition.

    Attributes
    ----------
    parent: H256
        GP-0.5.0-eq:5.2 (bold_H_p) |
        Hash of the header of the block's parent
    parent_state_root: H256
        GP-0.5.0-eq:5.8 (bold_H_r) |
        Merkle root of the block's parent posterior state
    extrinsic_hash: H256
        GP-0.5.0-eq:5.4 (bold_H_x) |
        Hash of the block's extrinsic data
    timeslot: U32
        GP-0.5.0-eq:5.7,6.1 (bold_H_t,blackboard_N=U32) |
        Block's timeslot
    epoch_marker: EpochMark
        GP-0.5.0-eq:5.10 (bold_H_e) |
        Optional block's epoch marker; fallback keys and entropy for next epoch
    tickets_marker: Option(Array(TicketBody,EPOCH_TIMESLOTS))
        GP-0.5.0-eq:5.10 (bold_H_w) |
        Optional block's winning tickets marker; provides a series of 600 slot sealing tickets for the next epoch
    offenders_marker: Vec(H256)
        GP-0.5.0-eq:5.10 (bold_H_o) |
        List of Ed25519 keys for offenders
    author_index: U16
        GP-0.5.0-eq:5.9 (bold_H_i) |
        Index to identify the block author into the posterior state of the current validator set (kappa)
    entropy_source: Array(U8, 96)
        GP-0.5.0-eq:6.17 (bold_H_v) |
        Entropy-yielding VRF signature
    seal: Array(U8, 96)
        GP-0.5.0-eq:6.15,6.16 (bold_H_s) |
        Seal signature
    """
    parent: bytes = field(metadata={'codec': H256})
    parent_state_root: bytes = field(metadata={'codec': H256})
    extrinsic_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})
    epoch_marker: Optional[EpochMark] = field(metadata={'codec': Option(EpochMark.to_codec_def())})
    tickets_marker: Optional[TicketsMark] = field(
        metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )
    offenders_marker: List[bytes] = field(metadata={'codec': Vec(H256)})
    author_index: int = field(metadata={'codec': U16})
    entropy_source: bytes = field(metadata={'codec': Array(U8, 96)})
    seal: bytes = field(metadata={'codec': Array(U8, 96)})

    # TODO recent-history seems to need this, how to handle with this
    # hash: bytes = field(default=None, metadata={'codec': H256})

    @property
    def hash(self) -> bytes:
        """
        Generates a hash of the header. GP-0.5.0-eq:5.2 E_U(H)

        Returns
        -------
        bytes
        """
        if getattr(self, '_hash', None) is not None:
            return getattr(self, '_hash')

        return blake2b_256_hash(self.to_jam_bytes().to_bytes())

    def get_unsigned_payload(self) -> bytes:
        """
        Payload to create seal signature GP-0.5.0-eq:6.15,6.16 E_U(H)

        Returns
        -------
        bytes
        """
        return self.to_jam_bytes().to_bytes()[:-96]

    @hash.setter
    def hash(self, value: bytes) -> None:
        setattr(self, '_hash', value)

    def verify_ticket_seal(self, bandersnatch_key: bytes, ticket_body: TicketBody, entropy: bytes) -> bytes:
        vrf_output = ietf_vrf_verify(
            bytes(bandersnatch_key),
            b"jam_ticket_seal" + entropy + int.to_bytes(ticket_body.attempt, byteorder='little', length=1),
            self.get_unsigned_payload(),
            bytes(self.seal)
        )

        return ticket_body.id == vrf_output

    def verify_fallback_seal(self, sealer_key: bytes, entropy: bytes) -> bytes:
        return ietf_vrf_verify(
            bytes(sealer_key),
            b"jam_fallback_seal" + entropy,
            self.get_unsigned_payload(),
            bytes(self.seal)
        )

    @classmethod
    def default(cls) -> 'Header':
        return Header(
                parent=bytes(32),
                parent_state_root=bytes(32),
                extrinsic_hash=bytes(32),
                timeslot=0,
                epoch_marker=None,
                tickets_marker=None,
                offenders_marker=[],
                author_index=0,
                entropy_source=bytes(96),
                seal=bytes(96)
            )

    # Todo: new function for derived author_key from validator set; GP-0.5.0-eq:5.9 (bold_H_a)
    # def generate_author_bandersnatch_key(self) -> bytes:
    #    pass


@dataclass
class Extrinsic(Serializable):
    """
    GP-0.5.0-eq:4.3 (bold_E) | Extrinsic data is input data external to the system.
    Extrinsic data is split into several discrete portions.

    Attributes
    ----------
    tickets: Vec(TicketEnvelope)
        GP-0.5.0-eq:6.29 (bold_E_T) |
        Manages selection of validators for permissioning of block authoring
    preimages: Vec(Preimage)
        GP-0.5.0-eq:12.28 (bold_E_P) |
        Static data presently being requested to be available for workloads to be able to fetch on demand
    guarantees: Vec(Guarantee)
        GP-0.5.0-eq:11.22 (bold_E_G) |
        Reports of newly completed workloads whose accuracy is guaranteed by specific validators
    assurances: Vec(Assurance)
        GP-0.5.0-eq:11.8 (bold_E_A) |
        Assurances by each validator concerning which of the input data of workloads they have correctly received and
        are storing locally
    disputes: ExtrinsicDisputes
        GP-0.5.0-eq:10.2 (bold_E_D) |
        Votes by validators on disputes
    """
    tickets: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})
    preimages: List[Preimage] = field(metadata={'codec': Vec(Preimage.to_codec_def())})
    guarantees: List[Guarantee] = field(metadata={'codec': Vec(Guarantee.to_codec_def())})
    assurances: List[Assurance] = field(metadata={'codec': Vec(Assurance.to_codec_def())})
    disputes: ExtrinsicDisputes = field(metadata={'codec': ExtrinsicDisputes.to_codec_def()})

    # TODO TEMP unclear, move when Extrinsic is fully defined
    # work_report_hashes: Optional[List[bytes]] = field(metadata={'codec': Option(Vec(H256))})
    # accumulate_root: Optional[bytes] = field(metadata={'codec': Option(H256)})

    def generate_extrinsic_hash(self) -> bytes:
        """
        GP-0.5.0-eq:5.4

        Returns
        -------
        bytes
        """
        return blake2b_256_hash(self.to_jam_bytes().to_bytes())


@dataclass
class Block(Serializable):
    """
    GP-0.5.0-eq:4.2 (bold_B) | The header is a collection of metadata primarily concerned with cryptographic references
    to the blockchain ancestors and the operands and results of the present transition.

    Attributes
    ----------
    header: Header
        GP-0.5.0-eq:4.3 (bold_H) | Collection of metadata primarily concerned with cryptographic references to the
        blockchain ancestors and the operands and results of the present transition
    extrinsic: Extrinsic
        GP-0.5.0-eq:4.3 (bold_E) |
        Extrinsic data is input data external to the system
    """
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    extrinsic: Extrinsic = field(metadata={'codec': Extrinsic.to_codec_def()})


@dataclass
class WorkItemExtrinsic(Serializable):
    """
    GP-0.5.0-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.

    Attributes
    ----------
    hash: H256
        GP-0.5.0-eq:14.3 (blackboard_H) | Blob hashes.
    len: U32
        GP-0.5.0-eq:14.3 (blackboard_N type derived from encoding appendix) | A validator index.
    """
    hash: bytes = field(metadata={'codec': H256})
    len: int = field(metadata={'codec': U32})


@dataclass
class ImportSegment(Serializable):
    """
    GP-0.3.8-eq:175 (i) | Imported data segments consisting of the root of the segment tree and the index into it.

    Attributes
    ----------
    tree_root: H256
        GP-0.5.0-eq:14.3 (blackboard_H) | Root of the segment tree.
    index: U16
        GP-0.5.0-eq:14.3 (blackboard_N type derived from encoding appendix) | Index into the segment tree.
    """
    tree_root: bytes = field(metadata={'codec': H256})
    index: int = field(metadata={'codec': U16})


@dataclass
class WorkItem(Serializable):
    """
    GP-0.5.0-eq:14.3 (blackboard_I) | Work item.

    Attributes
    ----------
    service: U32
        GP-0.5.2-eq:14.3 (s) | The index of a service to which it relates.
    code_hash: H256
        GP-0.5.2-eq:14.3 (c) | The hash of the code  of the service at the time of being reported.
    payload: Bytes
        GP-0.5.2-eq:14.3 (bold_y) | A payload blob.
    refine_gas_limit: U64
        GP-0.5.2-eq:14.3 (g) | The gas limit.
    accumulate_gas_limit: U64
        GP-0.5.2-eq:14.3 (a) | The gas limit.
    import_segments: Vec(ImportSegment)
        GP-0.5.2-eq:14.3 (bold_i) | Imported data segments.
    extrinsic: Vec(WorkItemExtrinsic)
        GP-0.5.2-eq:14.3 (bold_x) | A sequence of blob hashes and lengths.
    export_count: U16
        GP-0.5.2-eq:14.3 (e) | The number of data segments exported by this work item.
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
    GP-0.5.0-eq:14.2 (u & bold_p) | A tuple of the authorization code hash and the parameterization blob.

    Attributes
    ----------
    code_hash: H256
        GP-0.5.0-eq:14.2 (u) | The authorization code hash.
    params: Bytes
        GP-0.5.0-eq:14.2 (bold_p) | A parameterization blob.
    """
    code_hash: bytes = field(metadata={'codec': H256})
    params: bytes = field(metadata={'codec': Bytes})


@dataclass
class WorkPackage(Serializable):
    """
    GP-0.5.0-eq:14.2 (blackboard_P) | Work package.

    Attributes
    ----------
    authorization: Bytes
        GP-0.5.0-eq:14.2 (bold_j) | Authorization token blob.
    auth_code_host: U32
        GP-0.5.0-eq:14.2 (h) | Index of the service which hosts the authorization code.
    # TODO: deviation from GP-0.5.0-eq:14.2 in which u & bold_p are separated.
    # TODO: This impacts the structure of JSON (not JAM-codec).
    authorizer: Authorizer
        GP-0.5.0-eq:14.2 (u & bold_p) | A tuple of the authorization code hash and the parameterization blob.
    context: pyjamaz.models.common.RefinementContext
        GP-0.5.0-eq:14.2 (bold_x) | The refinement context.
    items: Vec(WorkItem)
        GP-0.5.0-eq:14.2 (bold_w) | A sequence of work items.
    """
    authorization: bytes = field(metadata={'codec': Bytes})
    auth_code_host: int = field(metadata={'codec': U32})
    # TODO: deviation from GP-0.5.0-eq:14.2 in which u & bold_p are separated.
    # TODO: This impacts the structure of JSON (not JAM-codec).
    authorizer: Authorizer = field(metadata={'codec': Authorizer.to_codec_def()})
    context: RefinementContext = field(metadata={'codec': RefinementContext.to_codec_def()})
    items: List[WorkItem] = field(metadata={'codec': Vec(WorkItem.to_codec_def())})
