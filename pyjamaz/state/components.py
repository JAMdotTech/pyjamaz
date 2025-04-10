import bisect
import logging
from copy import deepcopy, copy
from typing import List, Union, Optional, Set

from bandersnatch_vrfs import ring_vrf_verify, ring_commitment, ietf_vrf_verify
from ed25519_zebra import ed_verify
from jamcodec.types import Vec, U32

import pyjamaz.graypaper_constants as gp_const
from jamcodec.base import JamBytes
from pyjamaz.accumulation import (work_report_mapping, full_sequential_accumulation, edit_queue,
                                  transfers_service_mapping)
from pyjamaz.pvm_interface.invocation import pvm_invoke_on_transfer

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import MerkleMountainRange
from pyjamaz.signing import Ed25519Keypair
from pyjamaz.storage import StorageEngine, Transaction
from pyjamaz.models.common import ValidatorData, WorkReport, TicketBody
from pyjamaz.models.stf_output import SafroleErrorCode, SafroleOutput, ValidatorPoolOutput, TimeslotOutput, \
    EntropyOutput, ValidatorArchiveOutput, RecentHistoryOutput, DisputesOutput, StatisticsOutput, \
    AuthorizerPoolsOutput, RecentHistoryIntermediateOutput, AssurancesAfterDisputesOutput, \
    AssurancesAfterAssurancesOutput, AssurancesAfterGuaranteesOutput, ServicesAfterAccumulationOutput, \
    ServicesAfterPreimagesOutput, \
    DisputesErrorCode, AssurancesErrorCode, GuaranteeErrorCode, ReportedPackage, ServicesErrorCode, \
    AccumulationHistoryOutput, AccumulationQueueOutput, ServicesAfterTransfersOutput

from pyjamaz.state.base import StateComponent, state_key_constructor_service_account, state_key_constructor_preimage, \
    state_key_constructor_preimage_availability, AppContext
from pyjamaz.exceptions import StateTransitionError, BlockValidationError, StateKeyNoResult
from pyjamaz.models.block import EpochMark, Header, TicketEnvelope, ExtrinsicDisputes, \
    Guarantee, Preimage, Assurance, Verdict, Judgement, Culprit, Fault, Credential, GuarantorAssignment, BlockContext, \
    EpochMarkValidatorKeys, DeferredTransferStatistic
from pyjamaz.models.state import TimeslotState, EntropyState, ValidatorPoolState, SafroleState, \
    ValidatorQueueState, ValidatorArchiveState, AuthorizerQueuesState, AuthorizerPoolsState, RecentHistoryState, \
    AssurancesState, PrivilegedServicesState, DisputesState, ServicesState, StatisticsState, RecentBlock, Mmr, \
    SlotSealerSeries, BeefyCommitmentMap, ReportedWorkPackage, ActivityRecord, Assurance as AssuranceStateItem, \
    AccumulationHistoryState, ServiceAccount, AccumulationQueueState, AccumulationStateComponents, \
    AccumulationQueueWorkPackage, DeferredTransfer, ServiceActivityRecord
from pyjamaz.utils import reorder_list_outside_in, list_has_duplicates


class Timeslot(StateComponent):
    component_id = 11

    def state_transition(
            self,
            header: Header
    ) -> TimeslotOutput:
        """
        GP-0.5.0-eq:6.1 (τ') | State transition function for the state's timeslot.

        Parameters
        ----------
        header: Header
            GP-0.6.4-eq:4.5 (bold_H)

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
        if value is None:
            raise ValueError(f"No storage found in DB for Component ID {self.component_id}")
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
        GP-0.5.0-eq:6.22,6.23 (η') | State transition function for the state's entropy.

        Parameters
        ----------
        header: Header
            GP-0.6.4-eq:4.9 (bold_H)
        pre_state_timeslot: TimeslotState
            GP-0.6.4-eq:4.9 (τ)
        pre_state_entropy: EntropyState
            GP-0.6.4-eq:4.9 (η)

        Returns
        -------
        EntropyOutput
            Output containing: posterior state of EntropyState (η')
        """

        post_state_entropy = deepcopy(pre_state_entropy)

        # GP-0.5.0-eq:6.22 (η'[0]) | State transition for first index of the entropy.
        eta_0 = blake2b_256_hash(pre_state_entropy.entropy[0] + self.entropy_output(header))

        # GP-0.5.0-eq:6.23 (η'[1-3]) | State transition for last three indices of the entropy.
        # State transition happen on epoch change.
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # GP-0.5.0-eq:6.23 (`e > e'`) | When epoch changes
            post_state_entropy.entropy = [eta_0] + pre_state_entropy.entropy[:3]
        else:
            post_state_entropy.entropy = [eta_0] + pre_state_entropy.entropy[1:]

        return EntropyOutput(
            post_state=post_state_entropy
        )

    def retrieve_state(self) -> EntropyState:
        value = self.retrieve()
        return EntropyState.from_jam_bytes(JamBytes(value))

    def entropy_output(self, header: Header) -> bytes:
        """
        GP-0.5.0-eq:G.5
        TODO check if output is indeed the first 32 bytes or a hash of the first 32 bytes
        TODO refactor to vrf_output of entropy signature
        Parameters
        ----------
        header: Header

        Returns
        -------
        bytes
        """

        if len(header.entropy_source) == 32:
            return header.entropy_source

        if header.author_bandersnatch_key is None or self.block_context.seal_vrf_output == bytes(32):
            return bytes(32)

        return ietf_vrf_verify(
            bytes(header.author_bandersnatch_key),
            b"jam_entropy" + self.block_context.seal_vrf_output,
            b'',
            bytes(header.entropy_source)
        )


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
        GP-0.5.0-eq:6.13 (κ') | State transition function for the state's current validator set. Occurs on epoch change.

        Parameters
        ----------
        header: Header
            GP-0.5.0-eq:4.10 (bold_H)
        pre_state_timeslot: TimeslotState
            GP-0.5.0-eq:4.10 (τ)
        pre_state_validator_pool: ValidatorPoolState
            GP-0.5.0-eq:4.10 (κ)
        pre_state_safrole: SafroleState
            GP-0.5.0-eq:4.10 (η)

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
        GP-0.5.0-eq:6.13 (λ') | State transition function for the state's archived validator set. Occurs on epoch
        change.

        Parameters
        ----------
        header: Header
            GP-0.5.0-eq:4.11 (bold_H)
        pre_state_timeslot: TimeslotState
            GP-0.5.0-eq:4.11 (τ)
        pre_state_validator_archive: ValidatorArchiveState
            GP-0.5.0-eq:4.11 (λ)
        pre_state_validator_pool: ValidatorPoolState
            GP-0.5.0-eq:4.11 (κ)

        Returns
        -------
        ValidatorArchiveOutput
            Output containing: posterior state of ValidatorArchiveState (λ')
        """
        post_state_validator_archive = deepcopy(pre_state_validator_archive)

        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Update prior epoch validators GP-0.5.0-eq:6.13
            post_state_validator_archive.validators = pre_state_validator_pool.validators

        return ValidatorArchiveOutput(
            post_state=post_state_validator_archive
        )

    def retrieve_state(self) -> ValidatorArchiveState:
        value = self.retrieve()
        return ValidatorArchiveState.from_jam_bytes(JamBytes(value))


class Safrole(StateComponent):
    component_id = 4

    def __init__(
        self,
        storage_engine: StorageEngine,
        block_context: BlockContext,
        app_context: AppContext,
        ring_data: bytes
    ):
        super().__init__(storage_engine, block_context, app_context)
        self.ring_data = ring_data
        self.post_state_safrole = None

    def create_ticket_body(self, ticket_data: TicketEnvelope, ring_public_keys: List[bytes], entropy: bytes) -> TicketBody:
        if ticket_data.attempt >= gp_const.TICKET_ENTRIES:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_attempt)

        vrf_input_data = ticket_data.generate_vrf_input(entropy)

        aux_data = b''

        try:
            logging.debug(f'Validating ticket in STF with entropy {entropy.hex()}')
            ring_vrf_output = ring_vrf_verify(
                self.ring_data, ring_public_keys, vrf_input_data, aux_data, bytes(ticket_data.signature)
            )
        except ValueError as e:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    def state_transition(
            self,
            header: Header,
            extrinsic_tickets: List[TicketEnvelope],
            pre_state_timeslot: TimeslotState,
            pre_state_safrole: SafroleState,
            pre_state_validator_queue: ValidatorQueueState,
            post_state_entropy: EntropyState,
            post_state_validator_pool: ValidatorPoolState,
            post_state_disputes: DisputesState
    ) -> SafroleOutput:
        """
        GP-0.5.0-eq:6.13,6.24,6.34 (γ') | State transition function for the state's Safrole data.

        Parameters
        ----------
        header: Header
            GP-0.6.4-eq:4.8 (bold_H)
        pre_state_timeslot: TimeslotState
            GP-0.6.4-eq:4.8 (τ)
        extrinsic_tickets: List[TicketEnvelope]
            GP-0.6.4-eq:4.8 (bold_E_T)
        pre_state_safrole: SafroleState
            GP-0.6.4-eq:4.8 (γ)
        pre_state_validator_queue: ValidatorQueueState
            GP-0.6.4-eq:4.8 (ι)
        post_state_entropy: EntropyState
            GP-0.6.4-eq:4.8 (η')
        post_state_validator_pool: ValidatorPoolState
            GP-0.6.4-eq:4.8 (κ')
        post_state_disputes: DisputesState
            GP-0.6.4-eq:4.8 (ψ')
        Returns
        -------
        SafroleOutput
            Output containing: Posterior state of SafroleState (γ') and optional Outputmarks
        """

        if header.timeslot <= pre_state_timeslot.number:
            raise StateTransitionError(SafroleErrorCode.bad_slot)

        self.post_state_safrole = deepcopy(pre_state_safrole)

        # GP-0.5.0-eq:6.30
        if self.slot_phase_index(header.timeslot) < gp_const.TICKET_SUBMISSION_END_SLOT:
            # Min 0, max 16 tickets
            if len(extrinsic_tickets) > gp_const.MAXIMUM_EXTRINSIC_TICKETS:  # constant_K=16
                raise StateTransitionError(SafroleErrorCode.too_many_tickets)
        else:
            if len(extrinsic_tickets) > 0:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT:
                raise StateTransitionError(SafroleErrorCode.unexpected_ticket)

        input_tickets = []

        if len(extrinsic_tickets) > 0:

            # Check for duplicate ticket_data; GP-0.5.0-eq:6.32
            if list_has_duplicates(extrinsic_tickets):
                raise StateTransitionError(SafroleErrorCode.duplicate_ticket)

            ring_public_keys = [v.bandersnatch for v in self.post_state_safrole.validators]

            # Validate extrinsic
            for idx, ticket_data in enumerate(extrinsic_tickets):

                ticket = self.create_ticket_body(ticket_data, ring_public_keys, post_state_entropy.entropy[2])

                # Check if ticket already exists
                if ticket in self.post_state_safrole.ticket_accumulator:
                    # GP-0.5.0-eq:6.33
                    raise StateTransitionError(SafroleErrorCode.duplicate_ticket)
                else:
                    input_tickets.append(ticket)

            # Check if tickets are in order: GP-0.5.0-eq:6.32
            if not self.tickets_in_order(input_tickets):
                raise StateTransitionError(SafroleErrorCode.bad_ticket_order)


        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        if (not self.is_epoch_change(pre_state_timeslot.number, header.timeslot) and
                self.slot_phase_index(header.timeslot) >= gp_const.TICKET_SUBMISSION_END_SLOT):
            # Ticket mark only when accumulator is saturated # GP-0.5.0-eq:6.28
            if len(self.post_state_safrole.ticket_accumulator) == gp_const.EPOCH_TIMESLOTS:
                # GP-0.5.0-eq:6.25
                tickets_mark = reorder_list_outside_in(deepcopy(self.post_state_safrole.ticket_accumulator))
                logging.debug(f"Tickets Mark generated")

        # TODO check conditions when epoch should be mark as changed
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Epoch change

            # Update Validator keys for the following epoch. # GP-0.5.0-eq:6.13
            # Apply key_nullifier-function (Φ). This function substitutes offenders with null keys. GP-0.5.0-eq:6.14
            self.post_state_safrole.validators = self.check_offenders(
                validators=deepcopy(pre_state_validator_queue.validators),
                offenders=post_state_disputes.offenders
            )

            # Clear tickets mark
            tickets_mark = None

            # Create epoch mark
            epoch_mark = EpochMark(
                entropy=post_state_entropy.entropy[1],
                tickets_entropy=post_state_entropy.entropy[2],
                validators=[
                    EpochMarkValidatorKeys(
                        bandersnatch=validator.bandersnatch,
                        ed25519=validator.ed25519
                    ) for validator in self.post_state_safrole.validators
                ]
            )
            logging.debug(f"Epoch Mark generated")

            # Update Sealing-key series of the current epoch.
            if self.enact_fallback_method(pre_state_timeslot.number, header.timeslot):
                # Determine fallback keys according to # GP-0.5.0-eq:6.26
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
                logging.info(f"🤷‍ New Slot Sealer Series with fallback keys")
                # TODO temp
                logging.debug(f"Used entropy: {post_state_entropy.entropy[2].hex()}")
                logging.debug(f"New Series: {self.post_state_safrole.slot_sealer_series.to_json()}")
            else:
                # When ticket accumulator is saturated and ticket mark is generated # GP-0.5.0-eq:6.24
                self.post_state_safrole.slot_sealer_series = SlotSealerSeries(
                    tickets=reorder_list_outside_in(deepcopy(self.post_state_safrole.ticket_accumulator))
                )
                logging.debug(f"New Slot Sealer Series with tickets")

            # Update ring commitment using O(); GP-0.5.0-eq:6.13
            self.post_state_safrole.ring_commitment = ring_commitment(
                self.ring_data, [v.bandersnatch for v in self.post_state_safrole.validators]
            )

        # Add tickets to ticket accumulator, sort and limit: GP-0.5.0-eq:6.34,6.35
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            # Not checked by W3F test vectors
            self.post_state_safrole.ticket_accumulator = input_tickets
        else:
            self.post_state_safrole.ticket_accumulator = input_tickets + pre_state_safrole.ticket_accumulator

        self.post_state_safrole.ticket_accumulator = sorted(
            self.post_state_safrole.ticket_accumulator, key=lambda t: t.id
        )[:gp_const.EPOCH_TIMESLOTS]

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
        GP-0.5.0-eq:6.14
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
        GP-0.5.4-eq:8.2,8.3 (α') | State transition function for the state's authorizer pools.

        Parameters
        ----------
        header: Header
            GP-0.5.4-eq:4.19 (bold_H)
        extrinsic_guarantees: List[Guarantee]
            GP-0.5.4-eq:4.19 (bold_E_G)
        post_state_authorizer_queues: AuthorizerQueuesState
            GP-0.5.4-eq:4.19 (φ')
        pre_state_authorizer_pools: AuthorizerPoolsState
            GP-0.5.4-eq:4.19 (α)

        Returns
        -------
        AuthorizerPoolsOutput
            Output containing: Posterior state of AuthorizerPoolsState (α')
        """
        post_state_authorizer_pools = deepcopy(pre_state_authorizer_pools)

        # GP-0.5.4-eq:8.3 | Remove used authorizations
        for guarantee in extrinsic_guarantees:
            try:
                post_state_authorizer_pools.authorizer_pools[guarantee.report.core_index].remove(
                    guarantee.report.authorizer_hash
                )
            except ValueError:
                raise StateTransitionError(GuaranteeErrorCode.core_unauthorized)

        # GP-0.5.4-eq:8.2 | Update authorizations from queue
        for core_index in range(gp_const.CORE_COUNT):
            offset = header.timeslot % gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS

            post_state_authorizer_pools.authorizer_pools[core_index].append(
                post_state_authorizer_queues.authorizer_queues[core_index][offset]
            )
            if len(post_state_authorizer_pools.authorizer_pools[core_index]) > gp_const.MAXIMIM_AUTHORIZATION_POOL_ITEMS:
                post_state_authorizer_pools.authorizer_pools[core_index] = post_state_authorizer_pools.authorizer_pools[core_index][1:]

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
        GP-0.5.0-eq:7.2 (β†) | Intermediate state transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            GP-0.6.4-eq:4.7 (bold_H)
        pre_state_recent_history: RecentHistoryState
            GP-0.6.4-eq:4.6 (β)

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
            beefy_commitment_map: Union[BeefyCommitmentMap, bytes]
    ) -> RecentHistoryOutput:
        """
        GP-0.5.0-eq:7.4 (β') | State transition function for the state's recent history.

        Parameters
        ----------
        header: Header
            GP-0.6.4-eq:4.7 (bold_H)
        extrinsic_guarantees: List[Guarantee]
            GP-0.6.4-eq:4.7 (bold_E_G)
        intermediate_state_recent_history: RecentHistoryState
            GP-0.6.4-eq:4.7 (β†)
        beefy_commitment_map: BeefyCommitmentMap
            GP-0.6.4-eq:4.7 (bold_C)

        Returns
        -------
        RecentHistoryOutput
            Output containing: Posterior state of RecentHistoryState (β')
        """
        post_state_recent_history = deepcopy(intermediate_state_recent_history)

        reported_work_packages = sorted([
            ReportedWorkPackage(
                hash=g.report.package_spec.hash,
                exports_root=g.report.package_spec.exports_root
            ) for g in extrinsic_guarantees
        ], key=lambda g: g.hash)

        # No more work reports than number of cores GP-0.5.0-eq:7.1
        # TODO: implicit limit to work-reports. GP-0.5.0 has a model change making bold_p a dictionary.
        if len(reported_work_packages) > gp_const.CORE_COUNT:
            raise StateTransitionError(f"Work reports must be less than number of cores ({gp_const.CORE_COUNT})")

        if len(intermediate_state_recent_history.recent_history) > 0:
            mmr_peaks = copy(post_state_recent_history.recent_history[-1].mmr.peaks)
        else:
            mmr_peaks = []

        # Extend MMR
        if type(beefy_commitment_map) is bytes:
            accumulate_root = beefy_commitment_map
        else:
            accumulate_root = beefy_commitment_map.get_accumulate_root()

        mmr = MerkleMountainRange(mmr_peaks)
        mmr.insert(accumulate_root)

        logging.debug(f'accumulate_root={accumulate_root.hex()}')

        recent_block = RecentBlock(
            header_hash=header.hash,
            mmr=Mmr(
                peaks=mmr.peaks
            ),
            state_root=bytes(32),
            reported=reported_work_packages
        )
        logging.debug(f"mmr={recent_block.mmr.to_json()['peaks']}")

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
        GP-0.5.0-eq:10.15 (ρ†) | Intermediate state transition function for the state's assurances that processes
        disputes extrinsic.

        Parameters
        ----------
        extrinsic_disputes: ExtrinsicDisputes
            GP-0.5.0-eq:4.13 (bold_E_D)
        pre_state_assurances: AssurancesState
            GP-0.5.0-eq:4.13 (ρ)

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

    def validate_after_disputes(
            self,
            extrinsic_assurances: List[Assurance],
            pre_state_validator_pool: ValidatorPoolState,
            header: Header
    ):
        """
        Validation of Assurances input data after disputes.

        Parameters
        ----------
        extrinsic_assurances
        pre_state_validator_pool
        header

        Returns
        -------

        """

        if not self.have_valid_validators(extrinsic_assurances, pre_state_validator_pool):
            raise StateTransitionError(AssurancesErrorCode.bad_validator_index)

        if not self.are_assurances_sorted(extrinsic_assurances):
            raise StateTransitionError(AssurancesErrorCode.not_sorted_or_unique_assurers)

        if self.has_duplicated_validators(extrinsic_assurances):
            raise StateTransitionError(AssurancesErrorCode.not_sorted_or_unique_assurers)

        for assurance in extrinsic_assurances:

            if assurance.anchor != header.parent:
                raise StateTransitionError(AssurancesErrorCode.bad_attestation_parent)

            validator = pre_state_validator_pool.validators[assurance.validator_index]

            if not self.has_valid_signature(assurance, validator):
                raise StateTransitionError(AssurancesErrorCode.bad_signature)


    def state_transition_after_assurances(
            self,
            extrinsic_assurances: List[Assurance],
            intermediate_state_assurances_after_disputes: AssurancesState
    ) -> AssurancesAfterAssurancesOutput:
        """
        GP-0.5.0-eq:11.28 (ρ‡) | Intermediate state transition function for the state's assurances that processes
        assurances extrinsic.

        Parameters
        ----------
        extrinsic_assurances: List[Assurance]
            GP-0.5.0-eq:4.14 (bold_E_A)
        intermediate_state_assurances_after_disputes: AssurancesState
            GP-0.5.0-eq:4.14 (ρ†)

        Returns
        -------
        AssurancesAfterAssurancesOutput
            Output Containing: Intermediate state after processing assurances of AssurancesState (ρ‡)
        """

        intermediate_state_assurances_after_assurances = deepcopy(intermediate_state_assurances_after_disputes)

        total_assurances_per_core = {c: 0 for c in range(0, gp_const.CORE_COUNT)}
        reported = []

        for assurance in extrinsic_assurances:


            for core in assurance.cores_engaged:
                if intermediate_state_assurances_after_disputes.assurances[core] is None:
                    raise StateTransitionError(AssurancesErrorCode.core_not_engaged)
                else:
                    total_assurances_per_core[core] += 1

        # Check for available reports
        for idx, assurance in enumerate(intermediate_state_assurances_after_disputes.assurances):
            if assurance:
                if total_assurances_per_core[assurance.report.core_index] > 2 / 3 * gp_const.VALIDATOR_COUNT:
                    # GP-0.5.2-eq:11.17 | Work report becomes available
                    reported.append(intermediate_state_assurances_after_disputes.assurances[idx].report)

                    # GP-0.5.2-eq:11.18 | Remove from assurances
                    intermediate_state_assurances_after_assurances.assurances[idx] = None

        return AssurancesAfterAssurancesOutput(
            intermediate_state_after_assurances=intermediate_state_assurances_after_assurances,
            reported=reported
        )

    @staticmethod
    def have_valid_validators(assurances: List[Assurance], post_state_validator_pool: ValidatorPoolState) -> bool:
        """
        GP-0.5.2-eq:11.10 | Validator index is element of current ValidatorPool

        Parameters
        ----------
        assurances: List[Assurance]
        post_state_validator_pool: ValidatorPoolState

        Returns
        -------
        bool
        """
        return all([a.validator_index < len(post_state_validator_pool.validators) for a in assurances])

    @staticmethod
    def are_assurances_sorted(assurances: List[Assurance]) -> bool:
        """
        GP-0.5.2-eq:11.12 | Are assurances correctly sorted by validator index

        Parameters
        ----------
        assurances: List[Assurance]

        Returns
        -------
        bool
        """
        return all(
            assurances[i].validator_index <= assurances[i + 1].validator_index for i in range(len(assurances) - 1)
        )

    @staticmethod
    def has_duplicated_validators(assurances: List[Assurance]) -> bool:
        validator_indexes = [a.validator_index for a in assurances]
        return len(validator_indexes) != len(set(validator_indexes))

    @staticmethod
    def has_valid_signature(assurance: Assurance, validator: ValidatorData) -> bool:
        data = b"jam_available" + blake2b_256_hash(assurance.anchor + assurance.bitfield_bytes)
        return ed_verify(bytes(assurance.signature), data, validator.ed25519)

    def validate_guarantees(
            self,
            extrinsic_guarantees: List[Guarantee],
            pre_services_state: ServicesState,
            intermediate_state_recent_history: RecentHistoryState,
            pre_authorizer_pools: AuthorizerPoolsState,
            intermediate_state_assurances_after_assurances: AssurancesState,
            post_state_validator_pool: ValidatorPoolState,
            header: Header,
            pre_accumulation_history: AccumulationHistoryState,
            post_entropy: EntropyState,
            post_state_timeslot: TimeslotState,
            post_state_validator_archive: ValidatorArchiveState
    ):

        # GP-0.5.3-eq:11.28 (w)
        work_reports = [g.report for g in extrinsic_guarantees]

        # GP-0.5.3-eq:11.40 | Segment-root lookup
        segment_root_lookup = {
            g.report.package_spec.hash: g.report.package_spec.exports_root for g in extrinsic_guarantees
        }

        # Extend segment-root lookup with recent history (GP-0.5.3-eq:11.41)
        for b in intermediate_state_recent_history.recent_history:
            segment_root_lookup.update({r.hash: r.exports_root for r in b.reported})

        for w in work_reports:
            # GP-0.5.3-eq:11.8 | Work report respects gas requirements
            self.check_size_limit(w)
            # GP-0.5.3-eq:11.30 | Work report respects gas requirements
            self.check_gas_requirements(w, pre_services_state)
            # GP-0.5.3-eq:11.3 | Work report respects dependency limit
            if w.dependency_count() > gp_const.MAXIMUM_DEPENDENCIES_WORK_REPORT:
                raise StateTransitionError(GuaranteeErrorCode.too_many_dependencies)
            # GP-0.5.3-eq:11.41 | Verify if segment roots mentioned in work-package are correct
            if not all([
                segment_root_lookup.get(work_package_hash, None) == segment_tree_root
                for work_package_hash, segment_tree_root  in w.segment_root_lookup.items()
            ]):
                raise StateTransitionError(GuaranteeErrorCode.segment_root_lookup_invalid)

        if not self.are_guarentees_sorted(extrinsic_guarantees):
            raise StateTransitionError(GuaranteeErrorCode.out_of_order_guarantee)

        if self.has_duplicated_guarentees(extrinsic_guarantees):
            raise StateTransitionError(GuaranteeErrorCode.out_of_order_guarantee)

        # GP-0.5.3-eq:11.31 (x)
        context_items = [w.context for w in work_reports]
        # GP-0.5.3-eq:11.31 (p)
        extrinsic_work_package_hashes = {w.package_spec.hash for w in work_reports}

        recent_history_work_package_hashes = [
            h.hash for b in intermediate_state_recent_history.recent_history for h in b.reported
        ]

        # GP-0.5.3-eq:11.32 | Check for duplicate
        if len(extrinsic_work_package_hashes) != len(work_reports):
            raise StateTransitionError(GuaranteeErrorCode.duplicate_package)

        # GP-0.5.3-eq:11.38 | Check if work-package appear in pipeline
        if self.work_packages_exists_in_pipeline(
                extrinsic_work_package_hashes,
                intermediate_state_recent_history,
                pre_accumulation_history
        ):
            raise StateTransitionError(GuaranteeErrorCode.duplicate_package)


        for context in context_items:
            # GP-0.5.3-eq:11.35 | Check for expired lookup anchors
            if context.lookup_anchor_slot < header.timeslot - gp_const.MAXIMUM_AGE_LOOKUP_ANCHOR:
                raise StateTransitionError(GuaranteeErrorCode.anchor_not_recent)

            # GP-0.5.3-eq:11.35 | Anchor must be in recent history
            recent_block = self.get_recent_block(context.anchor, intermediate_state_recent_history)

            if not recent_block:
                raise StateTransitionError(GuaranteeErrorCode.anchor_not_recent)

            if recent_block.state_root != context.state_root:
                raise StateTransitionError(GuaranteeErrorCode.bad_state_root)

            if recent_block.mmr.super_peak() != context.beefy_root:
                raise StateTransitionError(GuaranteeErrorCode.bad_beefy_mmr_root)


        for guarantee in extrinsic_guarantees:

            # GP-0.5.3-eq:11.26 | Check validity time slot
            if guarantee.slot > post_state_timeslot.number:
                raise StateTransitionError(GuaranteeErrorCode.future_report_slot)

            if guarantee.slot < gp_const.ROTATION_PERIOD_CORE * (post_state_timeslot.number // gp_const.ROTATION_PERIOD_CORE - 1) :
                raise StateTransitionError(GuaranteeErrorCode.report_epoch_before_last)

            guarantor_assignments = self.get_guarantor_assignments(guarantee, post_state_timeslot)

            if guarantee.report.core_index > len(intermediate_state_assurances_after_assurances.assurances):
                raise StateTransitionError(GuaranteeErrorCode.bad_core_index)

            if not self.are_guarentee_signatures_sorted(guarantee.signatures):
                raise StateTransitionError(GuaranteeErrorCode.not_sorted_or_unique_guarantors)

            # GP-0.5.3-eq:11.23
            if len(guarantee.signatures) < 2 or len(guarantee.signatures) > 3:
                raise StateTransitionError(GuaranteeErrorCode.insufficient_guarantees)

            for credential in guarantee.signatures:

                if credential.validator_index >= gp_const.VALIDATOR_COUNT:
                    raise StateTransitionError(GuaranteeErrorCode.bad_validator_index)

                # GP-0.5.3-eq:11.26 | Check for valid assignment
                guarantor_assignment = guarantor_assignments[credential.validator_index]

                if guarantor_assignment.core_index != guarantee.report.core_index:
                    raise StateTransitionError(GuaranteeErrorCode.wrong_assignment)

                if not self.valid_guarantee_signature(credential, guarantee, guarantor_assignment.validator_ed25519):
                    raise StateTransitionError(GuaranteeErrorCode.bad_signature)

            # GP-0.5.3-eq:11.29 | Check if core is available
            if intermediate_state_assurances_after_assurances.assurances[guarantee.report.core_index] is not None:
                raise StateTransitionError(GuaranteeErrorCode.core_engaged)

            # GP-0.5.3-eq:11.29 | Check if authorizer hash is present in authorizer pool of core
            if guarantee.report.authorizer_hash not in pre_authorizer_pools.authorizer_pools[guarantee.report.core_index]:
                raise StateTransitionError(GuaranteeErrorCode.core_unauthorized)

            # GP-0.5.3-eq:11.39 | Check work-package prerequisites
            for prerequisite in guarantee.report.context.prerequisites:
                if (
                    prerequisite not in recent_history_work_package_hashes and
                    prerequisite not in extrinsic_work_package_hashes
                ):
                    raise StateTransitionError(GuaranteeErrorCode.dependency_missing)


    def get_guarantor_assignments(
            self, guarantee: Guarantee, post_state_timeslot: TimeslotState
    ) -> List[GuarantorAssignment]:
        """
        GP-0.5.3-eq:11.26 | Get applicable mapping (G or G*) of Validator ED25519 and assigned core index

        Parameters
        ----------
        guarantee
        post_state_timeslot

        Returns
        -------
        Dict[bytes, int] Mapping of Validator ED25519 and assigned core index
        """
        if post_state_timeslot.number // gp_const.ROTATION_PERIOD_CORE == \
                guarantee.slot // gp_const.ROTATION_PERIOD_CORE:
            return self.block_context.guarantor_assignments
        else:
            return self.block_context.prev_guarantor_assignments

    @staticmethod
    def get_recent_block(block_hash, recent_history_state: RecentHistoryState) -> Optional[RecentBlock]:
        for block in recent_history_state.recent_history:
            if block.header_hash == block_hash:
                return block

    @staticmethod
    def check_size_limit(work_report: WorkReport):
        """
        GP-0.5.3-eq:11.8 | Work report respects size limit

        Parameters
        ----------
        work_report

        Returns
        -------

        """
        if (len(work_report.auth_output) + sum([len(r.result.ok or bytes(0)) for r in work_report.results])
                > gp_const.MAXIMUM_SIZE_ENCODED_WORK_REPORT):
            raise StateTransitionError(GuaranteeErrorCode.work_report_too_big)

    def check_gas_requirements(self, work_report: WorkReport, services_state: ServicesState):
        """
        GP-0.5.3-eq:11.30 | Work report respects gas requirements

        Parameters
        ----------
        work_report
        services_state

        Returns
        -------

        """
        total_gas = 0

        for result in work_report.results:
            try:
                services_state.retrieve_service_account(result.service_id)
            except StateKeyNoResult:
                raise StateTransitionError(GuaranteeErrorCode.bad_service_id)

            service = services_state.services[result.service_id]

            if result.code_hash != service.code_hash:
                raise StateTransitionError(GuaranteeErrorCode.bad_code_hash)

            # GP-0.5.3-eq:11.30 | Work report respects gas requirements

            if result.accumulate_gas < service.gas_limit_accumulate:
                raise StateTransitionError(GuaranteeErrorCode.service_item_gas_too_low)

            total_gas += result.accumulate_gas
            if total_gas > gp_const.GAS_ACCUMULATION:
                raise StateTransitionError(GuaranteeErrorCode.work_report_gas_too_high)



    @staticmethod
    def work_packages_exists_in_pipeline(
            work_package_hashes: Set[bytes],
            recent_history_state: RecentHistoryState,
            accumulation_history: AccumulationHistoryState
    ) -> bool:
        """
        GP-0.5.3-eq:11.38 | Check if work-packages appear in pipeline
        TODO finish additional checks 11.36 and 11.37
        Parameters
        ----------
        work_package_hashes
        recent_history_state
        accumulation_history

        Returns
        -------
        bool
        """

        if any(w in accumulation_history.accumulation_history for w in work_package_hashes):
            return True

        for recent_block in recent_history_state.recent_history:
            for item in recent_block.reported:
                if item.hash in work_package_hashes:
                    return True

        # TODO q = prerequisites acc. queue -> add state
        # TODO a zoek in pre_state_assurances

        return False

    def state_transition_after_guarantees(
            self,
            extrinsic_guarantees: List[Guarantee],
            intermediate_state_assurances_after_assurances: AssurancesState,
            pre_state_validator_pool: ValidatorPoolState,
            post_state_timeslot: TimeslotState
    ) -> AssurancesAfterGuaranteesOutput:
        """
        GP-0.5.0-eq:11.42 (ρ') | State transition function for the state's assurances that processes guarantees
        extrinsic.

        Parameters
        ----------
        extrinsic_guarantees: List[Guarantee]
            GP-0.5.0-eq:4.15 (bold_E_G)
        intermediate_state_assurances_after_assurances: AssurancesState
            GP-0.5.0-eq:4.15 (ρ‡)
        pre_state_validator_pool: ValidatorPoolState
            GP-0.5.0-eq:4.15 (κ)
        post_state_timeslot: TimeslotState
            GP-0.5.0-eq:4.15 (τ')

        Returns
        -------
        AssurancesAfterGuaranteesOutput
            Output containing: Posterior state after processing guarantees of AssurancesState (ρ')
        """
        post_state_assurances = deepcopy(intermediate_state_assurances_after_assurances)

        self.process_stale_reports(post_state_assurances, post_state_timeslot)

        reported = []
        reporters = []

        for guarantee in extrinsic_guarantees:

            # GP-0.5.3-eq:11.43 | Assign work report to core
            post_state_assurances.assurances[guarantee.report.core_index] = AssuranceStateItem(
                report=guarantee.report,
                timeout=post_state_timeslot.number
            )

            reported.append(
                ReportedPackage(
                    work_package_hash=guarantee.report.package_spec.hash,
                    segment_tree_root=guarantee.report.package_spec.exports_root
                )
            )

            guarantor_assignments = self.get_guarantor_assignments(guarantee, post_state_timeslot)

            for signature in guarantee.signatures:
                reporters.append(guarantor_assignments[signature.validator_index].validator_ed25519)

        # Sort output lists
        reported.sort(key=lambda rp: rp.work_package_hash)
        reporters.sort()

        return AssurancesAfterGuaranteesOutput(
            post_state=post_state_assurances,
            reported=reported,
            reporters=reporters
        )

    @staticmethod
    def process_stale_reports(post_state_assurances: AssurancesState, post_state_timeslot: TimeslotState):
        """
        GP-0.5.2-eq:11.30 | Check for stale reports

        Parameters
        ----------
        post_state_assurances: AssurancesState
        post_state_timeslot: TimeslotState

        Returns
        -------

        """
        for idx, assurance in enumerate(post_state_assurances.assurances):
            if assurance and post_state_timeslot.number >= assurance.timeout + gp_const.UNAVAILABLE_WORK_REPLACEMENT_PERIOD:
                post_state_assurances.assurances[idx] = None

    @staticmethod
    def valid_guarantee_signature(credential: Credential, guarantee: Guarantee, validator_ed25519: bytes) -> bool:
        """
        GP-0.5.2-eq:11.27 | Valid signatures for guarantee

        Parameters
        ----------
        credential
        guarantee
        validator_ed25519

        Returns
        -------
        bool
        """

        data = b"jam_guarantee" + blake2b_256_hash(guarantee.report.to_jam_bytes().to_bytes())
        return ed_verify(bytes(credential.signature), data, validator_ed25519)

    @staticmethod
    def are_guarentees_sorted(guarantees: List[Guarantee]) -> bool:
        """
        GP-0.5.2-eq:11.25 | The core index of guarantees must be in ascending order

        Parameters
        ----------
        guarantees: List[Guarantee]

        Returns
        -------
        bool
        """
        return all(
            guarantees[i].report.core_index <= guarantees[i + 1].report.core_index for i in range(len(guarantees) - 1)
        )

    @staticmethod
    def has_duplicated_guarentees(guarantees: List[Guarantee]) -> bool:
        """
        GP-0.5.2-eq:11.25 | The core index of each guarantee must be unique

        Parameters
        ----------
        guarantees

        Returns
        -------
        bool
        """
        core_indices = [g.report.core_index for g in guarantees]
        return len(core_indices) != len(set(core_indices))

    @staticmethod
    def are_guarentee_signatures_sorted(signatures: List[Credential]) -> bool:
        """
        GP-0.5.2-eq:11.26 | Are signatures correctly sorted by validator index

        Parameters
        ----------
        signatures: List[Credential]

        Returns
        -------
        bool
        """
        return all(
            signatures[i].validator_index <= signatures[i + 1].validator_index for i in range(len(signatures) - 1)
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
        GP-0.5.0-eq:10.16,10.17,10.18,10.19 (ψ') | State transition function for the state's disputes.

        Parameters
        ----------
        extrinsic_disputes: ExtrinsicDisputes
            GP-0.5.0-eq:4.12 (bold_E_D)
        pre_state_disputes: DisputesState
            GP-0.5.0-eq:4.12 (ψ)

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
    # TODO: proper documentation
    def has_valid_judgement_signatures(cls, verdict: Verdict, validators: List[ValidatorData]) -> bool:
        """
        GP-0.5.0-eq:10.3

        Parameters
        ----------
        verdict
        validators

        Returns
        -------

        """
        for judgement in verdict.votes:
            keypair = Ed25519Keypair.from_public_key(validators[judgement.index].ed25519)
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
    # TODO: proper documentation
    def are_judgements_sorted(votes: List[Judgement]) -> bool:
        """
        GP-0.5.0-eq:10.10

        Parameters
        ----------
        votes

        Returns
        -------
        bool
        """
        return all(votes[i].index <= votes[i + 1].index for i in range(len(votes) - 1))

    @staticmethod
    # TODO: proper documentation
    def has_duplicate_judgements(votes: List[Judgement]) -> bool:
        """
        GP-0.5.0-eq:10.10

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
    # TODO: proper documentation
    def are_verdicts_sorted(verdicts: List[Verdict]) -> bool:
        """
        GP-0.5.0-eq:10.7

        Parameters
        ----------
        verdicts

        Returns
        -------
        bool
        """
        return all(verdicts[i].target <= verdicts[i + 1].target for i in range(len(verdicts) - 1))

    @staticmethod
    # TODO: proper documentation
    def are_culprits_sorted(culprits: List[Culprit]) -> bool:
        """
        GP-0.5.0-eq:10.8

        Parameters
        ----------
        culprits

        Returns
        -------
        bool
        """
        return all(culprits[i].key <= culprits[i + 1].key for i in range(len(culprits) - 1))

    @staticmethod
    # TODO: proper documentation
    def are_faults_sorted(faults: List[Fault]) -> bool:
        """
        GP-0.5.0-eq:10.8

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
    # TODO: proper documentation
    def has_duplicate_report_hashes(verdicts: List[Verdict]) -> bool:
        """
        GP-0.5.0-eq:10.9

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
    # TODO: proper documentation
    def check_valid_faults_count(faults: List[Fault], report_hash: bytes):
        """
        GP-0.5.0-eq:10.13

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
    # TODO: proper documentation
    def check_valid_culprits_count(culprits: List[Culprit], report_hash: bytes):
        """
        GP-0.5.0-eq:10.14

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
    def validate_extrinsic_disputes(
            cls,
            extrinsic_disputes: ExtrinsicDisputes,
            pre_state_timeslot: TimeslotState,
            pre_state_validator_pool: ValidatorPoolState,
            pre_state_validator_archive: ValidatorArchiveState
    ):
        current_epoch = pre_state_timeslot.number // gp_const.EPOCH_TIMESLOTS

        for verdict in extrinsic_disputes.verdicts:

            if current_epoch - verdict.age == 0:
                validators = pre_state_validator_pool.validators
            elif current_epoch - verdict.age == 1:
                validators = pre_state_validator_archive.validators
            else:
                raise BlockValidationError(DisputesErrorCode.bad_judgement_age)

            if not cls.has_valid_judgement_signatures(verdict, validators):
                raise BlockValidationError(DisputesErrorCode.bad_signature)

        validator_keys = [v.ed25519 for v in pre_state_validator_pool.validators]

        # Check if culprit is in validator set
        for culprit in extrinsic_disputes.culprits:
            if culprit.key not in validator_keys:
                raise BlockValidationError(DisputesErrorCode.bad_guarantor_key)

        # Check if faulty auditor is in validator set
        for fault in extrinsic_disputes.faults:
            if fault.key not in validator_keys:
                raise BlockValidationError(DisputesErrorCode.bad_auditor_key)




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
        GP-0.5.0-eq:13.3,13.4 (π') | State transition function for the state's statistics.

        Parameters
        ----------
        extrinsic_guarantees: List[Guarantee]
            GP-0.5.0-eq:4.20 (bold_E_G)
        extrinsic_preimages: List[Preimage]
            GP-0.5.0-eq:4.20 (bold_E_P)
        extrinsic_assurances: List[Assurance]
            GP-0.5.0-eq:4.20 (bold_E_A)
        extrinsic_tickets: List[TicketEnvelope]
            GP-0.5.0-eq:4.20 (bold_E_T)
        pre_state_timeslot: TimeslotState
            GP-0.5.0-eq:4.20 (τ)
        post_state_timeslot: TimeslotState
            GP-0.5.0-eq:4.20 (τ')
        post_state_validator_pool: ValidatorPoolState
            GP-0.5.0-eq:4.20 (κ')
        pre_state_statistics: StatisticsState
            GP-0.5.0-eq:4.20 (π)
        header: Header
            GP-0.5.0-eq:4.20 (bold_H)

        Returns
        -------
        StatisticsOutput
            Output containing: Posterior state of StatisticsState (π')
        """
        post_state = deepcopy(pre_state_statistics)

        # GP-0.6.4-eq:13.3 | Shift statistics after epoch change
        if self.is_epoch_change(pre_state_timeslot.number, header.timeslot):
            post_state.vals_last = post_state.vals_current
            post_state.vals_current = [ActivityRecord(
                blocks=0,
                tickets=0,
                pre_images=0,
                pre_images_size=0,
                guarantees=0,
                assurances=0
            ) for _ in range(gp_const.VALIDATOR_COUNT)]

        # GP-0.6.4-eq:13.4 | Update validator stats
        post_state.vals_current[header.author_index].blocks += 1
        post_state.vals_current[header.author_index].tickets += len(extrinsic_tickets)
        post_state.vals_current[header.author_index].pre_images += len(extrinsic_preimages)
        post_state.vals_current[header.author_index].pre_images_size += sum([len(p.blob) for p in extrinsic_preimages])

        for assurance in extrinsic_assurances:
            post_state.vals_current[assurance.validator_index].assurances += 1

        for reporter in self.block_context.reporters:
            post_state.vals_current[self.retrieve_validator_index(reporter, post_state_validator_pool)].guarantees += 1

        incoming_work_reports = [g.report for g in extrinsic_guarantees]

        # GP-0.6.4-eq:13.8 | Update core statistics
        for c in range(gp_const.CORE_COUNT):
            post_state.cores[c].update(
                core_index=c,
                incoming_work_reports=incoming_work_reports,
                available_work_reports=self.block_context.available_work_reports,
                extrinsic_assurances=extrinsic_assurances
            )

        post_state.services = {}

        # GP-0.6.4-eq:13.12 | Determine affected services
        services = [r.service_id for w in incoming_work_reports for r in w.results]
        services += [p.requester for p in extrinsic_preimages]
        services += self.block_context.accumulation_statistics.keys()
        services += self.block_context.deferred_transfer_statistics.keys()

        # GP-0.6.4-eq:13.11 | Update service statistics
        for s in sorted(set(services)):
            activity_record = ServiceActivityRecord()
            for p in extrinsic_preimages:
                if p.requester == s:
                    activity_record.provided_count += 1
                    activity_record.provided_size += len(p.blob)

            for w in incoming_work_reports:
                for r in w.results:
                    if r.service_id == s:
                        activity_record.refinement_count += 1
                        activity_record.refinement_gas_used += r.refine_load.gas_used
                        activity_record.imports += r.refine_load.imports
                        activity_record.extrinsic_count += r.refine_load.extrinsic_count
                        activity_record.extrinsic_size += r.refine_load.extrinsic_size
                        activity_record.exports += r.refine_load.exports

            accumulation_stats = self.block_context.accumulation_statistics.get(s)
            if accumulation_stats:
                activity_record.accumulate_count += accumulation_stats.nr_work_reports_accumulated
                activity_record.accumulate_gas_used += accumulation_stats.total_gas_utilized

            transfer_stats = self.block_context.deferred_transfer_statistics.get(s)
            if transfer_stats:
                activity_record.on_transfers_count += transfer_stats.nr_transfers
                activity_record.on_transfers_gas_used += transfer_stats.gas_used

            post_state.services[s] = activity_record

        return StatisticsOutput(
            post_state=post_state
        )

    @staticmethod
    def retrieve_validator_index(ed25519_key: bytes, post_validator_pool: ValidatorPoolState) -> int:
        for validator_index, validator_data in enumerate(post_validator_pool.validators):
            if validator_data.ed25519 == ed25519_key:
                return validator_index
        raise ValueError("Bandersnatch key not found in validator pool")


    def retrieve_state(self) -> StatisticsState:
        value = self.retrieve()
        return StatisticsState.from_jam_bytes(JamBytes(value))


class Services(StateComponent):
    component_id = 255

    def validate_extrinsic_preimages(
            self,
            extrinsic_preimages: List[Preimage],
            pre_state_services: ServicesState,
    ):
        """
        Validate quality of extrinsic preimages.
        TODO Emiel: check if pre_state_services is correct, should be after accumulate?

        Parameters
        ----------
        extrinsic_preimages
        pre_state_services

        Returns
        -------

        """
        if len(extrinsic_preimages) > 0:
            if not self.are_preimages_unique(extrinsic_preimages):
                raise StateTransitionError(ServicesErrorCode.preimages_not_sorted_unique)

            if not self.are_preimages_sorted(extrinsic_preimages):
                raise StateTransitionError(ServicesErrorCode.preimages_not_sorted_unique)

            # GP-0.5.4-eq:12.31
            for preimage in extrinsic_preimages:
                if not self.is_preimage_needed(preimage, pre_state_services):
                    raise StateTransitionError(ServicesErrorCode.preimage_unneeded)

    @staticmethod
    def are_preimages_unique(preimages: List[Preimage]) -> bool:
        """
        GP-0.6.2-eq:12.29 | Are all preimages unique?

        Parameters
        ----------
        preimages: List[Preimage]

        Returns
        -------
        bool
        """
        return len(preimages) == len({(p.requester, p.blob) for p in preimages})

    @staticmethod
    def are_preimages_sorted(preimages: List[Preimage]) -> bool:
        """
        GP-0.6.2-eq:12.29 | Are all preimages sorted?

        Parameters
        ----------
        preimages: List[Preimage]

        Returns
        -------
        bool
        """

        sorted_preimage = lambda p: int(p.requester).to_bytes(2, byteorder="little") + p.blob

        return all(
            sorted_preimage(preimages[i]) <= sorted_preimage(preimages[i + 1]) for i in range(len(preimages) - 1)
        )

    def state_transition_after_preimages(
            self,
            extrinsic_preimages: List[Preimage],
            intermediate_state_after_transfers: ServicesState,
            post_state_timeslot: TimeslotState
    ) -> ServicesAfterPreimagesOutput:
        """
        GP-0.3.8-eq:156 (δ†) | Intermediate state transition function after processing Preimages for the state's
        services.

        Parameters
        ----------
        extrinsic_preimages: List[Preimage]
            GP-0.3.8-eq:24 (bold_E_P)
        intermediate_state_after_transfers: ServicesState
            GP-0.3.8-eq:24 (δ‡)
        post_state_timeslot: TimeslotState
            GP-0.3.8-eq:24 (τ')

        Returns
        -------
        ServicesAfterPreimagesOutput
            Output containing: Intermediate state after processing Preimages of ServicesState (δ†)
        """

        # GP-0.5.4-eq:12.33
        for preimage in extrinsic_preimages:
            # Store preimage
            intermediate_state_after_transfers.store_preimage(
                service_account_id=preimage.requester,
                preimage_blob=preimage.blob
            )

            # Update availability information
            intermediate_state_after_transfers.store_preimage_availability(
                service_account_id=preimage.requester,
                preimage_hash=blake2b_256_hash(preimage.blob),
                preimage_length=len(preimage.blob),
                value=[post_state_timeslot.number]
            )

        return ServicesAfterPreimagesOutput(
            post_state=intermediate_state_after_transfers
        )

    def state_transition_accumulation(
            self,
            accumulatable_work_reports: List[WorkReport],
            pre_state_privileged_services: PrivilegedServicesState,
            pre_state_services: ServicesState,
            pre_state_validator_queue: ValidatorQueueState,
            pre_state_authorizer_queues: AuthorizerQueuesState,
            post_state_timeslot: TimeslotState,
            post_state_entropy: EntropyState,
    ) -> ServicesAfterAccumulationOutput:
        """
        GP-0.6.0-eq:12.21,12.22 (δ†) | State transition function for the state's services.

        Parameters
        ----------
        accumulatable_work_reports: List[WorkReport]
            GP-0.6.0-eq:12.21 (W*)
        pre_state_services: ServicesState
            GP-0.6.0-eq:12.21 (δ)
        pre_state_privileged_services: PrivilegedServicesState
            GP-0.6.0-eq:12.21 (χ)
        pre_state_validator_queue: ValidatorQueueState
            GP-0.6.0-eq:12.21 (ι)
        pre_state_authorizer_queues: AuthorizerQueuesState
            GP-0.6.0-eq:12.21 (φ)

        Returns
        -------
        ServicesAfterAccumulationOutput
            Output containing: intermediate state of ServicesState (δ†) and BeefyCommitmentMap (C).
        """

        services = ServicesState(services=deepcopy(pre_state_services.services))
        services.set_storage_engine(self.storage_engine)
        services.set_storage_transaction(self.app_context.transaction)

        accumulation_state = AccumulationStateComponents(
            services=services,
            validator_queue=deepcopy(pre_state_validator_queue),
            authorizer_queues=deepcopy(pre_state_authorizer_queues),
            privileged_services=deepcopy(pre_state_privileged_services)
        )

        # GP-0.6.0-eq:12.20
        gas_limit = min(
            gp_const.GAS_TOTAL, gp_const.GAS_ACCUMULATION * gp_const.CORE_COUNT + sum(
                pre_state_privileged_services.auto_accumulate_services.values()
            )
        )

        logging.debug(f'ORDERED ACCUMULATION: W^*={[w.package_spec.hash.hex() for w in accumulatable_work_reports]}')

        # GP-0.6.0-eq:12.21
        output = full_sequential_accumulation(
            gas_limit=gas_limit,
            work_reports=accumulatable_work_reports,
            accumulation_state=accumulation_state,
            auto_accumulate_services=pre_state_privileged_services.auto_accumulate_services,
            post_state_timeslot=post_state_timeslot,
            post_state_entropy=post_state_entropy
        )

        # GP-0.6.0-eq:12.22
        return ServicesAfterAccumulationOutput(
            intermediate_state_after_accumulation=output.post_accumulation_state.services,
            post_state_privileged_services=output.post_accumulation_state.privileged_services,
            post_state_validator_queue=output.post_accumulation_state.validator_queue,
            post_state_authorizer_queues=output.post_accumulation_state.authorizer_queues,
            beefy_commitment_map=output.accumulation_commitment,
            nr_work_results_accumulated=output.nr_work_results_accumulated,
            deferred_transfers=output.deferred_transfers,
            accumulation_gas_utilized=output.accumulation_gas_utilized
        )

    def state_transition_transfers(
            self,
            intermediate_state_after_accumulation: ServicesState,
            post_state_timeslot: TimeslotState,
            deferred_transfers: List[DeferredTransfer]
    ) -> ServicesAfterTransfersOutput:
        """
        GP-0.6.1-eq:12.24 (δ‡) | State transition function for the state's services.

        Parameters
        ----------
        intermediate_state_after_accumulation: ServicesState
            GP-0.6.1-eq:12.24 (δ†)
        post_state_timeslot: TimeslotState
            GP-0.6.1-eq:12.24 (τ')
        deferred_transfers: List[DeferredTransfer]
            GP-0.6.1-eq:12.24 (bold_t)

        Returns
        -------
        ServicesAfterTransfersOutput
            Output containing: intermediate state of ServicesState (δ‡)
        """

        intermediate_state_after_transfers = ServicesState(
            services=deepcopy(intermediate_state_after_accumulation.services)
        )
        intermediate_state_after_transfers.set_storage_engine(self.storage_engine)
        intermediate_state_after_transfers.set_storage_transaction(self.app_context.transaction)

        deferred_transfer_statistics = {}

        for service_id in intermediate_state_after_accumulation.services.keys():
            service_transfers = transfers_service_mapping(deferred_transfers, service_id)

            output = pvm_invoke_on_transfer(
                services_state=intermediate_state_after_accumulation,
                timeslot=post_state_timeslot.number,
                service_id=service_id,
                deferred_transfers=service_transfers
            )

            intermediate_state_after_transfers.services.update({
                service_id: output.service_account
            })

            # GP-0.6.4-eq:12.30
            if len(service_transfers) > 0:
                deferred_transfer_statistics[service_id] = DeferredTransferStatistic(
                    nr_transfers=len(service_transfers),
                    gas_used=output.gas_used,
                )

        return ServicesAfterTransfersOutput(
            intermediate_state_after_transfers=intermediate_state_after_transfers,
            deferred_transfer_statistics=deferred_transfer_statistics
        )

    def is_preimage_needed(self, preimage: Preimage, pre_state_services: ServicesState) -> bool:
        """
        GP-0.5.4-eq:12.30 | Is preimage needed

        Parameters
        ----------
        preimage
        pre_state_services

        Returns
        -------
        bool
        """
        preimage_hash = blake2b_256_hash(preimage.blob)

        # Check if preimage isn't already available
        if pre_state_services.preimage_exists(preimage.requester, preimage_hash):
            return False

        # Check if preimage is requested
        try:
            preimage_availability = pre_state_services.retrieve_preimage_availability(
                preimage.requester, preimage_hash, len(preimage.blob)
            )
            return preimage_availability == []
        except StateKeyNoResult:
            return False


    def retrieve_state(self) -> ServicesState:
        # State is retrieve per service
        return ServicesState(services={})

    def store_state(self, state: ServicesState, transaction: Optional[Transaction] = None):
        """
        State for services are stored per service account

        Parameters
        ----------
        state
        transaction

        Returns
        -------

        """
        #TODO: mark dirty state, so we have state_mutations directly available
        state_mutations = []

        # Collect all service accounts in current memory
        for service_id, service_account in state.services.items():

            # Process storage items
            for storage_key, storage_value in service_account.storage_items.items():
                if storage_value is None:
                    state_mutations.append(("storage_items_delete", service_id, storage_key))
                else:
                    state_mutations.append(("storage_items_update", service_id, storage_key, storage_value))

            # Process preimages
            for preimage_hash, preimage_blob in service_account.preimages.items():
                if preimage_blob is None:
                    state_mutations.append(("preimages_delete", service_id, preimage_hash))
                else:
                    state_mutations.append(("preimages_update", service_id, preimage_blob))

            # Process preimage availability
            for (preimage_hash, preimage_length), availability  in service_account.preimage_availability.items():

                if availability is None:
                    state_mutations.append(("preimage_availability_delete", service_id, preimage_hash, preimage_length))
                else:
                    state_mutations.append(("preimage_availability_update", service_id, preimage_hash, preimage_length, availability))

            # Process service account
            if service_account is None:
                state_mutations.append(("service_account_delete", service_id,))
            else:
                state_mutations.append(("service_account_update", service_id, service_account))

        # Process all mutations afterwards (in order) to prevent mutating the state while iterating over it
        for mut in state_mutations:
            if mut[0] == "storage_items_delete":
                state.delete_storage_item(mut[1], mut[2], commit=True)
            elif mut[0] == "storage_items_update":
                state.store_storage_item(mut[1], mut[2], mut[3], commit=True)
            elif mut[0] == "preimages_delete":
                state.delete_preimage(mut[1], mut[2], commit=True)
            elif mut[0] == "preimages_update":
                state.store_preimage(mut[1], mut[2], commit=True)
            elif mut[0] == "preimage_availability_delete":
                state.delete_preimage_availability(mut[1], mut[2], mut[3], commit=True)
            elif mut[0] == "preimage_availability_update":
                state.store_preimage_availability(
                    service_account_id=mut[1],
                    preimage_hash=mut[2],
                    preimage_length=mut[3],
                    value=mut[4],
                    commit=True
                )
            elif mut[0] == "service_account_delete":
                state.delete_service_account(mut[1], commit=True)
            elif mut[0] == "service_account_update":
                state.store_service_account(mut[1], mut[2], commit=True)


class AccumulationQueue(StateComponent):
    component_id = 14

    def state_transition(
            self,
            queued_work_reports: List[AccumulationQueueWorkPackage],
            pre_state_accumulation_queue: AccumulationQueueState,
            post_state_accumulation_history: AccumulationHistoryState,
            pre_state_timeslot: TimeslotState,
            post_state_timeslot: TimeslotState
    ) -> AccumulationQueueOutput:
        """
        GP-0.6.1-eq:12.27 (θ') | State transition function for the state's accumulation queue

        Parameters
        ----------
        queued_work_reports: List[WorkReport]
            GP-0.5.4-eq:4.17 (W_Q)
        pre_state_accumulation_queue: AccumulationQueueState
            GP-0.5.4-eq:4.17 (θ)
        post_state_accumulation_history: AccumulationHistoryState
            GP-0.5.4-eq:4.17 (ξ')

        Returns
        -------
        AccumulationQueueOutput
            Output containing: Posterior state of AccumulationQueueState (θ')
        """
        accumulation_queue = [[] for _ in range(gp_const.EPOCH_TIMESLOTS)]
        m = post_state_timeslot.number % gp_const.EPOCH_TIMESLOTS

        for i in range(gp_const.EPOCH_TIMESLOTS):

            if i == 0:
                accumulation_queue[m - i] = edit_queue(
                    queued_work_reports, post_state_accumulation_history.accumulation_history[
                        gp_const.EPOCH_TIMESLOTS - 1
                    ]
                )

            elif 1 <= i < post_state_timeslot.number - pre_state_timeslot.number:
                accumulation_queue[m - i] = []

            elif i >= post_state_timeslot.number - pre_state_timeslot.number:
                accumulation_queue[m - i] = edit_queue(
                    pre_state_accumulation_queue.accumulation_queue[m - i],
                    post_state_accumulation_history.accumulation_history[gp_const.EPOCH_TIMESLOTS - 1]
                )

        return AccumulationQueueOutput(
            post_state=AccumulationQueueState(accumulation_queue=accumulation_queue),
        )

    def retrieve_state(self) -> AccumulationQueueState:
        value = self.retrieve()
        return AccumulationQueueState.from_jam_bytes(JamBytes(value))


class AccumulationHistory(StateComponent):
    component_id = 15

    def state_transition(
            self,
            accumulatable_work_reports: List[WorkReport],
            pre_state_accumulation_history: AccumulationHistoryState,
            nr_work_results_accumulated: int
    ) -> AccumulationHistoryOutput:
        """
        GP-0.5.4-eq:12.25,12.26 (ξ') | State transition function for the state's accumulation history.

        Parameters
        ----------
        accumulatable_work_reports: List[WorkReport]
            GP-0.5.4-eq:12.11 (W*)
        pre_state_accumulation_history: AccumulationHistoryState
            GP-0.5.4-eq:4.17 (ξ)
        nr_work_results_accumulated: int
            GP-0.6.1-eq:12.21 (n)
        Returns
        -------
        AccumulationHistoryOutput
            Output containing: Posterior state of AccumulationHistoryState (ξ')
        """
        post_state_accumulation_history = AccumulationHistoryState(
            accumulation_history=pre_state_accumulation_history.accumulation_history[1:]
        )

        post_state_accumulation_history.accumulation_history.append(
            sorted(list(work_report_mapping(accumulatable_work_reports[:nr_work_results_accumulated])))
        )

        return AccumulationHistoryOutput(
            post_state=post_state_accumulation_history
        )

    def retrieve_state(self) -> AccumulationHistoryState:
        value = self.retrieve()
        return AccumulationHistoryState.from_jam_bytes(JamBytes(value))
