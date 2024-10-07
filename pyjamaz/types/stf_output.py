import enum
from dataclasses import dataclass, field
from typing import Optional

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Enum
from pyjamaz.types.block import OutputMarks
from pyjamaz.types.state import SafroleState, ValidatorPoolState, TimeslotState, EntropyState, DisputesState, \
    ValidatorArchiveState, RecentHistoryState, StatisticsState, AuthorizerPoolsState, AssurancesState, ServicesState, \
    BeefyCommitmentMap


@dataclass
class TimeslotOutput(Serializable):
    post_state: TimeslotState = field(metadata={'codec': TimeslotState.to_codec_def()})


@dataclass
class EntropyOutput(Serializable):
    post_state: EntropyState = field(metadata={'codec': EntropyState.to_codec_def()})


@dataclass
class DisputesOutput(Serializable):
    post_state: DisputesState = field(metadata={'codec': DisputesState.to_codec_def()})
    output_marks: OutputMarks = field(default=None, metadata={'codec': OutputMarks.to_codec_def()})


@dataclass
class ValidatorArchiveOutput(Serializable):
    post_state: ValidatorArchiveState = field(metadata={'codec': ValidatorArchiveState.to_codec_def()})


@dataclass
class ValidatorPoolOutput(Serializable):
    post_state: ValidatorPoolState = field(metadata={'codec': ValidatorPoolState.to_codec_def()})


@dataclass
class RecentHistoryIntermediateOutput(Serializable):
    intermediate_state: RecentHistoryState = field(metadata={'codec': RecentHistoryState.to_codec_def()})


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
    output_marks: OutputMarks = field(default=None, metadata={'codec': OutputMarks.to_codec_def()})  # Markers


@dataclass
class AuthorizerPoolsOutput(Serializable):
    post_state: AuthorizerPoolsState = field(metadata={'codec': AuthorizerPoolsState.to_codec_def()})


@dataclass
class AssurancesAfterDisputesOutput(Serializable):
    intermediate_state_after_disputes: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class AssurancesAfterAssurancesOutput(Serializable):
    intermediate_state_after_assurances: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class AssurancesAfterGuaranteesOutput(Serializable):
    post_state: AssurancesState = field(metadata={'codec': AssurancesState.to_codec_def()})


@dataclass
class StatisticsOutput(Serializable):
    post_state: StatisticsState = field(metadata={'codec': StatisticsState.to_codec_def()})


@dataclass
class ServicesAfterPreimagesOutput(Serializable):
    intermediate_state_after_preimages: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})


@dataclass
class ServicesOutput(Serializable):
    post_state: ServicesState = field(metadata={'codec': ServicesState.to_codec_def()})
    beefy_commitment_map: BeefyCommitmentMap = field(default=None, metadata={'codec': BeefyCommitmentMap.to_codec_def()})  # BeefyCommitmentMap


@dataclass
class STFOutput(Serializable):
    output_marks: OutputMarks = field(
        metadata={'codec': OutputMarks.to_codec_def()}
    )
