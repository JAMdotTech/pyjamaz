import enum
from dataclasses import dataclass, field
from typing import Optional, List

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Vec, H256, Array, U32
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.models.block import EpochMark
from pyjamaz.models.common import WorkReport, TicketBody
from pyjamaz.models.state import SafroleState, ValidatorPoolState, TimeslotState, EntropyState, DisputesState, \
    ValidatorArchiveState, RecentHistoryState, StatisticsState, AuthorizerPoolsState, AssurancesState, ServicesState, \
    BeefyCommitmentMap, AccumulationHistoryState, AccumulationQueueState, PrivilegedServicesState, ValidatorQueueState, \
    AuthorizerQueuesState, DeferredTransfer


@dataclass
class TimeslotOutput(Serializable):
    """
    GP-0.5.0-eq:4.5 (τ') | Output of Timeslot STF.

    Attributes
    ----------
    post_state: TimeslotState
        GP-0.5.0-eq:4.5 (τ') | Primary output of Timeslot STF.
    """
    post_state: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})


@dataclass
class EntropyOutput(Serializable):
    """
    GP-0.5.0-eq:4.9 (η') | Output of Entropy STF.

    Attributes
    ----------
    post_state: EntropyState
        GP-0.5.0-eq:4.9 (η') | Primary output of Entropy STF.
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
    GP-0.5.0-eq:4.12 (ψ') | Output of Disputes STF.

    Attributes
    ----------
    post_state: DisputesState
        GP-0.5.0-eq:4.12 (ψ') | Primary output of Disputes STF.
    offenders_mark: Vec(H256)
        GP-0.5.0-eq:10.20 (bold_H_o) | Secondary output of Disputes STF.
    """
    post_state: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})


@dataclass
class ValidatorArchiveOutput(Serializable):
    """
    GP-0.5.0-eq:4.11 (λ') | Output of ValidatorArchive STF.

    Attributes
    ----------
    post_state: ValidatorArchiveState
        GP-0.5.0-eq:4.11 (λ') | Primary output of ValidatorArchive STF.
    """
    post_state: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})


@dataclass
class ValidatorPoolOutput(Serializable):
    """
    GP-0.5.0-eq:4.10 (κ') | Output of ValidatorPool STF.

    Attributes
    ----------
    post_state:ValidatorPoolState
        GP-0.5.0-eq:4.10 (κ') | Primary output of ValidatorPool STF.
    """
    post_state: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})


@dataclass
class RecentHistoryIntermediateOutput(Serializable):
    """
    GP-0.5.0-eq:4.6 (β†) | Output of RecentHistoryIntermediate STF.

    Attributes
    ----------
    intermediate_state:RecentHistoryState
        GP-0.5.0-eq:4.6 (β†) | Primary output of RecentHistoryIntermediate STF.
    """
    intermediate_state: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})


@dataclass
class RecentHistoryOutput(Serializable):
    """
    GP-0.5.0-eq:4.7 (β') | Output of RecentHistory STF.

    Attributes
    ----------
    post_state:RecentHistoryState
        GP-0.5.0-eq:4.7 (β') | Primary output of RecentHistory STF.
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
    GP-0.5.0-eq:4.8 (γ') | Output of Safrole STF.

    Attributes
    ----------
    post_state: SafroleState
        GP-0.5.0-eq:4.8 (γ') | Primary output of Safrole STF.
    epoch_mark: Option(EpochMark)
        GP-0.5.0-eq:4.27 (bold_H_e) | Secondary output of Safrole STF.
    tickets_mark: Option(Array(TicketBody, EPOCH_TIMESLOTS))
        GP-0.5.0-eq:4.28 (bold_H_w) | Secondary output of Safrole STF.
    """
    post_state: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
    )
    tickets_mark: Optional[List[TicketBody]] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )


@dataclass
class AuthorizerPoolsOutput(Serializable):
    """
    GP-0.5.0-eq:4.19 (α') | Output of AuthorizerPools STF.

    Attributes
    ----------
    post_state:AuthorizerPoolsState
        GP-0.5.0-eq:4.19 (α') | Primary output of AuthorizerPools STF.
    """
    post_state: AuthorizerPoolsState = field(metadata={'codec': AuthorizerPoolsState.to_codec_def()})


@dataclass
class AssurancesAfterDisputesOutput(Serializable):
    """
    GP-0.5.0-eq:4.13 (ρ†) | Output of AssurancesAfterDisputes STF.

    Attributes
    ----------
    intermediate_state_after_disputes:AssurancesState
        GP-0.5.0-eq:4.13 (ρ†) | Primary output of AssurancesAfterDisputes STF.
    """
    intermediate_state_after_disputes: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class AssurancesAfterAssurancesOutput(Serializable):
    """
    GP-0.5.0-eq:4.14 (ρ‡) | Output of AssurancesAfterAssurances STF.

    Attributes
    ----------
    intermediate_state_after_assurances: AssurancesState
        GP-0.5.0-eq:4.14 (ρ‡) | Primary output of AssurancesAfterAssurances STF.
    reported: List[WorkReport]
        GP-0.5.2-eq:11.17 (bold_W) | Items removed from ρ† to get ρ'
    """
    intermediate_state_after_assurances: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})
    reported: List[WorkReport] = field(metadata={'codec': Vec(WorkReport.to_codec_def())})


@dataclass
class ReportedPackage(Serializable):
    work_package_hash: bytes = field(metadata={'codec': H256})
    segment_tree_root: bytes = field(metadata={'codec': H256})


@dataclass
class AssurancesAfterGuaranteesOutput(Serializable):
    """
    GP-0.5.0-eq:4.15 (ρ') | Output of AssurancesAfterGuarantees STF.

    Attributes
    ----------
    post_state: AssurancesState
        GP-0.5.0-eq:4.15 (ρ') | Primary output of AssurancesAfterGuarantees STF.
    reported: List[ReportedPackage]
        GP-0.5.2-eq:11.29 (bold_w) | The set of work reports in the current extrinsic
    reporters: List[bytes]
        GP-0.5.2-eq:11.27 (bold_R) | Ed25519 keys of validators in the current extrinsic
    """
    post_state: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})
    reported: List[ReportedPackage] = field(metadata={'codec': Vec(ReportedPackage.to_codec_def())})
    reporters: List[bytes] = field(metadata={'codec': Vec(H256)})


class AssurancesErrorCode(Serializable, enum.Enum):
    report_timeout = 0
    bad_attestation_parent = 1
    bad_validator_index = 2
    core_not_engaged = 3
    bad_signature = 4
    not_sorted_or_unique_assurers = 5

class GuaranteeErrorCode(Serializable, enum.Enum):
    bad_core_index = 0,
    future_report_slot = 1,
    report_epoch_before_last = 2,
    insufficient_guarantees = 3,
    out_of_order_guarantee = 4,
    not_sorted_or_unique_guarantors = 5,
    wrong_assignment = 6,
    core_engaged = 7,
    anchor_not_recent = 8,
    bad_service_id = 9,
    bad_code_hash = 10,
    dependency_missing = 11,
    duplicate_package = 12,
    bad_state_root = 13,
    bad_beefy_mmr_root = 14,
    core_unauthorized = 15,
    bad_validator_index = 16,
    work_report_gas_too_high = 17,
    service_item_gas_too_low = 18,
    too_many_dependencies = 19,
    segment_root_lookup_invalid = 20,
    bad_signature = 21,
    work_report_too_big = 22


@dataclass
class StatisticsOutput(Serializable):
    """
    GP-0.5.0-eq:4.20 (π') | Output of Statistics STF.

    Attributes
    ----------
    post_state:StatisticsState
        GP-0.5.0-eq:4.20 (π') | Primary output of Statistics STF.
    """
    post_state: StatisticsState = field(metadata={'codec': StatisticsState.to_codec_def()})


class ServicesErrorCode(Serializable, enum.Enum):
    preimage_unneeded = 0
    preimages_not_unique = 1


@dataclass
# TODO: Possibly deprecated since GP-0.5.0
class ServicesAfterPreimagesOutput(Serializable):
    """
    GP-0.5.0-eq:4.?? (δ') | Output of ServicesAfterPreimages STF.

    Attributes
    ----------
    post_state:ServicesState
        GP-0.5.0-eq:4.?? (δ') | Primary output of ServicesAfterPreimages STF.
    """
    post_state: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})


@dataclass
class ServicesAfterTransfersOutput(Serializable):
    """
    GP-0.5.0-eq:4.17 (δ‡) | Output of ServicesAfterTransfers STF.

    Attributes
    ----------
    intermediate_state_after_transfers: ServicesState
        GP-0.5.0-eq:4.17 (δ‡) | Primary output of ServicesAfterTransfers STF.
    """
    intermediate_state_after_transfers: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})


@dataclass
class ServicesAfterAccumulationOutput(Serializable):
    """
    GP-0.5.0-eq:4.18 (δ†) | Output of Services STF.

    Attributes
    ----------
    intermediate_state_after_accumulation: ServicesState
        GP-0.6.1-eq:12.22 (δ†) | Primary output of Services STF.
    post_state_privileged_services: PrivilegedServicesState
        GP-0.6.1-eq:12.22 (χ') | Posterior state of privileged services
    post_state_validator_queue: ValidatorQueueState
        GP-0.6.1-eq:12.22 (ι') | Posterior state of validator queue
    post_state_authorizer_queues: AuthorizerQueuesState
        GP-0.6.1-eq:12.22 (φ') | Posterior state of authorizer queues
    beefy_commitment_map: BeefyCommitmentMap
        GP-0.6.1-eq:12.21 (C) | Secondary output of Services STF, BeefyCommitmentMap.
    nr_work_results_accumulated: int
        GP-0.6.1-eq:12.21 (n) | Number of work results accumulated
    deferred_transfers: List[DeferredTransfer]
        GP-0.6.1-eq:12.21 (bold_t) | Number of work results accumulated

    """
    intermediate_state_after_accumulation: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    post_state_privileged_services: PrivilegedServicesState = field(metadata={'codec': PrivilegedServicesState.to_codec_def()})
    post_state_validator_queue: ValidatorQueueState = field(metadata={'codec': ValidatorQueueState.to_codec_def()})
    post_state_authorizer_queues: AuthorizerQueuesState = field(metadata={'codec': AuthorizerQueuesState.to_codec_def()})
    beefy_commitment_map: BeefyCommitmentMap = field(metadata={'codec': BeefyCommitmentMap.to_codec_def()})
    nr_work_results_accumulated: int = field(metadata={'codec': U32})
    deferred_transfers: List[DeferredTransfer] = field(metadata={'codec': Vec(DeferredTransfer.to_codec_def())})


@dataclass
class AccumulationHistoryOutput(Serializable):
    """
    GP-0.5.0-eq:4.17 (ξ') | Output of Accumulation History STF.

    Attributes
    ----------
    post_state: AccumulationHistoryState
        GP-0.5.0-eq:4.17 (ξ') | Primary output of AccumulationHistory STF.
    """
    post_state: AccumulationHistoryState = field(metadata={'codec': AccumulationHistoryState.to_codec_def()})


@dataclass
class AccumulationQueueOutput(Serializable):
    """
    GP-0.5.4-eq:4.17 (θ) | Output of Accumulation Queue STF.

    Attributes
    ----------
    post_state: ServicesState
        GP-0.5.4-eq:4.17 (θ') | Primary output of AccumulationQueue STF.
    """
    post_state: AccumulationQueueState = field(metadata={'codec': AccumulationQueueState.to_codec_def()})


@dataclass
class STFOutput(Serializable):
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
    )  # New epoch signal. OPTIONAL
    tickets_mark: Optional[List[TicketBody]] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
    )  # Tickets signal. OPTIONAL
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})
