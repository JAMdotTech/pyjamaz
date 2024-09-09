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
class AuthorizerPoolState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class RecentBlocksState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class ServicesState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class AssurancesState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class AuthorizerQueueState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class PrivilegedServicesState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class DisputesState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class StatisticsState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class JamState(Serializable, State):
    """
    GP-0.3.6-eq:15 (SIGMA | ) | Logically partitioned state into several largely independent segments which can help
    both visual clutter within the protocol description and provide formality over elements of computation which may be
    simultaneously calculated (i.e. parallelized).

    Attributes
    ----------
    authorizer_pool: AuthorizerPoolState
        GP-0.3.6-eq:15 (greek_ALPHA | α) |
        AuthorizerPool partition of the overall state
    recent_blocks: RecentBlocksState
        GP-0.3.6-eq:15 (greek_BETA | β) |
        RecentBlocks partition of the overall state
    safrole: SafroleState
        GP-0.3.6-eq:15 (greek_GAMMA | γ) |
        Safrole partition of the overall state
    services: ServicesState
        GP-0.3.6-eq:15 (greek_DELTA | δ) |
        Services partition of the overall state
    entropy: EntropyState
        GP-0.3.6-eq:15 (greek_ETA | η) |
        Entropy partition of the overall state
    validator_queue: ValidatorQueueState
        GP-0.3.6-eq:15 (greek_IOTA | ι) |
        ValidatorQueue partition of the overall state
    validator_pool: ValidatorPoolState
        GP-0.3.6-eq:15 (greek_KAPPA | κ) |
        ValidatorPool partition of the overall state
    validator_archive: ValidatorArchiveState
        GP-0.3.6-eq:15 (greek_LAMBDA | λ) |
        ValidatorArchive partition of the overall state
    assurances: AssurancesState
        GP-0.3.6-eq:15 (greek_RHO | ρ) |
        Assurances partition of the overall state
    timeslot: TimeslotState
        GP-0.3.6-eq:15 (greek_TAU | τ) |
        Timeslot partition of the overall state
    authorizer_queue: AuthorizerQueueState
        GP-0.3.6-eq:15 (greek_PHI | φ) |
        AuthorizerQueue partition of the overall state
    privileged_services: PrivilegedServicesState
        GP-0.3.6-eq:15 ({PSI} | χ) |
        PrivilegedServices partition of the overall state
    disputes: DisputesState
        GP-0.3.6-eq:15 (greek_CHI | ψ) |
        Disputes partition of the overall state
    statistics: StatisticsState
        GP-0.3.6-eq:15 (greek_PI | π) |
        Statistics partition of the overall state
    """
    authorizer_pool: AuthorizerPoolState = field(metadata={'codec': AuthorizerPoolState.to_codec_def()})
    recent_blocks: RecentBlocksState = field(metadata={'codec': RecentBlocksState.to_codec_def()})
    safrole: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    services: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    entropy: EntropyState = field(metadata={'codec': EntropyState.to_codec_def()})
    validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    validator_pool: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})
    validator_archive: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})
    assurances: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})
    timeslot: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})
    authorizer_queue: AuthorizerQueueState = field(metadata={'codec': AuthorizerQueueState.to_codec_def()})
    privileged_services: PrivilegedServicesState = field(metadata={'codec': PrivilegedServicesState.to_codec_def()})
    disputes: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    statistics: StatisticsState = field(metadata={'codec': StatisticsState.to_codec_def()})




