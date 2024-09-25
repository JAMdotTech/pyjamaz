from dataclasses import dataclass, field
from typing import List, Optional

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Array, H256, U32, U8, Vec, Enum
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.block import TicketBody
from pyjamaz.types.common import ValidatorsData, OpaqueHash, BandersnatchKey, ByteArray144, ValidatorData

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


