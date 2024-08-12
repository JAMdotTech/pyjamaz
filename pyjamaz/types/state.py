from dataclasses import dataclass, field
from typing import List

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.safrole import TicketBody, SlotSealerSeries, ValidatorData

from pyjamaz.mixins import SerializableMixin
from pyjamaz.state.base import State
from scalecodec.types import U32, Array, H256, U8, Vec


@dataclass
class TimeslotState(SerializableMixin, State):
    number: int = field(metadata={'scale': U32})  # Most recent block's timeslot; GP-ref:TAU

    def epoch_number(self) -> int:
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(SerializableMixin, State):
    entropy: List[bytes] = field(metadata={'scale': Array(H256, 4)})  # GP-ref:ETA


@dataclass
class SafroleState(SerializableMixin):
    validators: List[ValidatorData] = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys for the following epoch. # GP-ref:GAMMA_k,50
    ticket_accumulator: List[TicketBody] = field(metadata={'scale': Vec(TicketBody.scale_type_def())})  # Sealing-key contest ticket accumulator.
    slot_sealer_series: SlotSealerSeries  # Sealing-key series of the current epoch.
    ring_commitment: bytes = field(metadata={'scale': Array(U8, 144)})  # Bandersnatch ring commitment.


@dataclass
class ValidatorQueueState(SerializableMixin, State):
    validators: List[ValidatorData] = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys and metadata to be drawn from next. # GP-ref:IOTA,50


@dataclass
class ValidatorPoolState(SerializableMixin, State):
    validators: List[ValidatorData] = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys and metadata currently active. # GP-ref:KAPPA,50


@dataclass
class ValidatorArchiveState(SerializableMixin, State):
    validators: List[ValidatorData] = field(metadata={'scale': Array(ValidatorData.scale_type_def(), VALIDATOR_COUNT)})  # Validator keys and metadata which were active in the prior epoch. # GP-ref: LAMBDA,50


@dataclass
class JamState(SerializableMixin, State):
    timeslot: TimeslotState
    entropy: EntropyState
    safrole: SafroleState
    validator_queue: ValidatorQueueState
    validator_pool: ValidatorPoolState
    validator_archive: ValidatorArchiveState




