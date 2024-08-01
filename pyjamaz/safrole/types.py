from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from pyjamaz.mixins import Serializable
from pyjamaz.models.common import ValidatorKeys, ValidatorKeysObject

U8 = int  # INTEGER (0..255)
U32 = int  # INTEGER (0..4294967295)
ByteArray32 = bytes  # SEQUENCE (SIZE(32)) OF U8
ByteArray128 = bytes
ByteArray144 = bytes
ByteArray784 = bytes
OpaqueHash = ByteArray32
Ed25519Key = ByteArray32
BlsKey = ByteArray144  # SEQUENCE (SIZE(144)) OF U8
BandersnatchKey = ByteArray32
EpochKeys = List[BandersnatchKey]  # SEQUENCE (SIZE(epoch-length)) OF BandersnatchKey
TicketsBodies = List['TicketBody']  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


class CustomErrorCode(Enum):
    BAD_SLOT = 0  # Timeslot value must be strictly monotonic.
    UNEXPECTED_TICKET = 1  # Received a ticket while in epoch's tail.
    BAD_TICKET_ORDER = 2  # Tickets must be sorted.
    BAD_TICKET_PROOF = 3  # Invalid ticket ring proof.
    BAD_TICKET_ATTEMPT = 4  # Invalid ticket attempt value.
    RESERVED = 5  # Reserved
    DUPLICATE_TICKET = 6  # Found a ticket duplicate.


@dataclass
class TicketBody:
    id: OpaqueHash  # OpaqueHash
    attempt: U8     # U8


@dataclass
class SlotSealerSeries:
    tickets: Optional[List[TicketBody]] = field(default_factory=list)  # Optional list of TicketBody instances
    keys: Optional[List[BandersnatchKey]] = field(default_factory=list)  # Optional list of BandersnatchKey instances


@dataclass
class ValidatorData(Serializable):
    bandersnatch: BandersnatchKey  # Use forward references if these types are not yet defined in the current scope.
    ed25519: Ed25519Key
    bls: BlsKey
    metadata: ByteArray128

    _scale_type_def = ValidatorKeys()

    def to_scale_type(self) -> 'ValidatorKeysObject':
        # Create a new instance of the scale type using the scale_type_def metadata.
        scale_type = self._scale_type_def.new()
        # Deserialize the keys and metadata into the scale type.
        scale_type.deserialize({
            'bs_key': self.bandersnatch,  # GP-ref:52,vb
            'ed25519_key': self.ed25519,  # GP-ref:53,ve
            'bls_key': self.bls,  # GP-ref:54,vBLS
            'metadata': self.metadata  # GP-ref:55,vm
        })
        return scale_type

    @classmethod
    def from_scale_type(cls, scale_type: ValidatorKeysObject):
        return cls(
            bandersnatch=scale_type.value_object['bs_key'].to_bytes(),
            ed25519=scale_type.value_object['ed25519_key'].to_bytes(),
            bls=scale_type.value_object['bls_key'].to_bytes(),
            metadata=scale_type.value_object['metadata'].to_bytes(),
        )


ValidatorsData = List[ValidatorData]  # SEQUENCE (SIZE(validators-count)) OF ValidatorData


@dataclass
class TicketEnvelope:
    attempt: U8  # U8
    signature: ByteArray784  # SEQUENCE (SIZE(784)) OF U8

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, bytes) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


@dataclass
class EpochMark:
    entropy: OpaqueHash  # OpaqueHash
    validators: List[BandersnatchKey]  # SEQUENCE (SIZE(validators-count)) OF BandersnatchKey


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks:
    epoch_mark: Optional[EpochMark] = None  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = None  # Tickets signal. OPTIONAL


@dataclass
class State:
    tau: U32  # Most recent block's timeslot.
    eta: List[OpaqueHash]  # SEQUENCE (SIZE(4)) OF OpaqueHash
    lambda_: ValidatorsData  # Validator keys and metadata which were active in the prior epoch.
    kappa: ValidatorsData  # Validator keys and metadata currently active.
    gamma_k: ValidatorsData  # Validator keys for the following epoch.
    iota: ValidatorsData  # Validator keys and metadata to be drawn from next.
    gamma_a: TicketsBodies  # Sealing-key contest ticket accumulator. SEQUENCE (SIZE(0..epoch-length)) OF TicketBody
    gamma_s: SlotSealerSeries  # Sealing-key series of the current epoch.
    gamma_z: ByteArray144  # Bandersnatch ring commitment. SEQUENCE (SIZE(144)) OF U8


@dataclass
class Input:
    slot: U32  # Current slot. U32
    entropy: OpaqueHash  # Per block entropy (originated from block entropy source VRF). OpaqueHash
    extrinsic: List[TicketEnvelope]  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope


@dataclass
class Output:
    ok: Optional[OutputMarks] = None  # Markers
    err: Optional[CustomErrorCode] = None  # Error code (not specified in the Graypaper)


@dataclass
class Testcase:
    input: Input  # Input.
    pre_state: State  # Pre-execution state.
    output: Output  # Output.
    post_state: State  # Post-execution state.
