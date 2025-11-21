from dataclasses import dataclass, field
from functools import cached_property

from bandersnatch_vrfs import ietf_vrf_verify, ietf_vrf_sign
from math import floor
from typing import List, Optional, TYPE_CHECKING

from pyjamaz.exceptions import BlockValidationError

from jamcodec.types import H256, U32, Option, Vec, Array, U8, U16, Bool, H512, Bytes, BitArray, Tuple
from pyjamaz.graypaper_constants import VALIDATOR_COUNT, EPOCH_TIMESLOTS, CORE_COUNT
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import WorkReport, TicketBody, ValidatorData
from pyjamaz.signing import Ed25519Keypair

from jamcodec.mixins import Serializable
from pyjamaz.utils import vrf_input_ticket_seal, vrf_input_fallback_seal

if TYPE_CHECKING:
    from pyjamaz.models.state import ValidatorPoolState


@dataclass
class EpochMarkValidatorKeys(Serializable):
    bandersnatch: bytes = field(metadata={'codec': H256})
    ed25519: bytes = field(metadata={'codec': H256})


@dataclass
# Todo: (Re)move, annotate, reference-GP GP-0.7.1-eq:5.10
class EpochMark(Serializable):
    entropy: bytes = field(metadata={'codec': H256})
    tickets_entropy: bytes = field(metadata={'codec': H256})
    validators: List[EpochMarkValidatorKeys] = field(metadata={
        'codec': Array(EpochMarkValidatorKeys.to_codec_def(), VALIDATOR_COUNT)
    })


@dataclass
class TicketEnvelope(Serializable):
    """
    GP-0.7.1-eq:6.29 (bold_E_T) | Single item in the tickets extrinsic. Manages selection of validators for
    permissioning of block authoring

    Attributes
    ----------
    attempt: U8
        GP-0.7.1-eq:6.29 (e) | An entry index
    signature: Array(U8,784)
        GP-0.7.1-eq:6.29 (p) | Proof of a ticket's validity
    """
    attempt: int = field(metadata={'codec': U8})
    signature: bytes = field(metadata={'codec': Array(U8, 784)})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise BlockValidationError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise BlockValidationError("Signature must be a bytes object of length 784")

    def generate_vrf_input(self, entropy: bytes) -> bytes:
        """
        GP-0.7.1-eq:6.31

        Parameters
        ----------
        entropy

        Returns
        -------
        bytes
        """

        return vrf_input_ticket_seal(entropy, self.attempt)


@dataclass
class Judgement(Serializable):
    """
    GP-0.7.1-eq:10.2 (third element of the tuple in bold_E_V) | An individual judgements coming from a validator

    Attributes
    ----------
    vote: Bool
        GP-0.7.1-eq:10.2 ({T/F}) | A vote
    index: U16
        GP-0.7.1-eq:10.2 (blackboard_N_V) | A validator index
    signature: H512
        GP-0.7.1-eq:10.2 (blackboard_V_-) | A valid Ed25519 signature corresponding to the validator index
    """
    vote: bool = field(metadata={'codec': Bool()})
    index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})

    def get_signing_context(self) -> bytes:
        """
        GP-0.7.1-eq:10.4

        Returns
        -------
        bytes
        """
        return b'jam_valid' if self.vote else b'jam_invalid'


@dataclass
class Verdict(Serializable):
    """
    GP-0.7.1-eq:10.2 (bold_E_V) | A compilation of judgements coming from exactly two-thirds plus one of either the
    active validator set or the previous epoch's validator set

    Attributes
    ----------
    target: H256
        GP-0.7.1-eq:10.2 (blackboard_H in bold_E_V) | A work-report hash
    age: U32
        GP-0.7.1-eq:10.2 (second element of the tuple in bold_E_V) | Determines whether the current or the previous
        validator set applies to this verdict
    votes: Vec(fault)
        GP-0.7.1-eq:10.2 (third element of the tuple in bold_E_V) | A set of judgements by two-thirds plus one of
        either the current or the previous validator set
    """
    target: bytes = field(metadata={'codec': H256})
    age: int = field(metadata={'codec': U32})
    # Todo: change array size to use constants: 1+(floor(VALIDATOR_COUNT/3)*2)
    votes: List[Judgement] = field(metadata={'codec': Array(Judgement.to_codec_def(), 1+(floor(VALIDATOR_COUNT/3)*2))})

    @cached_property
    def total_positive_votes(self) -> int:
        """
        GP-0.7.1-eq:10.12

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
    GP-0.7.1-eq:10.2 (bold_E_C) | Proof of misbehaviour of one or more validators by guaranteeing a work-report found
    to be invalid. This is considered an offence.

    Attributes
    ----------
    target: H256
        GP-0.7.1-eq:10.2 (blackboard_H) | A work-report hash
    key: H256
        GP-0.7.1-eq:10.2 (blackboard_H_-) | A validator Ed25519 public key
    signature: H512
        GP-0.7.1-eq:10.2 (blackboard_V_-) | A valid Ed25519 signature corresponding to the validator's Ed25519 public
        key
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
    GP-0.7.1-eq:10.2 (bold_E_F) | Proof of misbehaviour of one or more validators by signing a judgement found to be
    contradiction to a work-report's validity. This is considered an offence.

    Attributes
    ----------
    target: H256
        GP-0.7.1-eq:10.2 (blackboard_H) | A work-report hash
    vote: Bool
        GP-0.7.1-eq:10.2 ({T/F}) | A vote
    key: H256
        GP-0.7.1-eq:10.2 (blackboard_H_-) | A validator Ed25519 public key
    signature: H512
        GP-0.7.1-eq:10.2 (blackboard_V_-) | A valid Ed25519 signature corresponding to the validator's Ed25519 public
        key
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
    GP-0.7.1-eq:10.2 (bold_E_D) | judgements by validators on disputes.

    Attributes
    ----------
    verdicts: Vec(verdict)
        GP-0.7.1-eq:10.2 (bold_E_V) | Compilations of judgements coming from exactly two-thirds plus one of either the
        active validator set or the previous epoch's validator set.
    culprits: Vec(culprit)
        GP-0.7.1-eq:10.2 (bold_E_C) | Proofs of misbehaviour of one or more validators by guaranteeing a work-report
        found to be invalid. This is considered an offence.
    faults: Vec(fault)
        GP-0.7.1-eq:10.2 (bold_E_F) | Proofs of misbehaviour of one or more validators by signing a judgement found to
        be contradiction to a work-report's validity. This is considered an offence.
    """
    verdicts: List[Verdict] = field(metadata={'codec': Vec(Verdict.to_codec_def())})
    culprits: List[Culprit] = field(metadata={'codec': Vec(Culprit.to_codec_def())})
    faults: List[Fault] = field(metadata={'codec': Vec(Fault.to_codec_def())})


@dataclass
class Preimage(Serializable):
    """
    GP-0.7.1-eq:12.33 (bold_E_P) | Single item in the preimages extrinsic. A preimage is a pair of service indices and
    data.

    Attributes
    ----------
    requester: U32
        GP-0.7.1-eq:12.33 (blackboard_N_S) | A service index.
    blob: Bytes
        GP-0.7.1-eq:12.33 (blackboard_B) | Arbitrary length data.
    """
    requester: int = field(metadata={'codec': U32})
    blob: bytes = field(metadata={'codec': Bytes})

    def hash(self):
        return blake2b_256_hash(self.blob)

    def length(self):
        return len(self.blob)

    def sort_key(self):
        return int(self.requester).to_bytes(4, byteorder="big") + self.blob


@dataclass
class Assurance(Serializable):
    """
    GP-0.7.1-eq:11.10 (bold_E_A) | Single item in the assurances extrinsic. Assurance by individual validator concerning
    which of the input data of workloads they have correctly received and are storing locally.

    Attributes
    ----------
    anchor: H256
        GP-0.7.1-eq:11.10 (a) | Anchor to the parent_hash of the block.
    bitfield: BitArray(constant_C)
        GP-0.7.1-eq:11.10 (f) | A sequence of binary values (bitstring) one per core.
    validator_index: U16
        GP-0.7.1-eq:11.10 (v) | A validator index.
    signature: H512
        GP-0.7.1-eq:11.10 (s) | A Ed25519 signature corresponding to the validator index.
    """
    anchor: bytes = field(metadata={'codec': H256})
    bitfield: List[bool] = field(metadata={'codec': BitArray(CORE_COUNT)})
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})

    @property
    def bitfield_bytes(self) -> bytes:
        return BitArray(CORE_COUNT).encode(self.bitfield).to_bytes()

    @property
    def cores_engaged(self) -> list:
        return [c for c, e in enumerate(self.bitfield) if e == True]


@dataclass
class Credential(Serializable):
    """
    GP-0.7.1-eq:11.22 (a) | Single item in the signatures attribute of a guarantee comprising a validator index and its
    Ed25519 signature.

    Attributes
    ----------
    validator_index: U16
        GP-0.7.1-eq:11.22 (blackboard_N_V) | A validator index.
    signature: H512
        GP-0.7.1-eq:11.22 (blackboard_V_-) | A valid Ed25519 signature corresponding to the validator index.
    """
    validator_index: int = field(metadata={'codec': U16})
    signature: bytes = field(metadata={'codec': H512})


@dataclass
class Guarantee(Serializable):
    """
    GP-0.7.1-eq:11.23 (bold_E_G) | Single item in the guarantees extrinsic. Report of newly completed workload whose
    accuracy is guaranteed by specific validators.

    Attributes
    ----------
    report: pyjamaz.models.common.WorkReport
        GP-0.7.1-eq:11.23 (bold_r) | A work report.
    slot: U32
        GP-0.7.1-eq:11.23 (t) | A timeslot.
    signatures: Vec(Credential)
        GP-0.7.1-eq:11.23 (a) | A set of credentials.
    """
    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    slot: int = field(metadata={'codec': U32})
    # Todo: consider renaming to 'credentials'
    signatures: List[Credential] = field(metadata={'codec': Vec(Credential.to_codec_def())})


@dataclass
class Header(Serializable):
    """
    GP-0.7.1-eq:5.1 (bold_H) | The header is a collection of metadata primarily concerned with cryptographic references
    to the blockchain ancestors and the operands and results of the present transition.

    Serialization: GP-0.7.1-eq:C.22,23

    Attributes
    ----------
    parent: H256
        GP-0.7.1-eq:5.2 (bold_H_P) |
        Hash of the header of the block's parent
    parent_state_root: H256
        GP-0.7.1-eq:5.8 (bold_H_R) |
        Merkle root of the block's parent posterior state
    extrinsic_hash: H256
        GP-0.7.1-eq:5.4 (bold_H_X) |
        Hash of the block's extrinsic data
    timeslot: U32
        GP-0.7.1-eq:5.7,6.1 (bold_H_T,blackboard_N=U32) |
        Block's timeslot
    epoch_marker: EpochMark
        GP-0.7.1-eq:5.10 (bold_H_E) |
        Optional block's epoch marker; fallback keys and entropy for next epoch
    tickets_marker: Option(Array(TicketBody,EPOCH_TIMESLOTS))
        GP-0.7.1-eq:5.10 (bold_H_W) |
        Optional block's winning tickets marker; provides a series of 600 slot sealing tickets for the next epoch
    author_index: U16
        GP-0.7.1-eq:5.9 (bold_H_I) |
        Index to identify the block author into the posterior state of the current validator set (kappa)
    entropy_source: Array(U8, 96)
        GP-0.7.1-eq:6.17 (bold_H_V) |
        Entropy-yielding VRF signature
    offenders_marker: Vec(H256)
        GP-0.7.1-eq:5.10 (bold_H_O) |
        List of Ed25519 keys for offenders
    seal: Array(U8, 96)
        GP-0.7.1-eq:6.15,6.16 (bold_H_S) |
        Seal signature
    """
    parent: bytes = field(metadata={'codec': H256})
    parent_state_root: bytes = field(metadata={'codec': H256})
    extrinsic_hash: bytes = field(metadata={'codec': H256})
    timeslot: int = field(metadata={'codec': U32})
    epoch_marker: Optional[EpochMark] = field(metadata={'codec': Option(EpochMark.to_codec_def())})
    tickets_marker: Optional[List[TicketBody]] = field(
        metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )
    author_index: int = field(metadata={'codec': U16})
    entropy_source: bytes = field(metadata={'codec': Array(U8, 96)})
    offenders_marker: List[bytes] = field(metadata={'codec': Vec(H256)})
    seal: bytes = field(metadata={'codec': Array(U8, 96)})

    @property
    def hash(self) -> bytes:
        """
        Generates a hash of the header. GP-0.7.1-eq:5.2 E_U(H)

        Returns
        -------
        bytes
        """
        if getattr(self, '_hash', None) is not None:
            return getattr(self, '_hash')

        return blake2b_256_hash(self.to_jam_bytes().to_bytes())

    def get_unsigned_payload(self) -> bytes:
        """
        Payload to create seal signature GP-0.7.1-eq:6.15,6.16 E_U(H)

        Serialization: GP-0.7.1-eq:C.23

        Returns
        -------
        bytes
        """
        return self.to_jam_bytes().to_bytes()[:-96]

    @hash.setter
    def hash(self, value: bytes) -> None:
        setattr(self, '_hash', value)

    @property
    def slot_phase_index(self) -> int:
        """
        GP-0.7.0-eq:6.2 (m) | Function that returns the phase index into the epoch of the timeslot.

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot.

        """
        return self.timeslot % EPOCH_TIMESLOTS

    def verify_ticket_seal(self, bandersnatch_key: bytes, ticket_body: TicketBody, entropy: bytes) -> bytes:
        return ietf_vrf_verify(
            bytes(bandersnatch_key),
            vrf_input_ticket_seal(entropy, ticket_body.attempt),
            self.get_unsigned_payload(),
            bytes(self.seal)
        )

    def verify_fallback_seal(self, sealer_key: bytes, entropy: bytes) -> bytes:
        return ietf_vrf_verify(
            bytes(sealer_key),
            vrf_input_fallback_seal(entropy),
            self.get_unsigned_payload(),
            bytes(self.seal)
        )

    def generate_ticket_seal(self, bandersnatch_priv_key: bytes, entropy: bytes, ticket_attempt: int) -> bytes:
        """
        GP-0.7.1-eq:6.15 (bold_H_S) | Generate block seal using tickets

        Parameters
        ----------
        bandersnatch_priv_key
        entropy
        ticket_attempt

        Returns
        -------
        bytes
        """
        return ietf_vrf_sign(
            bandersnatch_priv_key,
            vrf_input_ticket_seal(entropy, ticket_attempt),
            self.get_unsigned_payload()
        )

    def generate_fallback_seal(self, bandersnatch_priv_key: bytes, entropy: bytes) -> bytes:
        """
        GP-0.7.1-eq:6.16 (bold_H_S) | Generate block seal using fallback method

        Parameters
        ----------
        bandersnatch_priv_key
        entropy

        Returns
        -------
        bytes
        """
        return ietf_vrf_sign(
            bandersnatch_priv_key,
            vrf_input_fallback_seal(entropy),
            self.get_unsigned_payload()
        )

    @classmethod
    def default(cls) -> 'Header':
        """
        GP-0.7.1-section:5 | We already presume consensus over this genesis header H^0 and the state it represents
        defined as σ^0. TODO make configurable
        """
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

    @classmethod
    def genesis(cls, validators: List[ValidatorData]) -> 'Header':
        """
        Genesis header (Bold_H_0)

        Parameters
        ----------
        validators: List[ValidatorData]

        Returns
        -------
        Header
        """
        return Header(
            parent=bytes(32),
            parent_state_root=bytes(32),
            extrinsic_hash=bytes(32),
            timeslot=0,
            epoch_marker=EpochMark(
                entropy=bytes(32),
                tickets_entropy=bytes(32),
                validators=[
                    EpochMarkValidatorKeys(
                        bandersnatch=v.bandersnatch,
                        ed25519=v.ed25519
                    ) for v in validators
                ],
            ),
            tickets_marker=None,
            offenders_marker=[],
            author_index=65535,
            entropy_source=bytes(96),
            seal=bytes(96)
        )

    @property
    def author_bandersnatch_key(self) -> Optional[bytes]:
        """
        GP-0.7.1-eq:5.9 (bold_H_A) Derived author bandersnatch key from author index
        Returns
        -------
        Optional[bytes]
        """
        return getattr(self, '_author_bandersnatch_key', None)

    def set_author_bandersnatch_key(self, post_state_validator_pool: 'ValidatorPoolState'):
        """
        GP-0.7.1-eq:5.9 (bold_H_A) | Derive author bandersnatch key from validator pool (κ')

        Parameters
        ----------
        post_state_validator_pool: ValidatorPoolState

        Returns
        -------

        """
        if self.author_index >= len(post_state_validator_pool.validators):
            raise BlockValidationError("Invalid author index")

        setattr(self, '_author_bandersnatch_key', post_state_validator_pool.validators[self.author_index].bandersnatch)


@dataclass
class Extrinsic(Serializable):
    """
    GP-0.7.1-eq:4.3 (bold_E) | Extrinsic data is input data external to the system.
    Extrinsic data is split into several discrete portions.

    Serialization: GP-0.7.1-eq:C.16

    Attributes
    ----------
    tickets: Vec(TicketEnvelope)
        GP-0.7.1-eq:6.29 (bold_E_T) |
        Manages selection of validators for permissioning of block authoring
    preimages: Vec(Preimage)
        GP-0.7.1-eq:12.28 (bold_E_P) |
        Static data presently being requested to be available for workloads to be able to fetch on demand
    guarantees: Vec(Guarantee)
        GP-0.7.1-eq:11.22 (bold_E_G) |
        Reports of newly completed workloads whose accuracy is guaranteed by specific validators
    assurances: Vec(Assurance)
        GP-0.7.1-eq:11.8 (bold_E_A) |
        Assurances by each validator concerning which of the input data of workloads they have correctly received and
        are storing locally
    disputes: ExtrinsicDisputes
        GP-0.7.1-eq:10.2 (bold_E_D) |
        Votes by validators on disputes
    """
    tickets: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})
    preimages: List[Preimage] = field(metadata={'codec': Vec(Preimage.to_codec_def())})
    guarantees: List[Guarantee] = field(metadata={'codec': Vec(Guarantee.to_codec_def())})
    assurances: List[Assurance] = field(metadata={'codec': Vec(Assurance.to_codec_def())})
    disputes: ExtrinsicDisputes = field(metadata={'codec': ExtrinsicDisputes.to_codec_def()})

    def generate_extrinsic_hash(self) -> bytes:
        """
        GP-0.7.1-eq:5.4,5.5,5.6

        Returns
        -------
        bytes
        """

        # GP-0.7.1-eq:5.5
        extrinsic_hash = blake2b_256_hash(bytes(Vec(TicketEnvelope.to_codec_def()).encode([
            t.to_jam_bytes() for t in self.tickets
        ])))

        extrinsic_hash += blake2b_256_hash(bytes(Vec(Preimage.to_codec_def()).encode([
            p.to_jam_bytes() for p in self.preimages
        ])))

        hashed_guarantees = Vec(Tuple(H256, U32, Vec(Credential.to_codec_def()))).encode(
            [
                (blake2b_256_hash(bytes(g.report.to_jam_bytes())), g.slot, [s.to_jam_bytes() for s in g.signatures])
                for g in self.guarantees
            ]
        )

        extrinsic_hash += blake2b_256_hash(bytes(hashed_guarantees))
        extrinsic_hash += blake2b_256_hash(bytes(Vec(Assurance.to_codec_def()).encode([
            a.to_jam_bytes() for a in self.assurances
        ])))
        extrinsic_hash += blake2b_256_hash(bytes(self.disputes.to_jam_bytes()))

        # GP-0.7.1-eq:5.4
        return blake2b_256_hash(extrinsic_hash)

    @classmethod
    def default(cls) -> "Extrinsic":
        return cls(
            tickets=[],
            preimages=[],
            guarantees=[],
            assurances=[],
            disputes=ExtrinsicDisputes(
                verdicts=[],
                culprits=[],
                faults=[]
            )
        )


@dataclass
class Block(Serializable):
    """
    GP-0.7.1-eq:4.2 (bold_B) | The header is a collection of metadata primarily concerned with cryptographic references
    to the blockchain ancestors and the operands and results of the present transition.

    Attributes
    ----------
    header: Header
        GP-0.7.1-eq:5.1 (bold_H) | Collection of metadata primarily concerned with cryptographic references to the
        blockchain ancestors and the operands and results of the present transition
    extrinsic: Extrinsic
        GP-0.7.1-eq:4.3 (bold_E) |
        Extrinsic data is input data external to the system
    """
    header: Header = field(metadata={'codec': Header.to_codec_def()})
    extrinsic: Extrinsic = field(metadata={'codec': Extrinsic.to_codec_def()})


@dataclass
class GuarantorAssignment:
    core_index: int
    validator_ed25519: bytes


@dataclass
class AccumulationStatistic:
    total_gas_utilized: int = 0
    nr_work_reports_accumulated: int = 0

