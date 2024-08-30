from dataclasses import dataclass, field
from typing import List, Optional

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.safrole import SlotSealerSeries
from pyjamaz.types.block import TicketBody
from pyjamaz.types.common import ValidatorData, BlockInfo

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
class BlocksHistoryState(Serializable, State):
    blocks: List[BlockInfo] = field(metadata={'size': 'blocks'})


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
    blocks_history: Optional[BlocksHistoryState]
    timeslot: Optional[TimeslotState]
    entropy: Optional[EntropyState]
    safrole: Optional[SafroleState]
    validator_queue: Optional[ValidatorQueueState]
    validator_pool: Optional[ValidatorPoolState]
    validator_archive: Optional[ValidatorArchiveState]




