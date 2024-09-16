from dataclasses import dataclass, field
import enum
from typing import List, Optional, Union

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Array, H256, U32, U8, Vec, Enum
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.block import TicketBody, TicketEnvelope, OutputMarks
from pyjamaz.types.common import ValidatorsData, OpaqueHash, BandersnatchKey, ByteArray144, ValidatorData


class SafroleErrorCode(Serializable, enum.Enum):
    bad_slot = 0  # Timeslot value must be strictly monotonic.
    unexpected_ticket = 1  # Received a ticket while in epoch's tail.
    bad_ticket_order = 2  # Tickets must be sorted.
    bad_ticket_proof = 3  # Invalid ticket ring proof.
    bad_ticket_attempt = 4  # Invalid ticket attempt value.
    reserved = 5  # Reserved
    duplicate_ticket = 6  # Found a ticket duplicate.
    too_many_tickets = 7  # Found amount of tickets > K


TicketsBodies = List[TicketBody]  # SEQUENCE (SIZE(epoch-length)) OF TicketBody


@dataclass
class SlotSealerSeries(Serializable):
    tickets: Optional[List[TicketBody]] = field(default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))})  # Optional list of TicketBody instances
    keys: Optional[List[BandersnatchKey]] = field(default=None, metadata={'codec': Option(Array(H256, EPOCH_TIMESLOTS))})  # Optional list of BandersnatchKey instances

    _codec_type_def = Enum(
        tickets=Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS),
        keys=Array(H256, EPOCH_TIMESLOTS)
    )

    def __post_init__(self):
        if self.tickets is None and self.keys is None:
            raise ValueError("Either tickets or keys must be set")


@dataclass
class SafroleTestState(Serializable):
    # Most recent block's timeslot.
    tau: int = field(metadata={'codec': U32})
    # SEQUENCE (SIZE(4)) OF OpaqueHash
    eta: List[OpaqueHash] = field(metadata={'codec': Array(H256, 4)})
    lambda_: ValidatorsData = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata which were active in the prior epoch.
    kappa: ValidatorsData = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata currently active.
    gamma_k: ValidatorsData = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys for the following epoch.
    iota: ValidatorsData = field(
        metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)}
        )  # Validator keys and metadata to be drawn from next.
    gamma_a: TicketsBodies = field(
        metadata={'codec': Vec(TicketBody.to_codec_def())}
        )  # Sealing-key contest ticket accumulator.
    gamma_s: SlotSealerSeries = field(
        metadata={'codec': SlotSealerSeries.to_codec_def()}) # Sealing-key series of the current epoch.
    gamma_z: ByteArray144 = field(metadata={'codec': Array(U8, 144)})  # Bandersnatch ring commitment.


@dataclass
class SafroleInput(Serializable):
    slot: int = field(metadata={'codec': U32})  # Current slot. U32
    entropy: OpaqueHash = field(metadata={'codec': H256})  # Per block entropy (originated from block entropy source VRF)
    extrinsic: List[TicketEnvelope] = field(metadata={'codec': Vec(TicketEnvelope.to_codec_def())})  # Safrole extrinsic. SEQUENCE (SIZE(0..16)) OF TicketEnvelope


@dataclass
class SafroleOutput(Serializable):
    ok: Optional[OutputMarks] = field(default=None, metadata={'codec': Option(OutputMarks.to_codec_def())})  # Markers
    err: Optional[SafroleErrorCode] = field(default=None, metadata={'codec': Option(SafroleErrorCode.to_codec_def())})  # Error code (not specified in the Graypaper)

    _codec_type_def = Enum(
        ok=OutputMarks.to_codec_def(),
        err=SafroleErrorCode.to_codec_def()
    )

    def serialize(self) -> dict:
        if self.err is not None:
            return {'err': self.err.serialize()}
        else:
            return {'ok': self.ok.serialize()}
