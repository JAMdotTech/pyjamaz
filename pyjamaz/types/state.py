from dataclasses import dataclass, field
from typing import List

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.safrole import TicketBody, SlotSealerSeries
from pyjamaz.types.common import ValidatorData

from pyjamaz.serialization import Serializable
from pyjamaz.state.base import State


@dataclass
class TimeslotState(Serializable, State):
    number: int = field(metadata={'length': 4})  # Most recent block's timeslot; GP-ref:TAU

    def epoch_number(self) -> int:
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(Serializable, State):
    entropy: List[bytes] = field(metadata={'length': 32, 'size': 4})  # GP-ref:ETA


@dataclass
class SafroleState(Serializable):
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys for the following epoch. # GP-ref:GAMMA_k,50
    ticket_accumulator: List[TicketBody] = field(metadata={'size': 'ticket_accumulator'})  # Sealing-key contest ticket accumulator.
    slot_sealer_series: SlotSealerSeries  # Sealing-key series of the current epoch.
    ring_commitment: bytes = field(metadata={'length': 144})  # Bandersnatch ring commitment.


@dataclass
class ValidatorQueueState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys and metadata to be drawn from next. # GP-ref:IOTA,50


@dataclass
class ValidatorPoolState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys and metadata currently active. # GP-ref:KAPPA,50


@dataclass
class ValidatorArchiveState(Serializable, State):
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # Validator keys and metadata which were active in the prior epoch. # GP-ref: LAMBDA,50


@dataclass
class JamState(Serializable, State):
    timeslot: TimeslotState
    entropy: EntropyState
    safrole: SafroleState
    validator_queue: ValidatorQueueState
    validator_pool: ValidatorPoolState
    validator_archive: ValidatorArchiveState




