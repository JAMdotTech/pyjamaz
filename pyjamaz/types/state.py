from dataclasses import dataclass, field
from typing import List

from jamcodec.mixins import Serializable
from jamcodec.types import U32, Array, H256, Vec, U8
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.safrole import TicketBody, SlotSealerSeries
from pyjamaz.types.common import ValidatorData

from pyjamaz.state.base import State


@dataclass
class TimeslotState(Serializable, State):
    number: int = field(metadata={'codec': U32})  # Most recent block's timeslot; GP-ref:TAU

    def epoch_number(self) -> int:
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(Serializable, State):
    entropy: List[bytes] = field(metadata={'codec': Array(H256, 4)})  # GP-ref:ETA


@dataclass
class SafroleState(Serializable):
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})  # Validator keys for the following epoch. # GP-ref:GAMMA_k,50
    ticket_accumulator: List[TicketBody] = field(metadata={'codec': Vec(TicketBody.to_codec_def())})  # Sealing-key contest ticket accumulator.
    slot_sealer_series: SlotSealerSeries = field(metadata={'codec': SlotSealerSeries.to_codec_def()}) # Sealing-key series of the current epoch.
    ring_commitment: bytes = field(metadata={'codec': Array(U8, 144)})  # Bandersnatch ring commitment.


@dataclass
class ValidatorQueueState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})  # Validator keys and metadata to be drawn from next. # GP-ref:IOTA,50


@dataclass
class ValidatorPoolState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})  # Validator keys and metadata currently active. # GP-ref:KAPPA,50


@dataclass
class ValidatorArchiveState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})  # Validator keys and metadata which were active in the prior epoch. # GP-ref: LAMBDA,50


@dataclass
class JamState(Serializable, State):
    timeslot: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})
    entropy: EntropyState = field(metadata={'codec': EntropyState.to_codec_def()})
    safrole: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    validator_pool: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})
    validator_archive: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})




