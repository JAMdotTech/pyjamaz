from copy import deepcopy, copy
from typing import List

from bandersnatch_vrfs import ring_vrf_verify, ring_commitment

import pyjamaz.graypaper_constants as gp_const
from jamcodec.base import JamBytes
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import MerkleMountainRange
from pyjamaz.storage import StorageInterface
from pyjamaz.types.safrole import SlotSealerSeries
from pyjamaz.types.stf_output import SafroleErrorCode, SafroleOutput

from pyjamaz.state.base import StateComponent
from pyjamaz.state.exceptions import StateTransitionError
from pyjamaz.types.block import Block, TicketBody, EpochMark, OutputMarks, Header, TicketEnvelope, ExtrinsicDisputes, \
    Guarantee
from pyjamaz.types.state import TimeslotState, EntropyState, ValidatorPoolState, SafroleState, \
    ValidatorQueueState, ValidatorArchiveState, AuthorizerQueuesState, AuthorizerPoolsState, RecentHistoryState, \
    AssurancesState, PrivilegedServicesState, DisputesState, ServicesState, StatisticsState, RecentBlock, Mmr
from pyjamaz.utils import reorder_list_outside_in, list_has_duplicates


class Timeslot(StateComponent):
    component_id = 11

    def state_transition(self, header: Header):
        """
        GP-0.3.6-eq:45 (greek_TAU_prime | τ') | State transition function for the state's timeslot.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:16 (bold_H)

        Returns
        -------
        post_state_timeslot: TimeslotState
            Posterior state of TimeslotState (greek_TAU_prime | τ')
        """
        if header.timeslot <= self.pre_state.number:
            raise StateTransitionError(SafroleErrorCode.bad_slot)

        self.post_state.number = header.timeslot

    def is_epoch_change(self):
        """
        GP-0.3.6-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.
        """
        return self.post_state.epoch_number() != self.pre_state.epoch_number()

    def retrieve_state(self) -> TimeslotState:
        value = self.retrieve()
        return TimeslotState.from_jam_bytes(JamBytes(value))


class Entropy(StateComponent):
    component_id = 6

    def state_transition(self, header: Header, pre_state_timeslot: TimeslotState):
        """
        GP-0.3.6-eq:66,67 (greek_ETA_prime | η') | State transition function for the state's entropy.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:20 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.6-eq:20 (greek_TAU | τ)
        # pre_state_entropy: EntropyState
        #     Input parameter 3 | GP-0.3.6-eq:20 (greek_ETA | η)

        Returns
        -------
        post_state_entropy: EntropyState
            Posterior state of EntropyState (greek_ETA_prime | η')
        """

        # GP-0.3.6-eq:66 (greek_ETA_prime[0] | η'[0]) | State transition for first index of the entropy.
        eta_0 = blake2b_256_hash(self.pre_state.entropy[0] + header.entropy_source)

        # GP-0.3.6-eq:67 (greek_ETA_prime[1-3] | η'[1-3]) | State transition for last three indices of the entropy.
        # State transition happen on epoch change.
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # GP-0.3.6-eq:67 (`e > e'`) | When epoch changes
            self.post_state.entropy = [eta_0] + self.pre_state.entropy[:3]
        else:
            self.post_state.entropy = [eta_0] + self.pre_state.entropy[1:]

    def retrieve_state(self) -> EntropyState:
        value = self.retrieve()
        return EntropyState.from_jam_bytes(JamBytes(value))


class ValidatorQueue(StateComponent):
    component_id = 7

    # Todo: remove function | STF for the validator queue, is delegated to a privileged service.
    def state_transition(self, block: Block):
        pass

    def retrieve_state(self) -> ValidatorQueueState:
        value = self.retrieve()
        return ValidatorQueueState.from_jam_bytes(JamBytes(value))


class ValidatorPool(StateComponent):
    component_id = 8

    def state_transition(self, header: Header, pre_state_timeslot: TimeslotState, pre_state_safrole: SafroleState,
                         post_state_disputes: DisputesState):
        """
        GP-0.3.6-eq:57 (greek_KAPPA_prime | κ') | State transition function for the state's current validator set.
        Occurs on epoch change.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:21 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.6-eq:21 (greek_TAU | τ)
        # pre_state_validator_pool: ValidatorPoolState
            Input parameter 3 | GP-0.3.6-eq:21 (greek_KAPPA | κ)
        pre_state_safrole: SafroleState
            Input parameter 4 | GP-0.3.6-eq:21 (greek_GAMMA | η)
        post_state_disputes: DisputesState
            Input parameter 5 | GP-0.3.6-eq:21 (greek_PSI_prime | ψ')

        Returns
        -------
        post_state_validator_pool: ValidatorPoolState
            Posterior state of ValidatorPoolState (greek_KAPPA_prime | κ')
        """
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            self.post_state.validators = pre_state_safrole.validators

    def retrieve_state(self) -> ValidatorPoolState:
        value = self.retrieve()
        return ValidatorPoolState.from_jam_bytes(JamBytes(value))


class ValidatorArchive(StateComponent):
    component_id = 9

    def state_transition(self, header: Header, pre_state_timeslot: TimeslotState,
                         pre_state_validator_pool: ValidatorPoolState):
        """
        GP-0.3.6-eq:57 (greek_LAMBDA_prime | λ') | State transition function for the state's archived validator set.
        Occurs on epoch change.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:22 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.6-eq:22 (greek_TAU | τ)
        #pre_state_validator_archive: ValidatorArchiveState
            Input parameter 3 | GP-0.3.6-eq:22 (greek_LAMBDA | λ)
        pre_state_validator_pool: ValidatorPoolState
            Input parameter 4 | GP-0.3.6-eq:22 (greek_KAPPA | κ)

        Returns
        -------
        post_state_validator_archive: ValidatorArchiveState
            Posterior state of ValidatorArchiveState (greek_LAMBDA_prime | λ')
        """
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Update prior epoch validators   GP-0.3.2-eq:58
            self.post_state.validators = pre_state_validator_pool.validators

    def retrieve_state(self) -> ValidatorArchiveState:
        value = self.retrieve()
        return ValidatorArchiveState.from_jam_bytes(JamBytes(value))


class Safrole(StateComponent):
    component_id = 4

    def __init__(self, storage_engine: StorageInterface, ring_data: bytes):
        super().__init__(storage_engine)
        self.ring_data = ring_data

    def create_ticket_body(self, ticket_data, ring_public_keys, entropy: bytes) -> TicketBody:
        if ticket_data.attempt not in [0, 1]:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_attempt)

        # GP-0.3.2-ref:74
        vrf_input_data = b"jam_ticket_seal"  # GP-0.3.2-ref:65
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

    def state_transition(self,
                         header: Header,
                         pre_state_timeslot: TimeslotState,
                         extrinsic_tickets: List[TicketEnvelope],
                         pre_state_validator_queue: ValidatorQueueState,
                         post_state_entropy: EntropyState,
                         post_state_validator_pool: ValidatorPoolState
                         ) -> SafroleOutput:
        """
        GP-0.3.6-eq:57,59,60 (greek_GAMMA_prime | γ') | State transition function for the state's Safrole data.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:19 (bold_H)
        pre_state_timeslot: TimeslotState
            Input parameter 2 | GP-0.3.6-eq:19 (greek_TAU | τ)
        extrinsic_tickets: List[TicketEnvelope]
            Input parameter 3 | GP-0.3.6-eq:19 (bold_E_T)
        # pre_state_safrole: SafroleState
        #     Input parameter 4 | GP-0.3.6-eq:19 (greek_GAMMA | γ)
        pre_state_validator_queue: ValidatorQueueState
            Input parameter 5| GP-0.3.6-eq:19 (greek_IOTA | ι)
        post_state_entropy: EntropyState
            Input parameter 6 | GP-0.3.6-eq:19 (greek_ETA_prime | η')
        post_state_validator_pool: ValidatorPoolState
            Input parameter 7 | GP-0.3.6-eq:19 (greek_KAPPA_prime | κ')

        Returns
        -------
        post_state_safrole: SafroleState
            Posterior state of SafroleState (greek_GAMMA_prime | γ')
        """

        # GP-0.3.2-ref:75
        if self.slot_phase_index(header.timeslot) < gp_const.TICKET_SUBMISSION_END_SLOT:
            # Min 0, max 16 tickets
            if len(extrinsic_tickets) > gp_const.MAXIMUM_EXTRINSIC_TICKETS:  # contant_K=16
                raise StateTransitionError(SafroleErrorCode.too_many_tickets)
        else:
            if len(extrinsic_tickets) > 0:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT:
                raise StateTransitionError(SafroleErrorCode.unexpected_ticket)

        if len(extrinsic_tickets) > 0:

            # Check for duplicate ticket_data; GP-0.3.2-eq:77
            if list_has_duplicates(extrinsic_tickets):
                raise StateTransitionError(SafroleErrorCode.duplicate_ticket)

            ring_public_keys = [v.bandersnatch for v in self.post_state.validators]

            input_tickets = []

            # Validate extrinsic
            for idx, ticket_data in enumerate(extrinsic_tickets):

                ticket = self.create_ticket_body(ticket_data, ring_public_keys, post_state_entropy.entropy[2])

                # Check if ticket already exists
                if ticket in self.post_state.ticket_accumulator:
                    # GP-0.3.2-eq:78
                    raise StateTransitionError(SafroleErrorCode.duplicate_ticket)
                else:
                    input_tickets.append(ticket)

            # Check if tickets are in order: GP-0.3.2-ref:77
            if not self.tickets_in_order(input_tickets):
                raise StateTransitionError(SafroleErrorCode.bad_ticket_order)

            # Add tickets to ticket accumulator, sort and limit: GP-0.3.2-ref:78,79
            self.post_state.ticket_accumulator += input_tickets
            self.post_state.ticket_accumulator = sorted(
                self.post_state.ticket_accumulator, key=lambda t: t.id
            )[:gp_const.EPOCH_TIMESLOTS]

        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        if (not self.is_epoch_change(pre_state_timeslot.number, header.timeslot) and
                self.slot_phase_index(header.timeslot) >= gp_const.TICKET_SUBMISSION_END_SLOT):
            # Ticket mark only when accumulator is saturated # GP-0.3.2-ref:67
            if len(self.post_state.ticket_accumulator) == gp_const.EPOCH_TIMESLOTS:
                tickets_mark = reorder_list_outside_in(deepcopy(self.post_state.ticket_accumulator))  # GP-0.3.2-ref:70

        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Epoch change

            epoch_validator_keys = [
                validator.bandersnatch for validator in pre_state_validator_queue.validators
            ]

            # Clear tickets mark
            tickets_mark = None

            # Create epoch mark
            epoch_mark = EpochMark(
                entropy=post_state_entropy.entropy[1],
                validators=epoch_validator_keys
            )

            # Update Validator keys for the following epoch. # GP-0.3.2-eq:58
            # TODO: apply key_nullifier-function (Φ). This function substitutes offenders with null keys. GP-0.3.2-eq:59
            self.post_state.validators = deepcopy(pre_state_validator_queue.validators)

            # Update Sealing-key series of the current epoch.
            if self.enact_fallback_method(pre_state_timeslot.number, header.timeslot):
                # Determine fallback keys according to # GP-0.3.2-ref:71
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

                self.post_state.slot_sealer_series = SlotSealerSeries(keys=validators)
            else:
                # When ticket acculumator is saturated and ticket mark is generated # GP-0.3.2-ref:70
                self.post_state.slot_sealer_series = SlotSealerSeries(
                    tickets=reorder_list_outside_in(deepcopy(self.post_state.ticket_accumulator))
                )

            # Update ring commitment using O(); GP-0.3.2-eq:58
            self.post_state.ring_commitment = ring_commitment(
                self.ring_data, [v.bandersnatch for v in self.post_state.validators]
            )

            # Clear ticket accumulator
            self.post_state.ticket_accumulator = []

        return SafroleOutput(
            ok=OutputMarks(epoch_mark=epoch_mark, tickets_mark=tickets_mark)
        )

    def enact_fallback_method(self, pre_time_slot: int, post_time_slot: int) -> bool:
        return (
            # Not a full tickets accumulator
                len(self.post_state.ticket_accumulator) != gp_const.EPOCH_TIMESLOTS
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


class AuthorizerQueues(StateComponent):
    component_id = 2

    # Todo: remove function | STF for the authorizer queues, is delegated to a privileged service.
    def state_transition(self, block: Block):
        pass

    def retrieve_state(self) -> AuthorizerQueuesState:
        value = self.retrieve()
        return AuthorizerQueuesState.from_jam_bytes(JamBytes(value))


class AuthorizerPools(StateComponent):
    component_id = 1

    def state_transition(self, block: Block):
        """
        GP-0.3.6-eq:85,86 (greek_ALPHA_prime | α') | State transition function for the state's authorizer pools.

        Parameters
        ----------
        block: Block
            Todo: Remove this input parameter and replace with the following (see below). General remark regarding STFs.
            Refactor at some point to sandbox/isolate STFs to ONLY EXPLICITLY USE parameters to execute STFs. Currently
            the STFs utilize data external to the STF.
        # extrinsic_guarantees: Vec(Guarantee)
            Input parameter 1 | GP-0.3.6-eq:29 (bold_E_G)
        # post_state_authorizer_queues: AuthorizerQueuesState
            Input parameter 2 | GP-0.3.6-eq:29 (greek_PHI_prime | φ')
        # pre_state_authorizer_pools: AuthorizerPoolsState
            Input parameter 3 | GP-0.3.6-eq:29 (greek_ALPHA | α)

        Returns
        -------
        post_state_authorizer_pools: AuthorizerPoolsState
            Posterior state of AuthorizerPoolsState (greek_ALPHA_prime | α')
        """
        pass

    def retrieve_state(self) -> AuthorizerPoolsState:
        value = self.retrieve()
        return AuthorizerPoolsState.from_jam_bytes(JamBytes(value))


class RecentHistory(StateComponent):
    component_id = 3

    def state_transition_intermediate(self, header: Header) -> RecentHistoryState:
        """
        GP-0.3.6-eq:81 (greek_BETA_dagger | β†) | Intermediate state transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:17 (bold_H)
        # pre_state_recent_history: RecentHistoryState
            Input parameter 2 | GP-0.3.6-eq:17 (greek_BETA | β)

        Returns
        -------
        intermediate_state_recent_history: RecentHistoryState
            Intermediate state of RecentHistoryState (greek_BETA_dagger | β†)
        """
        intermediate_state = deepcopy(self.pre_state)

        if len(self.pre_state.recent_history) > 0:
            self.post_state.recent_history[-1].state_root = header.parent_state_root

        return intermediate_state

    def state_transition(self, header: Header, extrinsic_guarantees: List[Guarantee],
                         intermediate_state_recent_history: RecentHistoryState,
                         accumulate_root: bytes):
        """
        GP-0.3.6-eq:83 (greek_BETA_prime | β') | State transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            Input parameter 1 | GP-0.3.6-eq:18 (bold_H)
        extrinsic_guarantees: List[Guarantee]
            Input parameter 2 | GP-0.3.6-eq:18 (bold_E_G)
        intermediate_state_recent_history: RecentHistoryState
            Input parameter 3 | GP-0.3.6-eq:18 (greek_BETA_dagger | β†)
        # TODO: Create Dataclass for BeefyCommitmentMap GP-0.3.6-eq:163
        beefy_commitment_map: BeefyCommitmentMap
            Input parameter 4 | GP-0.3.6-eq:18 (bold_C)

        Returns
        -------
        post_state_recent_history: RecentHistoryState
            Posterior state of RecentHistoryState (greek_BETA_prime | β')
        """

        work_report_hashes = [g.report.package_spec.hash for g in extrinsic_guarantees]

        # No more work reports than number of cores GP-0.3.6-ref:80
        if work_report_hashes and len(work_report_hashes) > gp_const.CORE_COUNT:
            raise StateTransitionError(f"Work reports must be less than number of cores ({gp_const.CORE_COUNT})")

        if len(self.pre_state.recent_history) > 0:
            mmr_peaks = copy(self.post_state.recent_history[-1].mmr.peaks)
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

        self.post_state.recent_history.append(recent_block)

        if len(self.post_state.recent_history) > gp_const.HISTORY:
            # Limit reached, delete first (oldest) item in block history
            self.post_state.recent_history.pop(0)

    def retrieve_state(self) -> RecentHistoryState:
        value = self.retrieve()
        return RecentHistoryState.from_jam_bytes(JamBytes(value))


class Assurances(StateComponent):
    component_id = 10

    def state_transition_disputes(self, block: Block):
        """
        GP-0.3.6-eq:110 (greek_RHO_dagger | ρ†) | Intermediate state transition function for the state's assurances that
        processes disputes.

        Parameters
        ----------
        block: Block
            Todo: Remove this input parameter and replace with the following (see below). General remark regarding STFs.
            Refactor at some point to sandbox/isolate STFs to ONLY EXPLICITLY USE parameters to execute STFs. Currently
            the STFs utilize data external to the STF.
        # extrinsic_disputes: Disputes
            Input parameter 1 | GP-0.3.6-eq:25 (bold_E_D)
        # pre_state_assurances: AssurancesState
            Input parameter 2 | GP-0.3.6-eq:25 (greek_RHO | ρ)

        Returns
        -------
        post_disputes_state_assurances: AssurancesState
            Intermediate state after processing disputes of AssurancesState (greek_RHO_dagger | ρ†)
        """
        pass

    def state_transition_assurances(self, block: Block):
        """
        GP-0.3.6-eq:130 (greek_RHO_doubledagger | ρ‡) | Intermediate state transition function for the state's assurances
        that processes assurances.

        Parameters
        ----------
        block: Block
            Todo: Remove this input parameter and replace with the following (see below). General remark regarding STFs.
            Refactor at some point to sandbox/isolate STFs to ONLY EXPLICITLY USE parameters to execute STFs. Currently
            the STFs utilize data external to the STF.
        # extrinsic_assurances: Vec(Assurance)
            Input parameter 1 | GP-0.3.6-eq:26 (bold_E_A)
        # post_disputes_state_assurances: AssurancesState
            Input parameter 2 | GP-0.3.6-eq:26 (greek_RHO_dagger | ρ†)

        Returns
        -------
        post_assurances_state_assurances: AssurancesState
            Posterior state of AssurancesState (greek_RHO_doubledagger | ρ‡)
        """
        pass

    def state_transition_guarantees(self, block: Block):
        """
        GP-0.3.6-eq:152 (greek_RHO_prime | ρ') | State transition function for the state's assurances.

        Parameters
        ----------
        block: Block
            Todo: Remove this input parameter and replace with the following (see below). General remark regarding STFs.
            Refactor at some point to sandbox/isolate STFs to ONLY EXPLICITLY USE parameters to execute STFs. Currently
            the STFs utilize data external to the STF.
        # extrinsic_guarantees: Vec(Guarantee)
            Input parameter 1 | GP-0.3.6-eq:27 (bold_E_G)
        # post_assurances_state_assurances: AssurancesState
            Input parameter 2 | GP-0.3.6-eq:27 (greek_RHO_doubledagger | ρ‡)
        # pre_state_validator_pool: ValidatorPoolState
            Input parameter 3 | GP-0.3.6-eq:27 (greek_KAPPA | κ)
        # post_state_timeslot: TimeslotState
            Input parameter 4 | GP-0.3.6-eq:27 (greek_TAU_prime | τ')

        Returns
        -------
        post_state_assurances: AssurancesState
            Posterior state of AssurancesState (greek_RHO_prime | ρ')
        """
        pass

    def retrieve_state(self) -> AssurancesState:
        value = self.retrieve()
        return AssurancesState.from_jam_bytes(JamBytes(value))


class PrivilegedServices(StateComponent):
    component_id = 12

    # Todo: remove function | STF for the privileged services, is delegated to a privileged service.
    def state_transition(self, block: Block):
        pass

    def retrieve_state(self) -> PrivilegedServicesState:
        value = self.retrieve()
        return PrivilegedServicesState.from_jam_bytes(JamBytes(value))


class Disputes(StateComponent):
    component_id = 5

    def state_transition(self: DisputesState, extrinsic_disputes: ExtrinsicDisputes):
        """
        GP-0.3.6-eq:111,112,113,114 (greek_PSI_prime | ψ') | State transition function for the state's disputes.

        Parameters
        ----------
        self: DisputesState
            Input parameter 1 | GP-0.3.6-eq:23 (greek_PSI | ψ)
        extrinsic_disputes: ExtrinsicDisputes
            Input parameter 2 | GP-0.3.6-eq:23 (bold_E_D)

        Returns
        -------
        post_state_disputes: DisputesState
            Posterior state of DisputesState (greek_PSI_prime | ψ')
        """
        pass

    def retrieve_state(self) -> DisputesState:
        value = self.retrieve()
        return DisputesState.from_jam_bytes(JamBytes(value))


class Statistics(StateComponent):
    component_id = 13

    def state_transition(self, block: Block):
        """
        GP-0.3.6-eq:171,172 (greek_PI_prime | π') | State transition function for the state's statistics.

        Parameters
        ----------
        block: Block
            Todo: Remove this input parameter and replace with the following (see below). General remark regarding STFs.
            Refactor at some point to sandbox/isolate STFs to ONLY EXPLICITLY USE parameters to execute STFs. Currently
            the STFs utilize data external to the STF.
        # extrinsic_guarantees: Vec(Guarantee)
            Input parameter 1 | GP-0.3.6-eq:30 (bold_E_G)
        # extrinsic_preimages: Vec(Preimage)
            Input parameter 2 | GP-0.3.6-eq:30 (bold_E_P)
        # extrinsic_assurances: Vec(Assurance)
            Input parameter 3 | GP-0.3.6-eq:30 (bold_E_A)
        # extrinsic_tickets: Vec(TicketEnvelope)
            Input parameter 4 | GP-0.3.6-eq:30 (bold_E_T)
        # pre_state_timeslot: TimeslotState
            Input parameter 5 | GP-0.3.6-eq:30 (greek_TAU | τ)
        # post_state_timeslot: TimeslotState
            Input parameter 6 | GP-0.3.6-eq:30 (greek_TAU_prime | τ')
        # pre_state_statistics: StatisticsState
            Input parameter 7 | GP-0.3.6-eq:30 (greek_PI | π)
        # header: Header
            Input parameter 8 | GP-0.3.6-eq:30 (bold_H)

        Returns
        -------
        post_state_statistics: StatisticsState
            Posterior state of StatisticsState (greek_PI_prime | π')
        """
        pass

    def retrieve_state(self) -> StatisticsState:
        value = self.retrieve()
        return StatisticsState.from_jam_bytes(JamBytes(value))


class Services(StateComponent):
    # component_id = 255

    # Todo: later
    def state_transition(self, block: Block):
        pass

    def retrieve_state(self) -> ServicesState:
        value = self.retrieve()
        return ServicesState.from_jam_bytes(JamBytes(value))
