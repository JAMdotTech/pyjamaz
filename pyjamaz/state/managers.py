from copy import deepcopy
from typing import List

from bandersnatch_vrfs import ring_vrf_verify, ring_commitment

import pyjamaz.graypaper_constants as gp_const
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.types.safrole import CustomErrorCode, TicketBody, SlotSealerSeries, EpochMark, OutputMarks, Output

from pyjamaz.state.base import StateManager
from pyjamaz.state.exceptions import StateTransitionError
from pyjamaz.types.block import Header, Block
from pyjamaz.types.state import TimeslotState, EntropyState, JamState, ValidatorPoolState, SafroleState
from pyjamaz.utils import reorder_list_outside_in


class Timeslot(StateManager):

    def state_transition(self, block: Block):
        if block.header.timeslot <= self.state.timeslot.number:
            raise StateTransitionError(CustomErrorCode.bad_slot)

        self.state.timeslot.number = block.header.timeslot


class Entropy(StateManager):

    def state_transition(self, block: Block):
        eta_0 = blake2b_256_hash(self.state.entropy.entropy[0] + block.header.vrf_signature)  # GP-0.3.2-ref:67
        if self.is_epoch_change():
            self.state.entropy.entropy = [eta_0] + self.state.entropy.entropy[:3]  # GP-0.3.2-ref:68
        else:
            self.state.entropy.entropy = [eta_0] + self.state.entropy.entropy[1:]  # GP-0.3.2-ref:68


class ValidatorPool(StateManager):

    def state_transition(self, block: Block):
        if self.is_epoch_change():
            # Update Validator keys and metadata currently active.
            self.state.validator_pool.validators = deepcopy(self.state.safrole.validators)


class ValidatorArchive(StateManager):

    def state_transition(self, block: Block):
        if self.is_epoch_change():
            # Update prior epoch validators
            self.state.validator_archive.validators = deepcopy(self.state.validator_pool.validators)


class Safrole(StateManager):
    def __init__(self, current_state: JamState, pre_state: JamState, ring_data: bytes):
        super().__init__(current_state, pre_state)
        self.ring_data = ring_data

    def create_ticket_body(self, ticket_data, ring_public_keys) -> TicketBody:
        if ticket_data.attempt not in [0, 1]:
            raise StateTransitionError(CustomErrorCode.bad_ticket_attempt)

        # GP-0.3.2-ref:74
        vrf_input_data = b"jam_ticket_seal"  # GP-0.3.2-ref:65
        vrf_input_data += self.state.entropy.entropy[2]
        vrf_input_data += int.to_bytes(ticket_data.attempt, byteorder='little', length=1)

        aux_data = b''

        try:
            ring_vrf_output = ring_vrf_verify(
                self.ring_data, ring_public_keys, vrf_input_data, aux_data, ticket_data.signature
            )
        except ValueError as e:
            raise StateTransitionError(CustomErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    def state_transition(self, block: Block) -> Output:
        if len(block.extrinsic.tickets) > 0:
            if self.state.timeslot.slot_phase_index() >= gp_const.TICKET_SUBMISSION_END_SLOT:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT: GP-0.3.2:paragraph6.7
                raise StateTransitionError(CustomErrorCode.unexpected_ticket)

            ring_public_keys = [v.bandersnatch for v in self.state.safrole.validators]

            input_tickets = []

            # Validate extrinsic
            for idx, ticket_data in enumerate(block.extrinsic.tickets):

                ticket = self.create_ticket_body(ticket_data, ring_public_keys)

                # Check if ticket already exists
                if ticket in self.state.safrole.ticket_accumulator:
                    raise StateTransitionError(CustomErrorCode.duplicate_ticket)
                else:
                    input_tickets.append(ticket)

            # Check if tickets are in order: GP-0.3.2-ref:80
            if not self.tickets_in_order(input_tickets):
                raise StateTransitionError(CustomErrorCode.bad_ticket_order)

            # Add tickets to ticket accumulator, sort and limit: GP-0.3.2-ref:78,79
            self.state.safrole.ticket_accumulator += input_tickets
            self.state.safrole.ticket_accumulator = sorted(
                self.state.safrole.ticket_accumulator, key=lambda t: t.id
            )[:gp_const.EPOCH_TIMESLOTS]

        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        if not self.is_epoch_change() and self.state.timeslot.slot_phase_index() >= gp_const.TICKET_SUBMISSION_END_SLOT:
            # Ticket mark only when accumulator is saturated # GP-0.3.2-ref:67
            if len(self.state.safrole.ticket_accumulator) == gp_const.EPOCH_TIMESLOTS:
                tickets_mark = reorder_list_outside_in(deepcopy(self.state.safrole.ticket_accumulator))  # GP-0.3.2-ref:70

        if self.is_epoch_change():
            # Epoch change

            epoch_validator_keys = [validator.bandersnatch for validator in self.state.validator_queue.validators]

            # Clear tickets mark
            tickets_mark = None

            # Create epoch mark
            epoch_mark = EpochMark(
                entropy=self.state.entropy.entropy[1],
                validators=epoch_validator_keys
            )

            # Update Validator keys for the following epoch.
            self.state.safrole.validators = deepcopy(self.state.validator_queue.validators)

            # Update Sealing-key series of the current epoch.
            if self.enact_fallback_method():
                # Determine fallback keys according to # GP-0.3.2-ref:71
                validators = []
                for n in range(gp_const.EPOCH_TIMESLOTS):
                    blake_hash = blake2b_256_hash(
                        self.state.entropy.entropy[2] + int.to_bytes(n, length=4, byteorder='little')
                    )
                    validator_idx = int.from_bytes(
                        blake_hash[:4], byteorder='little') % len(self.state.validator_pool.validators)
                    validators.append(self.state.validator_pool.validators[validator_idx].bandersnatch)

                self.state.safrole.slot_sealer_series = SlotSealerSeries(keys=validators)
            else:
                # When ticket acculumator is saturated and ticket mark is generated # GP-0.3.2-ref:70
                self.state.safrole.slot_sealer_series = SlotSealerSeries(
                    tickets=reorder_list_outside_in(deepcopy(self.state.safrole.ticket_accumulator))
                )

            # Update ring commitment
            self.state.safrole.ring_commitment = ring_commitment(
                self.ring_data, [v.bandersnatch for v in self.state.safrole.validators]
            )

            # Clear ticket accumulator
            self.state.safrole.ticket_accumulator = []

        output_marks = OutputMarks(epoch_mark=epoch_mark, tickets_mark=tickets_mark)

        return Output(ok=output_marks)

    def enact_fallback_method(self) -> bool:
        return (
                # Not a full tickets accumulator
                len(self.state.safrole.ticket_accumulator) != gp_const.EPOCH_TIMESLOTS
                # No Ticket marker generated
                or self.pre_state.timeslot.slot_phase_index() < gp_const.TICKET_SUBMISSION_END_SLOT
                # Whole epoch is skipped
                or self.state.timeslot.epoch_number() - self.pre_state.timeslot.epoch_number() > 1
        )

    @staticmethod
    def tickets_in_order(tickets: List[TicketBody]) -> bool:
        ticket_ids = [t.id for t in tickets]
        return all(x <= y for x, y in zip(ticket_ids, ticket_ids[1:]))
