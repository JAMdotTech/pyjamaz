import enum
from dataclasses import dataclass, field
from typing import Optional, List

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Enum, Vec, H256, Array
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.types.block import OutputMarks, EpochMark, TicketsMark, TicketBody
from pyjamaz.types.state import SafroleState, ValidatorPoolState, TimeslotState, EntropyState, DisputesState, \
    ValidatorArchiveState, RecentHistoryState, StatisticsState, AuthorizerPoolsState, AssurancesState, ServicesState, \
    BeefyCommitmentMap


@dataclass
class TimeslotOutput(Serializable):
    """
    GP-0.3.8-eq:16 (τ') | Output of Timeslot STF.

    Attributes
    ----------
    post_state: TimeslotState
        GP-0.3.8-eq:16 (τ') | Primary output of Timeslot STF.
    """
    post_state: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})


@dataclass
class EntropyOutput(Serializable):
    """
    GP-0.3.8-eq:20 (η') | Output of Entropy STF.

    Attributes
    ----------
    post_state: EntropyState
        GP-0.3.8-eq:20 (η') | Primary output of Entropy STF.
    """
    post_state: EntropyState = field(metadata={'codec': EntropyState.to_codec_def()})


class DisputesErrorCode(Serializable, enum.Enum):
    already_judged = 0
    bad_vote_split = 1
    verdicts_not_sorted_unique = 2
    judgements_not_sorted_unique = 3
    culprits_not_sorted_unique = 4
    faults_not_sorted_unique = 5
    not_enough_culprits = 6
    not_enough_faults = 7
    culprits_verdict_not_bad = 8
    fault_verdict_wrong = 9
    offender_already_reported = 10
    bad_judgement_age = 11
    bad_validator_index = 12
    bad_signature = 13


@dataclass
class DisputesOutput(Serializable):
    """
    GP-0.3.8-eq:23 (ψ') | Output of Disputes STF.

    Attributes
    ----------
    post_state: DisputesState
        GP-0.3.8-eq:23 (ψ') | Primary output of Disputes STF.
    output_marks: OutputMarks
        GP-0.3.8-eq:115 (ψ') | Secondary output of Disputes STF.
    """
    post_state: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})


@dataclass
class ValidatorArchiveOutput(Serializable):
    """
    GP-0.3.8-eq:22 (λ') | Output of ValidatorArchive STF.

    Attributes
    ----------
    post_state: ValidatorArchiveState
        GP-0.3.8-eq:22 (λ') | Primary output of ValidatorArchive STF.
    """
    post_state: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})


@dataclass
class ValidatorPoolOutput(Serializable):
    """
    GP-0.3.8-eq:21 (κ') | Output of ValidatorPool STF.

    Attributes
    ----------
    post_state:ValidatorPoolState
        GP-0.3.8-eq:21 (κ') | Primary output of ValidatorPool STF.
    """
    post_state: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})


@dataclass
class RecentHistoryIntermediateOutput(Serializable):
    """
    GP-0.3.8-eq:17 (β†) | Output of RecentHistoryIntermediate STF.

    Attributes
    ----------
    intermediate_state:RecentHistoryState
        GP-0.3.8-eq:17 (β†) | Primary output of RecentHistoryIntermediate STF.
    """
    intermediate_state: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})


@dataclass
class RecentHistoryOutput(Serializable):
    """
    GP-0.3.8-eq:18 (β†) | Output of RecentHistory STF.

    Attributes
    ----------
    post_state:RecentHistoryState
        GP-0.3.8-eq:18 (β†) | Primary output of RecentHistory STF.
    """
    post_state: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})


class SafroleErrorCode(Serializable, enum.Enum):
    bad_slot = 0  # Timeslot value must be strictly monotonic.
    unexpected_ticket = 1  # Received a ticket while in epoch's tail.
    bad_ticket_order = 2  # Tickets must be sorted.
    bad_ticket_proof = 3  # Invalid ticket ring proof.
    bad_ticket_attempt = 4  # Invalid ticket attempt value.
    reserved = 5  # Reserved
    duplicate_ticket = 6  # Found a ticket duplicate.
    too_many_tickets = 7  # Found amount of tickets > K


@dataclass
class SafroleOutput(Serializable):
    """
    GP-0.3.8-eq:19 (γ') | Output of Safrole STF.

    Attributes
    ----------
    post_state: SafroleState
        GP-0.3.8-eq:19 (γ') | Primary output of Safrole STF.
    output_marks: OutputMarks
        GP-0.3.8-eq:71.72 (bold_H_e, bold_H_w) | Secondary output of Safrole STF.
    """
    post_state: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
        )  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
        )  # Tickets signal. OPTIONAL


@dataclass
class AuthorizerPoolsOutput(Serializable):
    """
    GP-0.3.8-eq:29 (α') | Output of AuthorizerPools STF.

    Attributes
    ----------
    post_state:AuthorizerPoolsState
        GP-0.3.8-eq:29 (α') | Primary output of AuthorizerPools STF.
    """
    post_state: AuthorizerPoolsState = field(metadata={'codec': AuthorizerPoolsState.to_codec_def()})


@dataclass
class AssurancesAfterDisputesOutput(Serializable):
    """
    GP-0.3.8-eq:25 (ρ†) | Output of AssurancesAfterDisputes STF.

    Attributes
    ----------
    intermediate_state_after_disputes:AssurancesState
        GP-0.3.8-eq:25 (ρ†) | Primary output of AssurancesAfterDisputes STF.
    """
    intermediate_state_after_disputes: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class AssurancesAfterAssurancesOutput(Serializable):
    """
    GP-0.3.8-eq:26 (ρ‡) | Output of AssurancesAfterAssurances STF.

    Attributes
    ----------
    intermediate_state_after_assurances:AssurancesState
        GP-0.3.8-eq:26 (ρ‡) | Primary output of AssurancesAfterAssurances STF.
    """
    intermediate_state_after_assurances: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class AssurancesAfterGuaranteesOutput(Serializable):
    """
    GP-0.3.8-eq:27 (ρ') | Output of AssurancesAfterGuarantees STF.

    Attributes
    ----------
    post_state:AssurancesState
        GP-0.3.8-eq:27 (ρ') | Primary output of AssurancesAfterGuarantees STF.
    """
    post_state: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class StatisticsOutput(Serializable):
    """
    GP-0.3.8-eq:30 (π') | Output of Statistics STF.

    Attributes
    ----------
    post_state:StatisticsState
        GP-0.3.8-eq:30 (π') | Primary output of Statistics STF.
    """
    post_state: StatisticsState = field(metadata={'codec': StatisticsState.to_codec_def()})


@dataclass
class ServicesAfterPreimagesOutput(Serializable):
    """
    GP-0.3.8-eq:24 (δ†) | Output of ServicesAfterPreimages STF.

    Attributes
    ----------
    intermediate_state_after_preimages:ServicesState
        GP-0.3.8-eq:24 (δ†) | Primary output of ServicesAfterPreimages STF.
    """
    intermediate_state_after_preimages: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})


@dataclass
class ServicesOutput(Serializable):
    """
    GP-0.3.8-eq:28 (δ') | Output of Services STF.

    Attributes
    ----------
    post_state:ServicesState
        GP-0.3.8-eq:28 (δ') | Primary output of Services STF.
    beefy_commitment_map:BeefyCommitmentMap
        GP-0.3.8-eq:163 (bold_C) | Secondary output of Services STF, BeefyCommitmentMap.
    """
    post_state: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    # BeefyCommitmentMap
    beefy_commitment_map: BeefyCommitmentMap = field(
        default=None,
        metadata={'codec': BeefyCommitmentMap.to_codec_def()}
    )


@dataclass
class STFOutput(Serializable):
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
        )  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
        )  # Tickets signal. OPTIONAL
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})
