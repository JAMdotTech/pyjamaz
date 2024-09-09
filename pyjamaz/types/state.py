from dataclasses import dataclass, field
from typing import List, Optional

from jamcodec.mixins import Serializable
from jamcodec.types import U32, Array, H256, Vec, U8, Option
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS, VALIDATOR_COUNT, HISTORY
from pyjamaz.types.safrole import TicketBody, SlotSealerSeries
from pyjamaz.types.common import ValidatorData

from pyjamaz.state.base import State


@dataclass
class TimeslotState(Serializable, State):
    """
    GP-0.3.6-eq:45 (greek_TAU | τ) | The most recent block's slot index, combined with helper functions

    Attributes
    ----------

    number: U32
        GP-0.3.6-eq:45 (greek_TAU | τ) |
        The most recent block's slot index
    """
    # Todo: consider renaming number to timeslot
    number: int = field(metadata={'codec': U32})

    def epoch_number(self) -> int:
        """
        GP-0.3.6-eq:46 (e) | Function that returns the epoch index

        Returns
        -------
        number: int
            Epoch index of the timeslot

        """
        return self.number // EPOCH_TIMESLOTS

    def slot_phase_index(self) -> int:
        """
        GP-0.3.6-eq:46 (m) | Function that returns the phase index into the epoch of the timeslot

        Returns
        -------
        number: int
            Phase index into the epoch of the timeslot

        """
        return self.number % EPOCH_TIMESLOTS


@dataclass
class EntropyState(Serializable, State):
    """
    GP-0.3.6-eq:65 (greek_ETA | η) | Entropy partition of the overall state.

    Attributes
    ----------

    entropy: Array(H256,4)
        GP-0.3.6-eq:65 (greek_ETA | η) | η[0] serves as an entropy accumulator during the current epoch. η[1], η[2],
        η[3] retain three historical values of the accumulator at the point of each of the three most recently ended
        epochs respectively.
    """
    entropy: List[bytes] = field(metadata={'codec': Array(H256, 4)})


@dataclass
class SafroleState(Serializable):
    """
    GP-0.3.6-eq:47 (greek_GAMMA | γ) | Safrole partition of the overall state.

    Attributes
    ----------

    validators: Array(ValidatorData,constant_V)
        GP-0.3.6-eq:51 (greek_GAMMA_k | γ_k) | A fixed size set of keys and metadata for validators of the next epoch.
    ticket_accumulator: TicketBody
        GP-0.3.6-eq:49 (greek_GAMMA_a | γ_a) | Sealing-key contest ticket accumulator.
    slot_sealer_series: SlotSealerSeries
        GP-0.3.6-eq:49 (greek_GAMMA_s | γ_s) | Sealing-key series of the current epoch.
    ring_commitment: Array(U8,144)
        GP-0.3.6-eq:48 (greek_GAMMA_z | γ_z) | Bandersnatch ring commitment.
    """
    # Todo: reorder attributes to match order in GP: (γ_k, γ_z, γ_s, γ_a)
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})
    # Todo: review and annotate: TicketBody
    ticket_accumulator: List[TicketBody] = field(metadata={'codec': Vec(TicketBody.to_codec_def())})
    # Todo: review and annotate: SlotSealerSeries
    slot_sealer_series: SlotSealerSeries = field(metadata={'codec': SlotSealerSeries.to_codec_def()})
    ring_commitment: bytes = field(metadata={'codec': Array(U8, 144)})


@dataclass
# Todo: @arjan explain why 'State' is used here and not in class SafroleState(Serializable):
class ValidatorQueueState(Serializable, State):
    """
    GP-0.3.6-eq:51 (greek_IOTA | ι) | Validator keys and metadata to be drawn from next by the Safrole protocol.

    Attributes
    ----------

    validators: Array(ValidatorData,constant_V)
        GP-0.3.6-eq:51 (greek_IOTA | ι) | A fixed size set of validator keys and metadata to be drawn from next by the
        Safrole protocol.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorPoolState(Serializable, State):
    """
    GP-0.3.6-eq:51 (greek_KAPPA | κ) | Keys and metadata for validators of the current epoch.

    Attributes
    ----------

    validators: Array(ValidatorData,constant_V)
        GP-0.3.6-eq:51 (greek_KAPPA | κ) | A fixed size set of keys and metadata for validators of the current epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class ValidatorArchiveState(Serializable, State):
    """
    GP-0.3.6-eq:51 (greek_LAMBDA | λ) | Keys and metadata for validators of the previous epoch.

    Attributes
    ----------

    validators: Array(ValidatorData,constant_V)
        GP-0.3.6-eq:51 (greek_LAMBDA | λ) | A fixed size set of keys and metadata for validators of the previous epoch.
    """
    # Todo: review and annotate: ValidatorData
    validators: List[ValidatorData] = field(metadata={'codec': Array(ValidatorData.to_codec_def(), VALIDATOR_COUNT)})


@dataclass
class AuthorizerPoolState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class Mmr(Serializable):
    """
    GP-0.3.6-eq:302 (bold_b) | A Merkle Mountain Range.

    Attributes
    ----------

    peaks: Vec(Option(H256))
        GP-0.3.6-eq:302 (bold_b) | A collection of optional peaks in a Merkle Mountain Range
    """
    peaks: List[Optional[bytes]] = field(metadata={'codec': Vec(Option(H256))})


@dataclass
class RecentBlock(Serializable):
    """
    GP-0.3.6-eq:80 (greek_BETA | β) | A single item in the RecentHistory partition of the overall state.

    Attributes
    ----------

    header_hash: H256
        GP-0.3.6-eq:80 (h, blackboard_H) | Header hash of the recent block.
    mmr: Mmr
        GP-0.3.6-eq:80 (b) | Accumulation result Merkle Mountain Range of the recent block.
    state_root: H256
        GP-0.3.6-eq:80 (s, blackboard_H) | State root of the recent block.
    reported: Vec(H256)
        GP-0.3.6-eq:80 (p) | A collection of hashes for each work-report made into the MMR, limited to the number of
        cores (constant_c=341)
    """
    header_hash: bytes = field(metadata={'codec': H256})
    mmr: Mmr = field(metadata={'codec': Mmr.to_codec_def()})
    state_root: bytes = field(metadata={'codec': H256})
    reported: List[bytes] = field(metadata={'codec': Vec(H256)})

    def __post_init__(self):
        # Todo: 'reported' attribute is allowed to have up to constant_C (CORES=341) items.
        pass


@dataclass
class RecentHistoryState(Serializable):
    """
    GP-0.3.6-eq:80 (greek_BETA | β) | RecentHistory partition of the overall state

    Attributes
    ----------

    recent_history: Vec(RecentBlock)
        GP-0.3.6-eq:80 (greek_BETA | β) | A collection of items in the RecentHistory partition of the overall state of
        up to constant_H (8) items.
    """
    recent_history: List[RecentBlock] = field(metadata={'codec': Vec(RecentBlock.to_codec_def())})

    def __post_init__(self):
        # Todo: RecentHistory is allowed to have up to constant_H (HISTORY) items
        # Todo: Arjan this is a Vec (variable size) since it contains less than 8 items for the first 8
        #  blocks after genesis, so for the first 8 blocks it should have TAU entries and from block 9 and onwards it
        #  should have exactly constant_H (8) entries.
        #  GP-0.3.6-eq-289-C(3) states encoding is a Vec (i.e. has length definition)
        pass


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
    """
    GP-0.3.6-eq:96 (greek_PSI | ψ) | A collection of judgements of validators over the validity of work reports.

    Attributes
    ----------

    good_set: Vec(H256)
        GP-0.3.6-eq:111,97,98 (greek_PSI_g | ψ_g) | A collection of work reports hashes with a good verdict.
    bad_set: Vec(H256)
        GP-0.3.6-eq:112,97,98 (greek_PSI_b | ψ_b) | A collection of work reports hashes with a bad verdict.
    wonky_set: Vec(H256)
        GP-0.3.6-eq:113,97,98 (greek_PSI_w | ψ_w) | A collection of work reports hashes with a wonky verdict.
    offenders: Vec(H256)
        GP-0.3.6-eq:114,100,101 (greek_PSI_o | ψ_o) | A collection Edwards 25519 keys for validators found guilty of
        offending.
    """
    good_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    bad_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    wonky_set: List[bytes] = field(metadata={'codec': Vec(H256)})
    offenders: List[bytes] = field(metadata={'codec': Vec(H256)})


@dataclass
class StatisticsState(Serializable):
    # Todo: placeholder attribute -> remove/replace
    placeholder: int = field(metadata={'codec': U32})


@dataclass
class JamState(Serializable, State):
    """
    GP-0.3.6-eq:15 (greek_SIGMA | σ) | Logically partitioned state into several largely independent segments which can help
    both visual clutter within the protocol description and provide formality over elements of computation which may be
    simultaneously calculated (i.e. parallelized).

    Attributes
    ----------
    authorizer_pool: AuthorizerPoolState
        GP-0.3.6-eq:15 (greek_ALPHA | α) |
        AuthorizerPool partition of the overall state
    recent_history: RecentHistoryState
        GP-0.3.6-eq:15 (greek_BETA | β) |
        RecentHistory partition of the overall state
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
        GP-0.3.6-eq:15 (greek_CHI | χ) |
        PrivilegedServices partition of the overall state
    disputes: DisputesState
        GP-0.3.6-eq:15 (greek_PSI | ψ) |
        Disputes partition of the overall state
    statistics: StatisticsState
        GP-0.3.6-eq:15 (greek_PI | π) |
        Statistics partition of the overall state
    """
    authorizer_pool: AuthorizerPoolState = field(metadata={'codec': AuthorizerPoolState.to_codec_def()})
    recent_history: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})
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

