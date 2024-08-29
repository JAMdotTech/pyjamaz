from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.serialization import Serializable
from pyjamaz.types.common import ValidatorsData, OpaqueHash, U8, BandersnatchKey, ByteArray784, U32, ByteArray144


class SafroleErrorCode(Serializable, Enum):
    bad_slot = 0  # Timeslot value must be strictly monotonic.
    unexpected_ticket = 1  # Received a ticket while in epoch's tail.
    bad_ticket_order = 2  # Tickets must be sorted.
    bad_ticket_proof = 3  # Invalid ticket ring proof.
    bad_ticket_attempt = 4  # Invalid ticket attempt value.
    reserved = 5  # Reserved
    duplicate_ticket = 6  # Found a ticket duplicate.
    too_many_tickets = 7  # Found amount of tickets > K


@dataclass
class TicketBody(Serializable):  # GP-0.3.6-eq:50 (blackboard_C) | # Single ticket
    id: OpaqueHash = field(metadata={'length': 32})  # GP-0.3.6-eq:50 (bold_y) | # OpaqueHash
    attempt: U8 = field(metadata={'length': 1})  # GP-0.3.6-eq:50 (italic_r) | # U8

# TODO: explain next line
TicketsBodies = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class SlotSealerSeries(Serializable):  # GP-0.3.6-eq:49 (gamma_s|γ_s) | Slot-sealer series (ENUM structure)
    # TODO: where does Graypaper state this is an optional list; let's discuss?
    tickets: Optional[List[TicketBody]] = field(default=None, metadata={'size': EPOCH_TIMESLOTS})  # GP-0.3.6-eq:49 (blackboard_C,constant_E) | ?Optional? list of exactly 600 TicketBody instances
    # TODO: where does Graypaper state this is an optional list; let's discuss?
    keys: Optional[List[BandersnatchKey]] = field(default=None, metadata={'size': EPOCH_TIMESLOTS, 'length': 32})  # GP-0.3.6-eq:49 (blackboard_H_B,constant_E) | ?Optional? list of exactly 600 BandersnatchKey instances

    def __post_init__(self):
        # TODO: BUG use XOR. Both at the same time is not allowed
        if self.tickets is None and self.keys is None:
            raise ValueError("Either tickets or keys must be set")


@dataclass
class TicketEnvelope(Serializable):
    attempt: U8 = field(metadata={'length': 1})
    signature: ByteArray784 = field(metadata={'length': 784})

    def __post_init__(self):
        # Validate that attempt is a valid U8 integer
        if not isinstance(self.attempt, int) or not (0 <= self.attempt <= 255):
            raise ValueError("Attempt must be an integer between 0 and 255")

        # Validate that signature is a valid ByteArray784
        if not isinstance(self.signature, (bytes, bytearray)) or len(self.signature) != 784:
            raise ValueError("Signature must be a bytes object of length 784")


@dataclass
class EpochMark(Serializable):
    entropy: OpaqueHash = field(metadata={'length': 32})
    validators: List[BandersnatchKey] = field(metadata={'length': 32, 'size': VALIDATOR_COUNT})


TicketsMark = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class OutputMarks(Serializable):
    epoch_mark: Optional[EpochMark] = None  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(default=None, metadata={'size': EPOCH_TIMESLOTS})  # Tickets signal. OPTIONAL


@dataclass
class SafroleTestState(Serializable):
    tau: U32 = field(metadata={'length': 4})                # Most recent block's timeslot.
    eta: List[OpaqueHash] = field(metadata={'length': 32, 'size': 4})  # SEQUENCE (SIZE(4)) OF OpaqueHash
    lambda_: ValidatorsData = field(metadata={'name': 'lambda', 'size': VALIDATOR_COUNT}) # Validator keys and metadata which were active in the prior epoch.
    kappa: ValidatorsData = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys and metadata currently active.
    gamma_k: ValidatorsData = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys for the following epoch.
    iota: ValidatorsData = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys and metadata to be drawn from next.
    gamma_a: TicketsBodies = field(metadata={'size': 'gamma_a'})  # Sealing-key contest ticket accumulator.
    gamma_s: SlotSealerSeries  # Sealing-key series of the current epoch.
    gamma_z: ByteArray144 = field(metadata={'length': 144})  # Bandersnatch ring commitment.


@dataclass
class SafroleInput(Serializable):
    slot: U32 = field(metadata={'length': 4})  # Current slot. U32
    entropy: OpaqueHash = field(metadata={'length': 32})  # Per block entropy (originated from block entropy source VRF)
    extrinsic: List[TicketEnvelope] = field(metadata={'size': 'extrinsic'})  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope


@dataclass
class SafroleOutput(Serializable):
    ok: Optional[OutputMarks] = None  # Markers
    err: Optional[SafroleErrorCode] = None  # Error code (not specified in the Graypaper)

    def to_json(self) -> dict:
        if self.err is not None:
            return {'err': self.err.to_json()}
        else:
            return {'ok': self.ok.to_json()}
