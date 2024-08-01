from typing import List

from bandersnatch_vrfs import ring_vrf_verify

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.safrole.types import CustomErrorCode, TicketBody, EpochMark, OutputMarks, State, Output, Input


class SafroleProtocol:
    def __init__(self, ring_data: bytes, initial_state: State, validators_count: int, epoch_length: int):
        self.ring_data = ring_data
        self.state = initial_state
        self.validators_count = validators_count
        self.epoch_length = epoch_length

    def process_input(self, input_data: Input) -> 'Output':
        if input_data.slot <= self.state.tau:
            return Output(err=CustomErrorCode.BAD_SLOT)

        ring_public_keys = [v.bandersnatch for v in self.state.gamma_k]

        input_tickets = []

        # Validate extrinsic
        for idx, extrinsic in enumerate(input_data.extrinsic):

            if extrinsic.attempt not in [0, 1]:
                return Output(err=CustomErrorCode.BAD_TICKET_ATTEMPT)

            # GP-0.3.2-ref:60
            vrf_input_data = b"jam_ticket_seal"  # GP-0.3.2-ref:65
            vrf_input_data += self.state.eta[2]
            vrf_input_data += int.to_bytes(extrinsic.attempt, length=1)

            aux_data = b''  # TODO

            try:
                ring_vrf_output = ring_vrf_verify(
                    self.ring_data, ring_public_keys, vrf_input_data, aux_data, extrinsic.signature
                )
            except ValueError as e:
                return Output(err=CustomErrorCode.BAD_TICKET_PROOF)

            ticket = TicketBody(id=ring_vrf_output, attempt=extrinsic.attempt)

            # Check if ticket already existst
            if ticket in self.state.gamma_a:
                return Output(err=CustomErrorCode.DUPLICATE_TICKET)
            else:
                input_tickets.append(ticket)

        # Check if tickets are in order: GP-0.3.2-ref:80
        if not self.tickets_in_order(input_tickets):
            return Output(err=CustomErrorCode.BAD_TICKET_ORDER)

        # Add tickets to ticket accumulator
        self.state.gamma_a += input_tickets

        # Update state based on the new input
        self.state.tau = input_data.slot
        eta_0 = blake2b_256_hash(self.state.eta[0] + input_data.entropy)   # GP-0.3.2-ref:67
        self.state.eta = [eta_0] + self.state.eta[1:]  # GP-0.3.2-ref:68 TODO epoch transition

        # Create output markers if conditions are met
        epoch_mark = None
        tickets_mark = None

        if len(self.state.gamma_a) >= self.epoch_length:
            epoch_mark = EpochMark(
                entropy=self.state.eta[2],
                validators=[validator.bandersnatch for validator in self.state.kappa]
            )

            tickets_mark = self.state.gamma_a[:self.epoch_length]

        output_marks = OutputMarks(epoch_mark=epoch_mark, tickets_mark=tickets_mark)

        return Output(ok=output_marks)

    @staticmethod
    def tickets_in_order(tickets: List[TicketBody]) -> bool:
        ticket_ids = [t.id for t in tickets]
        return all(x <= y for x, y in zip(ticket_ids, ticket_ids[1:]))
