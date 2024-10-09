import enum
from dataclasses import dataclass, field
from typing import Optional, List

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Enum, Vec, H256, Array
from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.types.block import OutputMarks, EpochMark, TicketsMark, TicketBody
from pyjamaz.types.state import SafroleState, ValidatorPoolState, TimeslotState, EntropyState, DisputesState, \
    ValidatorArchiveState, RecentHistoryState


@dataclass
class TimeslotOutput(Serializable):
    post_state: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})


@dataclass
class EntropyOutput(Serializable):
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
    post_state: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})


@dataclass
class ValidatorArchiveOutput(Serializable):
    post_state: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})


@dataclass
class ValidatorPoolOutput(Serializable):
    post_state: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})


@dataclass
class RecentHistoryOutput(Serializable):
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
    post_state: SafroleState = field(metadata={'codec': SafroleState.to_codec_def()})
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
        )  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
        )  # Tickets signal. OPTIONAL


@dataclass
class STFOutput(Serializable):
    epoch_mark: Optional[EpochMark] = field(
        default=None, metadata={'codec': Option(EpochMark.to_codec_def())}
        )  # New epoch signal. OPTIONAL
    tickets_mark: Optional[TicketsMark] = field(
        default=None, metadata={'codec': Option(Array(TicketBody.to_codec_def(), EPOCH_TIMESLOTS))}
        )  # Tickets signal. OPTIONAL
    offenders_mark: List[bytes] = field(default_factory=list, metadata={'codec': Vec(H256)})
