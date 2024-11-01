import bisect
from copy import deepcopy, copy
from typing import List

from bandersnatch_vrfs import ring_vrf_verify, ring_commitment

import pyjamaz.graypaper_constants as gp_const
from jamcodec.base import JamBytes

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import MerkleMountainRange
from pyjamaz.signing import Keypair
from pyjamaz.storage import StorageInterface
from pyjamaz.models.common import ValidatorData
from pyjamaz.models.stf_output import SafroleErrorCode, SafroleOutput, ValidatorPoolOutput, TimeslotOutput, \
    EntropyOutput, ValidatorArchiveOutput, RecentHistoryOutput, DisputesOutput, StatisticsOutput, \
    AuthorizerPoolsOutput, RecentHistoryIntermediateOutput, AssurancesAfterDisputesOutput, \
    AssurancesAfterAssurancesOutput, AssurancesAfterGuaranteesOutput, ServicesOutput, ServicesAfterPreimagesOutput, \
    DisputesErrorCode

from pyjamaz.state.base import StateComponent
from pyjamaz.exceptions import StateTransitionError, BlockValidationError
from pyjamaz.models.block import TicketBody, EpochMark, Header, TicketEnvelope, ExtrinsicDisputes, \
    Guarantee, Preimage, Assurance, Verdict, Judgement, Culprit, Fault
from pyjamaz.models.state import TimeslotState, EntropyState, ValidatorPoolState, SafroleState, \
    ValidatorQueueState, ValidatorArchiveState, AuthorizerQueuesState, AuthorizerPoolsState, RecentHistoryState, \
    AssurancesState, PrivilegedServicesState, DisputesState, ServicesState, StatisticsState, RecentBlock, Mmr, \
    SlotSealerSeries, BeefyCommitmentMap
from pyjamaz.utils import reorder_list_outside_in, list_has_duplicates


class Timeslot(StateComponent):
    component_id = 11

    def state_transition(
            self,
            header: Header
    ) -> TimeslotOutput:
        """
        GP-0.3.8-eq:45 (τ') | State transition function for the state's timeslot.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:16 (bold_H)

        Returns
        -------
        TimeslotOutput
            Output containing: posterior state of TimeslotState (τ')
        """

        return TimeslotOutput(
            post_state=TimeslotState(
                number=header.timeslot
            )
        )

    def retrieve_state(self) -> TimeslotState:
        value = self.retrieve()
        return TimeslotState.from_jam_bytes(JamBytes(value))


class Entropy(StateComponent):
    component_id = 6

    def state_transition(
            self,
            header: Header,
            pre_state_timeslot: TimeslotState,
            pre_state_entropy: EntropyState
    ) -> EntropyOutput:
        """
        GP-0.3.8-eq:66,67 (η') | State transition function for the state's entropy.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:20 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.8-eq:20 (τ)
        pre_state_entropy: EntropyState
            Input parameter 3 | GP-0.3.8-eq:20 (η)

        Returns
        -------
        EntropyOutput
            Output containing: posterior state of EntropyState (η')
        """

        post_state_entropy = deepcopy(pre_state_entropy)

        # GP-0.3.8-eq:66 (η'[0]) | State transition for first index of the entropy.
        eta_0 = blake2b_256_hash(pre_state_entropy.entropy[0] + header.entropy_source)

        # GP-0.3.8-eq:67 (η'[1-3]) | State transition for last three indices of the entropy.
        # State transition happen on epoch change.
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # GP-0.3.8-eq:67 (`e > e'`) | When epoch changes
            post_state_entropy.entropy = [eta_0] + pre_state_entropy.entropy[:3]
        else:
            post_state_entropy.entropy = [eta_0] + pre_state_entropy.entropy[1:]

        return EntropyOutput(
            post_state=post_state_entropy
        )

    def retrieve_state(self) -> EntropyState:
        value = self.retrieve()
        return EntropyState.from_jam_bytes(JamBytes(value))


class ValidatorQueue(StateComponent):
    """
    ValidatorQueue has no native STF. STF is delegated to a particular PrivilegedService.
    """
    component_id = 7

    def retrieve_state(self) -> ValidatorQueueState:
        value = self.retrieve()
        return ValidatorQueueState.from_jam_bytes(JamBytes(value))


class ValidatorPool(StateComponent):
    component_id = 8

    def state_transition(
            self,
            header: Header,
            pre_state_timeslot: TimeslotState,
            pre_state_validator_pool: ValidatorPoolState,
            pre_state_safrole: SafroleState
    ) -> ValidatorPoolOutput:
        """
        GP-0.3.8-eq:57 (κ') | State transition function for the state's current validator set. Occurs on epoch change.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:21 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.8-eq:21 (τ)
        pre_state_validator_pool: ValidatorPoolState
            Input parameter 3 | GP-0.3.8-eq:21 (κ)
        pre_state_safrole: SafroleState
            Input parameter 4 | GP-0.3.8-eq:21 (η)

        Returns
        -------
        ValidatorPoolOutput
            Output containing: posterior state of ValidatorPoolState (κ')
        """
        post_state_validator_pool = deepcopy(pre_state_validator_pool)

        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            post_state_validator_pool.validators = pre_state_safrole.validators

        return ValidatorPoolOutput(
            post_state=post_state_validator_pool
        )

    def retrieve_state(self) -> ValidatorPoolState:
        value = self.retrieve()
        return ValidatorPoolState.from_jam_bytes(JamBytes(value))


class ValidatorArchive(StateComponent):
    component_id = 9

    def state_transition(
            self,
            header: Header,
            pre_state_timeslot: TimeslotState,
            pre_state_validator_archive: ValidatorArchiveState,
            pre_state_validator_pool: ValidatorPoolState
    ) -> ValidatorArchiveOutput:
        """
        GP-0.3.8-eq:57 (λ') | State transition function for the state's archived validator set. Occurs on epoch change.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:22 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.8-eq:22 (τ)
        pre_state_validator_archive: ValidatorArchiveState
            Input parameter 3 | GP-0.3.8-eq:22 (λ)
        pre_state_validator_pool: ValidatorPoolState
            Input parameter 4 | GP-0.3.8-eq:22 (κ)

        Returns
        -------
        ValidatorArchiveOutput
            Output containing: posterior state of ValidatorArchiveState (λ')
        """
        post_state_validator_archive = deepcopy(pre_state_validator_archive)

        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Update prior epoch validators GP-0.3.8-eq:57
            post_state_validator_archive.validators = pre_state_validator_pool.validators

        return ValidatorArchiveOutput(
            post_state=post_state_validator_archive
        )

    def retrieve_state(self) -> ValidatorArchiveState:
        value = self.retrieve()
        return ValidatorArchiveState.from_jam_bytes(JamBytes(value))


class Safrole(StateComponent):
    component_id = 4

    def __init__(self, storage_engine: StorageInterface, ring_data: bytes):
        super().__init__(storage_engine)
        self.ring_data = ring_data
        self.post_state_safrole = None

    def create_ticket_body(self, ticket_data, ring_public_keys, entropy: bytes) -> TicketBody:
        if ticket_data.attempt not in [0, 1]:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_attempt)

        # GP-0.3.8-eq:75
        vrf_input_data = b"jam_ticket_seal"  # GP-0.3.8-eq:64
        vrf_input_data += entropy
        vrf_input_data += int.to_bytes(ticket_data.attempt, byteorder='little', length=1)

        aux_data = b''

        try:
            ring_vrf_output = ring_vrf_verify(
                self.ring_data, ring_public_keys, vrf_input_data, aux_data, ticket_data.signature
            )
        except ValueError as e:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    def state_transition(
            self,
            header: Header,
            pre_state_timeslot: TimeslotState,
            extrinsic_tickets: List[TicketEnvelope],
            pre_state_safrole: SafroleState,
            pre_state_validator_queue: ValidatorQueueState,
            post_state_entropy: EntropyState,
            post_state_validator_pool: ValidatorPoolState,
            post_state_disputes = DisputesState
    ) -> SafroleOutput:
        """
        GP-0.3.8-eq:57,59,60 (γ') | State transition function for the state's Safrole data.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:19 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.8-eq:19 (τ)
        extrinsic_tickets: List[TicketEnvelope]
            Input parameter 3 | GP-0.3.8-eq:19 (bold_E_T)
        pre_state_safrole: SafroleState
            Input parameter 4 | GP-0.3.8-eq:19 (γ)
        pre_state_validator_queue: ValidatorQueueState
            Input parameter 5| GP-0.3.8-eq:19 (ι)
        post_state_entropy: EntropyState
            Input parameter 6 | GP-0.3.8-eq:19 (η')
        post_state_validator_pool: ValidatorPoolState
            Input parameter 7 | GP-0.3.8-eq:19 (κ')
        post_state_disputes: DisputesState
            Input parameter 5 | GP-0.4.5-eq:19 (ψ')
        Returns
        -------
        SafroleOutput
            Output containing: Posterior state of SafroleState (γ') and optional Outputmarks
        """
        self.post_state_safrole = deepcopy(pre_state_safrole)

        # GP-0.3.8-eq:74
        if self.slot_phase_index(header.timeslot) < gp_const.TICKET_SUBMISSION_END_SLOT:
            # Min 0, max 16 tickets
            if len(extrinsic_tickets) > gp_const.MAXIMUM_EXTRINSIC_TICKETS:  # constant_K=16
                raise StateTransitionError(SafroleErrorCode.too_many_tickets)
        else:
            if len(extrinsic_tickets) > 0:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT:
                raise StateTransitionError(SafroleErrorCode.unexpected_ticket)

        if len(extrinsic_tickets) > 0:

            # Check for duplicate ticket_data; GP-0.3.8-eq:77
            if list_has_duplicates(extrinsic_tickets):
                raise StateTransitionError(SafroleErrorCode.duplicate_ticket)

            ring_public_keys = [v.bandersnatch for v in self.post_state_safrole.validators]

            input_tickets = []

            # Validate extrinsic
            for idx, ticket_data in enumerate(extrinsic_tickets):

                ticket = self.create_ticket_body(ticket_data, ring_public_keys, post_state_entropy.entropy[2])

                # Check if ticket already exists
                if ticket in self.post_state_safrole.ticket_accumulator:
                    # GP-0.3.8-eq:78
                    raise StateTransitionError(SafroleErrorCode.duplicate_ticket)
                else:
                    input_tickets.append(ticket)

            # Check if tickets are in order: GP-0.3.8-eq:77
            if not self.tickets_in_order(input_tickets):
                raise StateTransitionError(SafroleErrorCode.bad_ticket_order)

            # Add tickets to ticket accumulator, sort and limit: GP-0.3.8-eq:78,79
            self.post_state_safrole.ticket_accumulator += input_tickets
            self.post_state_safrole.ticket_accumulator = sorted(
                self.post_state_safrole.ticket_accumulator, key=lambda t: t.id
            )[:gp_const.EPOCH_TIMESLOTS]

        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        if (not self.is_epoch_change(pre_state_timeslot.number, header.timeslot) and
                self.slot_phase_index(header.timeslot) >= gp_const.TICKET_SUBMISSION_END_SLOT):
            # Ticket mark only when accumulator is saturated # GP-0.3.8-eq:72
            if len(self.post_state_safrole.ticket_accumulator) == gp_const.EPOCH_TIMESLOTS:
                # GP-0.3.2-ref:70
                tickets_mark = reorder_list_outside_in(deepcopy(self.post_state_safrole.ticket_accumulator))

        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Epoch change

            # Update Validator keys for the following epoch. # GP-0.3.8-eq:57
            # Apply key_nullifier-function (Φ). This function substitutes offenders with null keys. GP-0.3.8-eq:58
            self.post_state_safrole.validators = self.check_offenders(
                validators=deepcopy(pre_state_validator_queue.validators),
                offenders=post_state_disputes.offenders
            )

            # Clear tickets mark
            tickets_mark = None

            # Create epoch mark
            epoch_mark = EpochMark(
                entropy=post_state_entropy.entropy[1],
                validators=[validator.bandersnatch for validator in self.post_state_safrole.validators]
            )

            # Update Sealing-key series of the current epoch.
            if self.enact_fallback_method(pre_state_timeslot.number, header.timeslot):
                # Determine fallback keys according to # GP-0.3.8-eq:70
                validators = []
                for n in range(gp_const.EPOCH_TIMESLOTS):
                    blake_hash = blake2b_256_hash(
                        post_state_entropy.entropy[2] + int.to_bytes(
                            n, length=4, byteorder='little'
                        )
                    )
                    validator_idx = int.from_bytes(
                        blake_hash[:4], byteorder='little'
                    ) % len(post_state_validator_pool.validators)
                    validators.append(post_state_validator_pool.validators[validator_idx].bandersnatch)

                self.post_state_safrole.slot_sealer_series = SlotSealerSeries(keys=validators)
            else:
                # When ticket accumulator is saturated and ticket mark is generated # GP-0.3.2-ref:69
                self.post_state_safrole.slot_sealer_series = SlotSealerSeries(
                    tickets=reorder_list_outside_in(deepcopy(self.post_state_safrole.ticket_accumulator))
                )

            # Update ring commitment using O(); GP-0.3.8-eq:57
            self.post_state_safrole.ring_commitment = ring_commitment(
                self.ring_data, [v.bandersnatch for v in self.post_state_safrole.validators]
            )

            # Clear ticket accumulator
            self.post_state_safrole.ticket_accumulator = []

        return SafroleOutput(
            post_state=self.post_state_safrole,
            epoch_mark=epoch_mark,
            tickets_mark=tickets_mark
        )

    def enact_fallback_method(self, pre_time_slot: int, post_time_slot: int) -> bool:
        return (
            # Not a full tickets accumulator
            len(self.post_state_safrole.ticket_accumulator) != gp_const.EPOCH_TIMESLOTS
            # No Ticket marker generated
            or self.slot_phase_index(pre_time_slot) < gp_const.TICKET_SUBMISSION_END_SLOT
            # Whole epoch is skipped
            or self.epoch_number(post_time_slot) - self.epoch_number(pre_time_slot) > 1
        )

    @staticmethod
    def tickets_in_order(tickets: List[TicketBody]) -> bool:
        ticket_ids = [t.id for t in tickets]
        return all(x <= y for x, y in zip(ticket_ids, ticket_ids[1:]))

    def retrieve_state(self) -> SafroleState:
        value = self.retrieve()
        return SafroleState.from_jam_bytes(JamBytes(value))

    def check_offenders(self, validators: List[ValidatorData], offenders: List[bytes]):
        """
        GP-0.3.8-eq:58
        """
        checked_validators = []
        for v in validators:
            if v.ed25519 in offenders:
                v.bandersnatch = bytes(32)
                v.ed25519 = bytes(32)
            checked_validators.append(v)

        return checked_validators



class AuthorizerQueues(StateComponent):
    """
    AuthorizerQueues has no native STF. STF is delegated to a particular PrivilegedService.
    """
    component_id = 2

    def retrieve_state(self) -> AuthorizerQueuesState:
        value = self.retrieve()
        return AuthorizerQueuesState.from_jam_bytes(JamBytes(value))


class AuthorizerPools(StateComponent):
    component_id = 1

    def state_transition(
            self,
            header: Header,
            extrinsic_guarantees: List[Guarantee],
            post_state_authorizer_queues: AuthorizerQueuesState,
            pre_state_authorizer_pools: AuthorizerPoolsState
    ) -> AuthorizerPoolsOutput:
        """
        GP-0.3.8-eq:85,86 (α') | State transition function for the state's authorizer pools.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:29 (bold_H)
        extrinsic_guarantees: List[Guarantee]
            Input parameter 2 | GP-0.3.8-eq:29 (bold_E_G)
        post_state_authorizer_queues: AuthorizerQueuesState
            Input parameter 3 | GP-0.3.8-eq:29 (φ')
        pre_state_authorizer_pools: AuthorizerPoolsState
            Input parameter 4 | GP-0.3.8-eq:29 (α)

        Returns
        -------
        AuthorizerPoolsOutput
            Output containing: Posterior state of AuthorizerPoolsState (α')
        """
        # Todo: properly set post_state by implementing STF
        post_state_authorizer_pools = pre_state_authorizer_pools
        return AuthorizerPoolsOutput(
            post_state=post_state_authorizer_pools
        )

    def retrieve_state(self) -> AuthorizerPoolsState:
        value = self.retrieve()
        return AuthorizerPoolsState.from_jam_bytes(JamBytes(value))


class RecentHistory(StateComponent):
    component_id = 3

    def state_transition_intermediate(
            self,
            header: Header,
            pre_state_recent_history: RecentHistoryState
    ) -> RecentHistoryIntermediateOutput:
        """
        GP-0.3.8-eq:81 (β†) | Intermediate state transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:17 (bold_H)
        pre_state_recent_history: RecentHistoryState
            Input parameter 2 | GP-0.3.8-eq:17 (β)

        Returns
        -------
        RecentHistoryIntermediateOutput
            Output containing: Intermediate state of RecentHistoryState (β†)
        """
        intermediate_state_recent_history = deepcopy(pre_state_recent_history)

        if len(pre_state_recent_history.recent_history) > 0:
            intermediate_state_recent_history.recent_history[-1].state_root = header.parent_state_root

        # return intermediate_state_recent_history
        return RecentHistoryIntermediateOutput(
            intermediate_state=intermediate_state_recent_history
        )

    def state_transition(
            self,
            header: Header,
            extrinsic_guarantees: List[Guarantee],
            intermediate_state_recent_history: RecentHistoryState,
            accumulate_root: bytes
    ) -> RecentHistoryOutput:
        """
        GP-0.3.8-eq:83 (β') | State transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.8-eq:18 (bold_H)
        extrinsic_guarantees: List[Guarantee]
            Input parameter 2 | GP-0.3.8-eq:18 (bold_E_G)
        intermediate_state_recent_history: RecentHistoryState
            Input parameter 3 | GP-0.3.8-eq:18 (β†)
        # TODO: Create Dataclass for BeefyCommitmentMap GP-0.3.8-eq:163
        beefy_commitment_map: BeefyCommitmentMap
            Input parameter 4 | GP-0.3.8-eq:18 (bold_C)

        Returns
        -------
        RecentHistoryOutput
            Output containing: Posterior state of RecentHistoryState (β')
        """
        post_state_recent_history = deepcopy(intermediate_state_recent_history)

        work_report_hashes = [g.report.package_spec.hash for g in extrinsic_guarantees]

        # No more work reports than number of cores GP-0.3.8-eq:80
        if work_report_hashes and len(work_report_hashes) > gp_const.CORE_COUNT:
            raise StateTransitionError(f"Work reports must be less than number of cores ({gp_const.CORE_COUNT})")

        if len(intermediate_state_recent_history.recent_history) > 0:
            mmr_peaks = copy(post_state_recent_history.recent_history[-1].mmr.peaks)
        else:
            mmr_peaks = []

        # Extend MMR
        mmr = MerkleMountainRange(mmr_peaks)
        mmr.insert(accumulate_root)

        recent_block = RecentBlock(
            header_hash=header.hash,
            mmr=Mmr(
                peaks=mmr.peaks
            ),
            state_root=bytes(32),
            reported=work_report_hashes
        )

        post_state_recent_history.recent_history.append(recent_block)

        if len(post_state_recent_history.recent_history) > gp_const.HISTORY:
            # Limit reached, delete first (oldest) item in block history
            post_state_recent_history.recent_history.pop(0)

        return RecentHistoryOutput(
            post_state=post_state_recent_history
        )

    def retrieve_state(self) -> RecentHistoryState:
        value = self.retrieve()
        return RecentHistoryState.from_jam_bytes(JamBytes(value))


class Assurances(StateComponent):
    component_id = 10

    def state_transition_after_disputes(
            self,
            extrinsic_disputes: ExtrinsicDisputes,
            pre_state_assurances: AssurancesState
    ) -> AssurancesAfterDisputesOutput:
        """
        GP-0.3.8-eq:110 (ρ†) | Intermediate state transition function for the state's assurances that processes
        disputes extrinsic.

        Parameters
        ----------
        extrinsic_disputes: ExtrinsicDisputes
            Input parameter 1 | GP-0.3.8-eq:25 (bold_E_D)
        pre_state_assurances: AssurancesState
            Input parameter 2 | GP-0.3.8-eq:25 (ρ)

        Returns
        -------
        AssurancesAfterDisputesOutput
            Output Containing: Intermediate state after processing disputes of AssurancesState (ρ†)
        """
        # Todo: properly set intermediate_state_after_disputes by implementing STF
        intermediate_state_assurances_after_disputes = pre_state_assurances
        return AssurancesAfterDisputesOutput(
            intermediate_state_after_disputes=intermediate_state_assurances_after_disputes
        )

    def state_transition_after_assurances(
            self,
            extrinsic_assurances: List[Assurance],
            intermediate_state_assurances_after_disputes: AssurancesState
    ) -> AssurancesAfterAssurancesOutput:
        """
        GP-0.3.8-eq:130 (ρ‡) | Intermediate state transition function for the state's assurances that processes
        assurances extrinsic.

        Parameters
        ----------
        extrinsic_assurances: List[Assurance]
            Input parameter 1 | GP-0.3.8-eq:26 (bold_E_A)
        intermediate_state_assurances_after_disputes: AssurancesState
            Input parameter 2 | GP-0.3.8-eq:26 (ρ†)

        Returns
        -------
        AssurancesAfterAssurancesOutput
            Output Containing: Intermediate state after processing assurances of AssurancesState (ρ‡)
        """
        # Todo: properly set intermediate_state_assurances_after_assurances by implementing STF
        intermediate_state_assurances_after_assurances = intermediate_state_assurances_after_disputes
        return AssurancesAfterAssurancesOutput(
            intermediate_state_after_assurances=intermediate_state_assurances_after_assurances
        )

    def state_transition_after_guarantees(
            self,
            extrinsic_guarantees: List[Guarantee],
            intermediate_state_assurances_after_assurances: AssurancesState,
            pre_state_validator_pool: ValidatorPoolState,
            post_state_timeslot: TimeslotState
    ) -> AssurancesAfterGuaranteesOutput:
        """
        GP-0.3.8-eq:152 (ρ') | State transition function for the state's assurances that processes guarantees extrinsic.

        Parameters
        ----------
        extrinsic_guarantees: List[Guarantee]
            Input parameter 1 | GP-0.3.8-eq:27 (bold_E_G)
        intermediate_state_assurances_after_assurances: AssurancesState
            Input parameter 2 | GP-0.3.8-eq:27 (ρ‡)
        pre_state_validator_pool: ValidatorPoolState
            Input parameter 3 | GP-0.3.8-eq:27 (κ)
        post_state_timeslot: TimeslotState
            Input parameter 4 | GP-0.3.8-eq:27 (τ')

        Returns
        -------
        AssurancesAfterGuaranteesOutput
            Output containing: Posterior state after processing guarantees of AssurancesState (ρ')
        """
        # Todo: properly set post_state by implementing STF
        post_state_assurances = intermediate_state_assurances_after_assurances
        return AssurancesAfterGuaranteesOutput(
            post_state=post_state_assurances
        )

    def retrieve_state(self) -> AssurancesState:
        value = self.retrieve()
        return AssurancesState.from_jam_bytes(JamBytes(value))


class PrivilegedServices(StateComponent):
    """
    PrivilegedServices has no native STF. STF is delegated to a particular PrivilegedService.
    """
    component_id = 12

    def retrieve_state(self) -> PrivilegedServicesState:
        value = self.retrieve()
        return PrivilegedServicesState.from_jam_bytes(JamBytes(value))


class Disputes(StateComponent):
    component_id = 5

    def state_transition(
            self,
            extrinsic_disputes: ExtrinsicDisputes,
            pre_state_disputes: DisputesState
    ) -> DisputesOutput:
        """
        GP-0.3.8-eq:111,112,113,114 (ψ') | State transition function for the state's disputes.

        Parameters
        ----------
        extrinsic_disputes: ExtrinsicDisputes
            Input parameter 1 | GP-0.3.8-eq:23 (bold_E_D)
        pre_state_disputes: DisputesState
            Input parameter 2 | GP-0.3.8-eq:23 (ψ)

        Returns
        -------
        DisputesOutput
            Output containing: Posterior state of DisputesState (ψ')
        """

        self.output = DisputesOutput(
            post_state=deepcopy(pre_state_disputes), offenders_mark=[]
        )

        if not self.are_faults_verdict_correct(extrinsic_disputes.faults):
            raise StateTransitionError(DisputesErrorCode.fault_verdict_wrong)

        # Check if all culprits have valid signatures
        if not all(c.has_valid_signature() for c in extrinsic_disputes.culprits):
            raise StateTransitionError(DisputesErrorCode.bad_signature)

        # Check if all faults have valid signatures
        if not all(f.has_valid_signature() for f in extrinsic_disputes.faults):
            raise StateTransitionError(DisputesErrorCode.bad_signature)

        # Check if verdicts are sorted
        if not self.are_verdicts_sorted(extrinsic_disputes.verdicts):
            raise StateTransitionError(DisputesErrorCode.verdicts_not_sorted_unique)

        if self.has_duplicate_report_hashes(extrinsic_disputes.verdicts):
            raise StateTransitionError(DisputesErrorCode.verdicts_not_sorted_unique)

        # Process verdicts
        for verdict in extrinsic_disputes.verdicts:

            if self.is_already_judged(verdict):
                raise StateTransitionError(DisputesErrorCode.already_judged)

            # Check if judgements are sorted and unique
            if not self.are_judgements_sorted(verdict.votes) or self.has_duplicate_judgements(verdict.votes):
                raise StateTransitionError(DisputesErrorCode.judgements_not_sorted_unique)

            # Process verdict
            if verdict.is_good():
                self.check_valid_faults_count(extrinsic_disputes.faults, verdict.target)
                bisect.insort(self.output.post_state.good_set, verdict.target)

            elif verdict.is_bad():
                self.check_valid_culprits_count(extrinsic_disputes.culprits, verdict.target)
                bisect.insort(self.output.post_state.bad_set, verdict.target)

            elif verdict.is_wonky():
                bisect.insort(self.output.post_state.wonky_set, verdict.target)
            else:
                raise StateTransitionError(DisputesErrorCode.bad_vote_split)

        # Process culprits
        if not self.are_culprits_sorted(extrinsic_disputes.culprits):
            raise StateTransitionError(DisputesErrorCode.culprits_not_sorted_unique)

        for culprit in extrinsic_disputes.culprits:
            self.add_culprit(culprit)

        # Process faults
        if not self.are_faults_sorted(extrinsic_disputes.faults):
            raise StateTransitionError(DisputesErrorCode.faults_not_sorted_unique)

        for fault in extrinsic_disputes.faults:
            self.add_fault(fault)

        return self.output

    @classmethod
    def has_valid_judgement_signatures(cls, verdict: Verdict, validators: List[ValidatorData]) -> bool:
        """
        GP-0.3.8-eq:98

        Parameters
        ----------
        verdict
        validators

        Returns
        -------

        """
        for judgement in verdict.votes:
            keypair = Keypair.from_public_key(validators[judgement.index].ed25519)
            if not keypair.verify(judgement.get_signing_context() + verdict.target, judgement.signature):
                return False
        return True

    def is_already_judged(self, verdict: Verdict) -> bool:
        return (
                verdict.target in self.output.post_state.good_set or
                verdict.target in self.output.post_state.bad_set or
                verdict.target in self.output.post_state.wonky_set
        )

    @staticmethod
    def are_judgements_sorted(votes: List[Judgement]) -> bool:
        """
        GP-0.3.8-eq:105

        Parameters
        ----------
        votes

        Returns
        -------
        bool
        """
        return all(votes[i].index <= votes[i + 1].index for i in range(len(votes) - 1))

    @staticmethod
    def has_duplicate_judgements(votes: List[Judgement]) -> bool:
        """
        GP-0.3.8-eq:105

        Parameters
        ----------
        votes

        Returns
        -------
        bool
        """

        seen_indices = []
        for vote in votes:
            if vote.index in seen_indices:
                return True
            else:
                seen_indices.append(vote.index)
        return False

    @staticmethod
    def are_verdicts_sorted(verdicts: List[Verdict]) -> bool:
        """
        GP-0.3.8-eq:102

        Parameters
        ----------
        verdicts

        Returns
        -------
        bool
        """
        return all(verdicts[i].target <= verdicts[i + 1].target for i in range(len(verdicts) - 1))

    @staticmethod
    def are_culprits_sorted(culprits: List[Culprit]) -> bool:
        """
        GP-0.3.8-eq:103

        Parameters
        ----------
        culprits

        Returns
        -------
        bool
        """
        return all(culprits[i].key <= culprits[i + 1].key for i in range(len(culprits) - 1))

    @staticmethod
    def are_faults_sorted(faults: List[Fault]) -> bool:
        """
        GP-0.3.8-eq:103

        Parameters
        ----------
        faults

        Returns
        -------
        bool
        """
        return all(faults[i].key <= faults[i + 1].key for i in range(len(faults) - 1))

    @staticmethod
    def are_faults_verdict_correct(faults: List[Fault]) -> bool:
        return not any(f.vote for f in faults)

    def add_offender(self, offender_key: bytes):
        if offender_key in self.output.post_state.offenders:
            raise StateTransitionError(DisputesErrorCode.offender_already_reported)
        self.output.offenders_mark.append(offender_key)
        bisect.insort(self.output.post_state.offenders, offender_key)

    def add_culprit(self, culprit: Culprit):

        if culprit.target in self.output.post_state.bad_set:
            self.add_offender(culprit.key)
        else:
            raise StateTransitionError(DisputesErrorCode.culprits_verdict_not_bad)

    def add_fault(self, fault: Fault):

        if fault.target in self.output.post_state.good_set:
            self.add_offender(fault.key)
        else:
            raise StateTransitionError(DisputesErrorCode.fault_verdict_wrong)

    def retrieve_state(self) -> DisputesState:
        value = self.retrieve()
        return DisputesState.from_jam_bytes(JamBytes(value))

    @staticmethod
    def has_duplicate_report_hashes(verdicts: List[Verdict]) -> bool:
        """
        GP-0.3.8-eq:104

        Parameters
        ----------
        verdicts

        Returns
        -------
        bool
        """

        seen_targets = []
        for verdict in verdicts:
            if verdict.target in seen_targets:
                return True
            else:
                seen_targets.append(verdict.target)
        return False

    @staticmethod
    def check_valid_faults_count(faults: List[Fault], report_hash: bytes):
        """
        GP-0.3.8-eq:108

        Parameters
        ----------
        faults
        report_hash

        Returns
        -------

        """
        if sum(1 for f in faults if f.target == report_hash) == 0:
            raise StateTransitionError(DisputesErrorCode.not_enough_faults)

    @staticmethod
    def check_valid_culprits_count(culprits: List[Culprit], report_hash: bytes):
        """
        GP-0.3.8-eq:109

        Parameters
        ----------
        culprits
        report_hash

        Returns
        -------

        """
        if sum(1 for c in culprits if c.target == report_hash) < 2:
            raise StateTransitionError(DisputesErrorCode.not_enough_culprits)

    @classmethod
    def validate_extrinsic_disputes(cls, disputes: ExtrinsicDisputes, current_epoch: int,
                                    current_validators: List[ValidatorData], prev_validators: List[ValidatorData]):
        for verdict in disputes.verdicts:

            if current_epoch - verdict.age == 0:
                validators = current_validators
            elif current_epoch - verdict.age == 1:
                validators = prev_validators
            else:
                raise BlockValidationError(DisputesErrorCode.bad_judgement_age)

            if not cls.has_valid_judgement_signatures(verdict, validators):
                raise BlockValidationError(DisputesErrorCode.bad_signature)


class Statistics(StateComponent):
    component_id = 13

    def state_transition(
            self,
            extrinsic_guarantees: List[Guarantee],
            extrinsic_preimages: List[Preimage],
            extrinsic_assurances: List[Assurance],
            extrinsic_tickets: List[TicketEnvelope],
            pre_state_timeslot: TimeslotState,
            post_state_timeslot: TimeslotState,
            post_state_validator_pool: ValidatorPoolState,
            pre_state_statistics: StatisticsState,
            header: Header
    ) -> StatisticsOutput:
        """
        GP-0.3.8-eq:171,172 (π') | State transition function for the state's statistics.

        Parameters
        ----------
        extrinsic_guarantees: List[Guarantee]
            Input parameter 1 | GP-0.3.8-eq:30 (bold_E_G)
        extrinsic_preimages: List[Preimage]
            Input parameter 2 | GP-0.3.8-eq:30 (bold_E_P)
        extrinsic_assurances: List[Assurance]
            Input parameter 3 | GP-0.3.8-eq:30 (bold_E_A)
        extrinsic_tickets: List[TicketEnvelope]
            Input parameter 4 | GP-0.3.8-eq:30 (bold_E_T)
        pre_state_timeslot: TimeslotState
            Input parameter 5 | GP-0.3.8-eq:30 (τ)
        post_state_timeslot: TimeslotState
            Input parameter 6 | GP-0.3.8-eq:30 (τ')
        post_state_validator_pool: ValidatorPoolState
            Input parameter 7 | GP-0.3.8-eq:30 (κ')
        pre_state_statistics: StatisticsState
            Input parameter 8 | GP-0.3.8-eq:30 (π)
        header: Header
            Input parameter 9 | GP-0.3.8-eq:30 (bold_H)

        Returns
        -------
        StatisticsOutput
            Output containing: Posterior state of StatisticsState (π')
        """
        # Todo: properly set post_state by implementing STF
        post_state = pre_state_statistics
        return StatisticsOutput(
            post_state=post_state
        )

    def retrieve_state(self) -> StatisticsState:
        value = self.retrieve()
        return StatisticsState.from_jam_bytes(JamBytes(value))


class Services(StateComponent):
    # component_id = 255

    def state_transition_after_preimages(
            self,
            extrinsic_preimages: List[Preimage],
            pre_state_services: ServicesState,
            post_state_timeslot: TimeslotState
    ) -> ServicesAfterPreimagesOutput:
        """
        GP-0.3.8-eq:156 (δ†) | Intermediate state transition function after processing Preimages for the state's
        services.

        Parameters
        ----------
        extrinsic_preimages: List[Preimage]
            Input parameter 1 | GP-0.3.8-eq:24 (bold_E_P)
        pre_state_services: ServicesState
            Input parameter 2 | GP-0.3.8-eq:24 (δ)
        post_state_timeslot: TimeslotState
            Input parameter 3 | GP-0.3.8-eq:24 (τ')

        Returns
        -------
        ServicesAfterPreimagesOutput
            Output containing: Intermediate state after processing Preimages of ServicesState (δ†)
        """
        # Todo: properly set intermediate_state_services_after_preimages by implementing STF
        intermediate_state_services_after_preimages = pre_state_services
        return ServicesAfterPreimagesOutput(
            intermediate_state_after_preimages=intermediate_state_services_after_preimages
        )

    # Todo: Add additional intermediate STF for δ‡ (Services after accumulation, but before transfers as per
    #  GP-0.3.8-eq:166. State Transition Dependency Graph does not currently list a distinct STF for this. This may
    #  impact input parameters of the main STF.

    def state_transition(
            self,
            extrinsic_assurances: List[Assurance],
            post_state_assurances: AssurancesState,
            intermediate_state_services_after_preimages: ServicesState,
            pre_state_privileged_services: PrivilegedServicesState,
            pre_state_validator_queue: ValidatorQueueState,
            pre_state_authorizer_queues: AuthorizerQueuesState
    ) -> ServicesOutput:
        """
        GP-0.3.8-eq:168 (δ') | State transition function for the state's services.

        Parameters
        ----------
        extrinsic_assurances: List[Assurance]
            Input parameter 1 | GP-0.3.8-eq:28 (bold_E_A)
        post_state_assurances: AssurancesState
            Input parameter 2 | GP-0.3.8-eq:28 (ρ')
        intermediate_state_services_after_preimages: ServicesState
            Input parameter 3 | GP-0.3.8-eq:28 (δ†)
        pre_state_privileged_services: PrivilegedServicesState
            Input parameter 4 | GP-0.3.8-eq:28 (χ)
        pre_state_validator_queue: ValidatorQueueState
            Input parameter 5 | GP-0.3.8-eq:28 (ι)
        pre_state_authorizer_queues: AuthorizerQueuesState
            Input parameter 6 | GP-0.3.8-eq:28 (φ)

        Returns
        -------
        ServicesOutput
            Output containing: posterior state of ServicesState (δ') and BeefyCommitmentMap.
        """
        # Todo: properly set post_state_services by implementing STF
        post_state_services = intermediate_state_services_after_preimages
        return ServicesOutput(
            post_state=post_state_services,
            # Todo: BeefyCommitmentMap Dictionary is a result of service accumulation and is used in STF for
            #  RecentHistory.
            beefy_commitment_map=BeefyCommitmentMap({})
        )

    def retrieve_state(self) -> ServicesState:
        value = self.retrieve()
        return ServicesState.from_jam_bytes(JamBytes(value))
