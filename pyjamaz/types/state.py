from dataclasses import dataclass, field
from typing import List

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT
from pyjamaz.types.safrole import TicketBody, SlotSealerSeries
from pyjamaz.types.common import ValidatorData

from pyjamaz.serialization import Serializable
from pyjamaz.state.base import State


@dataclass
class TimeslotState(Serializable, State):
    number: int = field(metadata={'length': 4})  # GP-0.3.6-eq:36,45 (tau|τ,blackboard_N=U32) | Most recent block's timeslot

    # GP-0.3.6-eq:46 (italic_e,constant_E) | Epoch index [0,...]
    def epoch_number(self) -> int:
        return self.number // EPOCH_TIMESLOTS

    # GP-0.3.6-eq:46 (italic_m,constant_E) | Phase index [0,...,599]
    def slot_phase_index(self) -> int:
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(Serializable, State):
    entropy: List[bytes] = field(metadata={'length': 32, 'size': 4})  # GP-0.3.6-eq:65 (eta[]|η[]) | eta[0] functions as randomness accumulator, eta[1],eta[2],eta[3] retains historical values of the accumulator at three respective previous epoch endings


@dataclass
class SafroleState(Serializable):
    # TODO: question: impact of order? preferred order is the order in the grapypaper (gamma_k, gamma_z, gamma_s, gamma_a)
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # GP-0.3.6-eq:51 (gamma_k|γ_k,blackboard_K,constant_V) | 1023 validator keys for the following epoch
    ticket_accumulator: List[TicketBody] = field(metadata={'size': 'ticket_accumulator'})  # GP-0.3.6-eq:49 (gamma_a|γ_a,constant_E) | Sealing-key lottery ticket accumulator up to 600 items in list
    slot_sealer_series: SlotSealerSeries  # GP-0.3.6-eq:49 (gamma_s|γ_s) | Current epoch slot-sealer series
    ring_commitment: bytes = field(metadata={'length': 144})  # GP-0.3.6-eq:48 (gamma_z|γ_z,blackboard_Y_R) | Bandersnatch ring commitment


@dataclass
class ValidatorQueueState(Serializable, State):
    # TODO: Force list size to 1023 (constant_K)
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # GP-0.3.6-eq:51 (iota|ι,constant_V) | List of exactly 1023 validators (data includes keys and metadata) to be drawn from next once per epoch


@dataclass
class ValidatorPoolState(Serializable, State):
    # TODO: Force list size to 1023 (constant_K)
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # GP-0.3.6-eq:51 (kappa|κ,constant_V) | List of exactly 1023 validators (data includes keys and metadata) active in current epoch


@dataclass
class ValidatorArchiveState(Serializable, State):
    # TODO: Force list size to 1023 (constant_K)
    validators: List[ValidatorData] = field(metadata={'size': VALIDATOR_COUNT})  # GP-0.3.6-eq:51 (lambda|λ,constant_V) | List of exactly 1023 validators (data includes keys and metadata) which were active in the prior epoch


@dataclass
class JamState(Serializable, State):
    # GP-0.3.6-eq:15 (sigma|σ) | The state (sigma) is logically partitioned into several largely independent segments (enhances readability, allows parallelization)
    # TODO: complete type definition of state components
    timeslot: TimeslotState  # GP-0.3.6-eq:15 (tau|τ) | State with entropy related data
    entropy: EntropyState  # GP-0.3.6-eq:15 (eta|η) | State with time related data
    safrole: SafroleState  # GP-0.3.6-eq:15 (gamma|γ) | State dealing with validator slot allocation for next epoch
    validator_queue: ValidatorQueueState  # GP-0.3.6-eq:15 (iota|ι) | State with validators of future epoch
    validator_pool: ValidatorPoolState  # GP-0.3.6-eq:15 (kappa|κ) | State with validators of current epoch
    validator_archive: ValidatorArchiveState  # GP-0.3.6-eq:15 (lambda|λ) | State with validators of previous epoch

    # TODO: suggestion for additional type definitions of state below
    # TODO: question: impact of order? preferred order is the order in the grapypaper (alpha, beta, etc)
    # TODO: add placeholder dataclass for AuthorizerPoolState
    authorizer_pool: AuthorizerPoolState  # GP-0.3.6-eq:15 (alpha|α) | State with authorizers of current epoch
    # TODO: add placeholder dataclass for AuthorizerQueueState
    authorizer_queue: AuthorizerQueueState  # GP-0.3.6-eq:15 (phi|φ) | State with authorizers of future epoch
    # TODO: add placeholder dataclass for RecentHistoryState
    recent_history: RecentHistoryState  # GP-0.3.6-eq:15 (beta|β) | State with recent history
    # TODO: add placeholder dataclass for Services
    services: ServicesState  # GP-0.3.6-eq:15 (delta|δ) | State with services
    # TODO: add placeholder dataclass for Assurances
    assurances: AssurancesState  # GP-0.3.6-eq:15 (rho|ρ) | State with assurances
    # TODO: add placeholder dataclass for Disputes
    Disputes: DisputesState  # GP-0.3.6-eq:15 (psi|ψ) | State with disputes
    # TODO: add placeholder dataclass for PrivilegedServices
    privileged_services: PrivilegedServicesState  # GP-0.3.6-eq:15 (chi|χ) | State with privileged services
    # TODO: add placeholder dataclass for Statistics
    statistics: StatisticsState  # GP-0.3.6-eq:15 (pi|π) | State with statistics

