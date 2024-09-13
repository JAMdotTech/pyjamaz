from copy import deepcopy, copy
from typing import List

from bandersnatch_vrfs import ring_vrf_verify, ring_commitment

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.hashing import blake2b_256_hash, keccak_256_hash
from pyjamaz.merkle import MerkleMountainRange
from pyjamaz.serialization import JamBytes
from pyjamaz.types.common import BlockInfo, Mmr
from pyjamaz.types.safrole import SafroleErrorCode, SlotSealerSeries, SafroleOutput

from pyjamaz.state.base import StateComponent
from pyjamaz.state.exceptions import StateTransitionError
from pyjamaz.types.block import Block, TicketBody, EpochMark, OutputMarks
from pyjamaz.types.state import TimeslotState, EntropyState, ValidatorPoolState, SafroleState, \
    ValidatorQueueState, ValidatorArchiveState, BlocksHistoryState
from pyjamaz.utils import reorder_list_outside_in, list_has_duplicates


class Timeslot(StateComponent):
    component_id = 11

    def state_transition(self, block: Block):

        if block.header.timeslot <= self.pre_state.number:
            raise StateTransitionError(SafroleErrorCode.bad_slot)

        self.post_state.number = block.header.timeslot

    def is_epoch_change(self):
        return self.post_state.epoch_number() != self.pre_state.epoch_number()

    def retrieve_state(self) -> TimeslotState:
        value = self.retrieve()
        return TimeslotState.from_jam_bytes(JamBytes(value))


class Entropy(StateComponent):
    component_id = 6

    def state_transition(self, block: Block):
        # Todo generic prepare outside of function
        self.pre_state = self.retrieve_state()
        self.post_state = self.retrieve_state()

        eta_0 = blake2b_256_hash(self.pre_state.entropy[0] + block.header.vrf_signature)  # GP-0.3.2-ref:67
        if self.get_state_component(Timeslot).is_epoch_change():
            self.post_state.entropy = [eta_0] + self.pre_state.entropy[:3]  # GP-0.3.2-ref:68
        else:
            self.post_state.entropy = [eta_0] + self.pre_state.entropy[1:]  # GP-0.3.2-ref:68

    def retrieve_state(self) -> EntropyState:
        value = self.retrieve()
        return EntropyState.from_jam_bytes(JamBytes(value))


class ValidatorQueue(StateComponent):
    component_id = 7

    def state_transition(self, block: Block):
        pass

    def retrieve_state(self) -> ValidatorQueueState:
        value = self.retrieve()
        return ValidatorQueueState.from_jam_bytes(JamBytes(value))


class ValidatorPool(StateComponent):
    component_id = 8

    def state_transition(self, block: Block):
        if self.get_state_component(Timeslot).is_epoch_change():
            # Update Validator keys and metadata currently active. GP-0.3.2-eq:58
            self.post_state.validators = self.get_state_component(Safrole).pre_state.validators

    def retrieve_state(self) -> ValidatorPoolState:
        value = self.retrieve()
        return ValidatorPoolState.from_jam_bytes(JamBytes(value))


class ValidatorArchive(StateComponent):
    component_id = 9

    def state_transition(self, block: Block):
        if self.get_state_component(Timeslot).is_epoch_change():
            # Update prior epoch validators   GP-0.3.2-eq:58
            self.post_state.validators = self.get_state_component(ValidatorPool).pre_state.validators

    def retrieve_state(self) -> ValidatorArchiveState:
        value = self.retrieve()
        return ValidatorArchiveState.from_jam_bytes(JamBytes(value))


class Safrole(StateComponent):

    component_id = 4

    def __init__(self, state_manager, ring_data: bytes):
        super().__init__(state_manager)
        self.ring_data = ring_data

    def create_ticket_body(self, ticket_data, ring_public_keys) -> TicketBody:
        if ticket_data.attempt not in [0, 1]:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_attempt)

        # GP-0.3.2-ref:74
        vrf_input_data = b"jam_ticket_seal"  # GP-0.3.2-ref:65
        vrf_input_data += self.get_state_component(Entropy).post_state.entropy[2]
        vrf_input_data += int.to_bytes(ticket_data.attempt, byteorder='little', length=1)

        aux_data = b''

        try:
            ring_vrf_output = ring_vrf_verify(
                self.ring_data, ring_public_keys, vrf_input_data, aux_data, ticket_data.signature
            )
        except ValueError as e:
            raise StateTransitionError(SafroleErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    def state_transition(self, block: Block):

        # GP-0.3.2-ref:75
        if self.get_state_component(Timeslot).post_state.slot_phase_index() < gp_const.TICKET_SUBMISSION_END_SLOT:
            # Min 0, max 16 tickets
            if len(block.extrinsic.tickets) > gp_const.MAXIMUM_EXTRINSIC_TICKETS:  # contant_K=16
                raise StateTransitionError(SafroleErrorCode.too_many_tickets)
        else:
            if len(block.extrinsic.tickets) > 0:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT:
                raise StateTransitionError(SafroleErrorCode.unexpected_ticket)

        if len(block.extrinsic.tickets) > 0:

            # Check for duplicate ticket_data; GP-0.3.2-eq:77
            if list_has_duplicates(block.extrinsic.tickets):
                raise StateTransitionError(SafroleErrorCode.duplicate_ticket)

            ring_public_keys = [v.bandersnatch for v in self.post_state.validators]

            input_tickets = []

            # Validate extrinsic
            for idx, ticket_data in enumerate(block.extrinsic.tickets):

                ticket = self.create_ticket_body(ticket_data, ring_public_keys)

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

        if (not self.get_state_component(Timeslot).is_epoch_change() and
                self.get_state_component(Timeslot).post_state.slot_phase_index() >= gp_const.TICKET_SUBMISSION_END_SLOT):
            # Ticket mark only when accumulator is saturated # GP-0.3.2-ref:67
            if len(self.post_state.ticket_accumulator) == gp_const.EPOCH_TIMESLOTS:
                tickets_mark = reorder_list_outside_in(deepcopy(self.post_state.ticket_accumulator))  # GP-0.3.2-ref:70

        if self.get_state_component(Timeslot).is_epoch_change():
            # Epoch change

            epoch_validator_keys = [
                validator.bandersnatch for validator in self.get_state_component(ValidatorQueue).post_state.validators
            ]

            # Clear tickets mark
            tickets_mark = None

            # Create epoch mark
            epoch_mark = EpochMark(
                entropy=self.get_state_component(Entropy).post_state.entropy[1],
                validators=epoch_validator_keys
            )

            # Update Validator keys for the following epoch. # GP-0.3.2-eq:58
            # TODO: apply key_nullifier-function (Φ). This function substitutes offenders with null keys. GP-0.3.2-eq:59
            self.post_state.validators = deepcopy(self.get_state_component(ValidatorQueue).pre_state.validators)

            # Update Sealing-key series of the current epoch.
            if self.enact_fallback_method():
                # Determine fallback keys according to # GP-0.3.2-ref:71
                validators = []
                for n in range(gp_const.EPOCH_TIMESLOTS):
                    blake_hash = blake2b_256_hash(
                        self.get_state_component(Entropy).post_state.entropy[2] + int.to_bytes(n, length=4, byteorder='little')
                    )
                    validator_idx = int.from_bytes(
                        blake_hash[:4], byteorder='little') % len(self.get_state_component(ValidatorPool).post_state.validators)
                    validators.append(self.get_state_component(ValidatorPool).post_state.validators[validator_idx].bandersnatch)

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

        self.output_marks.epoch_mark = epoch_mark
        self.output_marks.tickets_mark = tickets_mark

    def enact_fallback_method(self) -> bool:
        return (
                # Not a full tickets accumulator
                len(self.post_state.ticket_accumulator) != gp_const.EPOCH_TIMESLOTS
                # No Ticket marker generated
                or self.get_state_component(Timeslot).pre_state.slot_phase_index() < gp_const.TICKET_SUBMISSION_END_SLOT
                # Whole epoch is skipped
                or self.get_state_component(Timeslot).post_state.epoch_number() - self.get_state_component(Timeslot).pre_state.epoch_number() > 1
        )

    @staticmethod
    def tickets_in_order(tickets: List[TicketBody]) -> bool:
        ticket_ids = [t.id for t in tickets]
        return all(x <= y for x, y in zip(ticket_ids, ticket_ids[1:]))

    def retrieve_state(self) -> SafroleState:
        value = self.retrieve()
        return SafroleState.from_jam_bytes(JamBytes(value))


class BlocksHistory(StateComponent):
    component_id = 3

    def state_transition(self, block: Block):
        # No more work reports than number of cores GP-0.3.6-ref:80
        if block.extrinsic.work_report_hashes and len(block.extrinsic.work_report_hashes) > gp_const.CORE_COUNT:
            raise StateTransitionError(f"Work reports must be less than number of cores ({gp_const.CORE_COUNT})")

        if len(self.pre_state.blocks) > 0:
            self.post_state.blocks[-1].state_root = block.header.parent_state_root
            mmr_peaks = copy(self.post_state.blocks[-1].mmr.peaks)
        else:
            mmr_peaks = []

        # Extend MMR
        mmr = MerkleMountainRange(mmr_peaks)
        mmr.insert(block.extrinsic.accumulate_root)

        recent_block = BlockInfo(
            header_hash=block.header.hash,
            mmr=Mmr(
                peaks=mmr.peaks
            ),
            state_root=bytes(32),
            reported=block.extrinsic.work_report_hashes
        )

        self.post_state.blocks.append(recent_block)

        if len(self.post_state.blocks) > gp_const.HISTORY:
            # Limit reached, delete first (oldest) item in block history
            self.post_state.blocks.pop(0)

    def retrieve_state(self) -> BlocksHistoryState:
        value = self.retrieve()
        return BlocksHistoryState.from_jam_bytes(JamBytes(value))
