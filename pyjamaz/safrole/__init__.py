from copy import deepcopy
from dataclasses import dataclass
from typing import List

from bandersnatch_vrfs import ring_vrf_verify

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.safrole.types import CustomErrorCode, TicketBody, EpochMark, OutputMarks, State, Output, Input, \
    SlotSealerSeries


@dataclass
class SafroleConfig:
    ring_data: bytes
    validators_count: int
    epoch_length: int
    ticket_end_slot: int

    def __post_init__(self):
        if self.ticket_end_slot >= self.epoch_length:
            raise ValueError("ticket_end_slot must be less than epoch_length")


class SafroleProtocol:
    def __init__(self, initial_state: State, config: SafroleConfig):
        self.ring_data = config.ring_data
        self.state = initial_state
        self.validators_count = config.validators_count
        self.epoch_length = config.epoch_length
        self.ticket_end_slot = config.ticket_end_slot

        self._ticket_mark_sent = False

    def calculate_epoch_and_slot_index(self, slot_index: int) -> tuple[int, int]:
        epoch_index = slot_index // self.epoch_length
        slot_phase_index = slot_index % self.epoch_length
        return epoch_index, slot_phase_index

    def process_input(self, input_data: Input) -> 'Output':

        # Check input conditions
        if input_data.slot <= self.state.tau:
            return Output(err=CustomErrorCode.bad_slot)

        if len(input_data.extrinsic) > 0:
            if input_data.slot >= self.ticket_end_slot:
                # Don't accept tickets after TICKET_SUBMISSION_END_SLOT: GP-0.3.2:paragraph6.7
                return Output(err=CustomErrorCode.unexpected_ticket)

            ring_public_keys = [v.bandersnatch for v in self.state.gamma_k]

            input_tickets = []

            # Validate extrinsic
            for idx, extrinsic in enumerate(input_data.extrinsic):

                if extrinsic.attempt not in [0, 1]:
                    return Output(err=CustomErrorCode.bad_ticket_attempt)

                # GP-0.3.2-ref:60
                vrf_input_data = b"jam_ticket_seal"  # GP-0.3.2-ref:65
                vrf_input_data += self.state.eta[2]
                vrf_input_data += int.to_bytes(extrinsic.attempt, byteorder='little', length=1)

                aux_data = b''  # TODO

                try:
                    ring_vrf_output = ring_vrf_verify(
                        self.ring_data, ring_public_keys, vrf_input_data, aux_data, extrinsic.signature
                    )
                except ValueError as e:
                    return Output(err=CustomErrorCode.bad_ticket_proof)

                ticket = TicketBody(id=ring_vrf_output, attempt=extrinsic.attempt)

                # Check if ticket already exists
                if ticket in self.state.gamma_a:
                    return Output(err=CustomErrorCode.duplicate_ticket)
                else:
                    input_tickets.append(ticket)

            # Check if tickets are in order: GP-0.3.2-ref:80
            if not self.tickets_in_order(input_tickets):
                return Output(err=CustomErrorCode.bad_ticket_order)

            # Add tickets to ticket accumulator, sort and limit: GP-0.3.2-ref:78,79
            self.state.gamma_a += input_tickets
            self.state.gamma_a = sorted(self.state.gamma_a, key=lambda t: t.id)[:self.epoch_length]

        # Update state based on the new input
        self.state.tau = input_data.slot

        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        eta_0 = blake2b_256_hash(self.state.eta[0] + input_data.entropy)  # GP-0.3.2-ref:67

        if self.ticket_end_slot <= self.state.tau < self.epoch_length and not self._ticket_mark_sent:
            # Ticket mark only when accumulator is saturated # GP-0.3.2-ref:67
            if len(self.state.gamma_a) == self.epoch_length:
                tickets_mark = deepcopy(self.state.gamma_a)
                self._ticket_mark_sent = True

        if self.state.tau >= self.epoch_length:
            # Epoch change

            epoch_validator_keys = [validator.bandersnatch for validator in self.state.iota]

            epoch_mark = EpochMark(
                entropy=self.state.eta[0],
                validators=epoch_validator_keys
            )

            self.state.eta = [eta_0] + self.state.eta[:3]  # GP-0.3.2-ref:68

            # Update prior epoch validators
            self.state.lambda_ = deepcopy(self.state.kappa)
            # Update Validator keys and metadata currently active.
            self.state.kappa = deepcopy(self.state.gamma_k)
            # Update Validator keys for the following epoch.
            self.state.gamma_k = deepcopy(self.state.iota)
            # Clear ticket accumulator
            self.state.gamma_a = []
            # TODO: Update Sealing-key series of the current epoch.
            #self.state.gamma_s = SlotSealerSeries(keys=epoch_validator_keys)

            # Reset flags
            self._ticket_mark_sent = False

        else:
            self.state.eta = [eta_0] + self.state.eta[1:]  # GP-0.3.2-ref:68

        output_marks = OutputMarks(epoch_mark=epoch_mark, tickets_mark=tickets_mark)

        return Output(ok=output_marks)

    @staticmethod
    def tickets_in_order(tickets: List[TicketBody]) -> bool:
        ticket_ids = [t.id for t in tickets]
        return all(x <= y for x, y in zip(ticket_ids, ticket_ids[1:]))
