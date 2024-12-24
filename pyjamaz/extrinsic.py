import logging
from typing import Dict, List

from bandersnatch_vrfs import ring_vrf_sign, ietf_vrf_verify, ring_vrf_verify, vrf_output

from pyjamaz.graypaper_constants import TICKET_ENTRIES, MAXIMUM_EXTRINSIC_TICKETS, TICKET_SUBMISSION_END_SLOT, \
    EPOCH_TIMESLOTS
from pyjamaz.models.block import TicketEnvelope, TicketBody
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.signing import BandersnatchKeypair


class ExtrinsicAccumulator:

    def __init__(self, ring_data: bytes):
        self.tickets_queue: Dict[bytes, TicketEnvelope] = {}
        self.own_tickets_next: List[bytes] = []
        self.own_tickets_current: List[bytes] = []
        self.ring_data = ring_data

    def create_ticket_body(self, ticket_data: TicketEnvelope, ring_public_keys: List[bytes], entropy: bytes) -> TicketBody:
        if ticket_data.attempt >= TICKET_ENTRIES:
            raise ValueError(SafroleErrorCode.bad_ticket_attempt)

        vrf_input_data = ticket_data.generate_vrf_input(entropy)

        aux_data = b''

        try:
            logging.debug(f'Validating ticket with entropy {entropy.hex()}')
            ring_vrf_output = ring_vrf_verify(
                self.ring_data, ring_public_keys, vrf_input_data, aux_data, bytes(ticket_data.signature)
            )
        except ValueError as e:
            raise ValueError(SafroleErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    def add_ticket(self, ticket_data: TicketEnvelope, ring_public_keys: List[bytes], entropy: bytes):
        ticket_body = self.create_ticket_body(ticket_data, ring_public_keys, entropy)
        self.tickets_queue[ticket_body.id] = ticket_data

    def can_add_own_ticket(self, timeslot: int) -> bool:
        return len(self.own_tickets_next) < TICKET_ENTRIES and timeslot % EPOCH_TIMESLOTS <= TICKET_SUBMISSION_END_SLOT

    def add_own_ticket(
            self, ring_public_keys: List[bytes], entropy: bytes, keypair: BandersnatchKeypair, author_index: int
    ):

        if len(self.tickets_queue) > TICKET_ENTRIES:
            raise ValueError("Too many tickets")

        attempt = len(self.own_tickets_next)

        # GP-0.3.8-eq:75
        vrf_input_data = b"jam_ticket_seal"  # GP-0.3.8-eq:64
        vrf_input_data += entropy
        vrf_input_data += int.to_bytes(attempt, byteorder='little', length=1)

        aux_data = b''

        signature = ring_vrf_sign(
            self.ring_data, ring_public_keys, keypair.private_key, author_index,
            vrf_input_data, aux_data
        )

        ticket = TicketEnvelope(
            attempt=attempt,
            signature=signature
        )

        ticket_id = vrf_output(keypair.private_key, vrf_input_data)

        logging.info(f'🎫 Generated ticket: 0x{ticket_id.hex()}')
        logging.debug(f'Generated ticket: id = {ticket_id.hex()} with entropy {entropy.hex()}')

        self.tickets_queue[ticket_id] = ticket
        self.own_tickets_next.append(ticket_id)

    def collect_tickets(self) -> List[TicketEnvelope]:
        """
        Collect tickets to include in a block

        Returns
        -------
        List[TicketEnvelope]
        """

        collected_tickets = sorted(self.tickets_queue.items())[:MAXIMUM_EXTRINSIC_TICKETS]

        # Remove from queue
        for key in [key for key, _ in collected_tickets]:
            self.tickets_queue.pop(key)

        return [ticket for _, ticket in collected_tickets]

    def is_own_ticket(self, ticket_id: bytes) -> bool:
        pass

    def own_ticket_count(self) -> int:
        return len(self.own_tickets_next)

    def clear_own_tickets(self):
        for ticket_id in self.own_tickets_next:
            del self.tickets_queue[ticket_id]
        self.own_tickets_next = []

    def clear_tickets(self):
        self.tickets_queue = {}
        self.own_tickets_next = []

    def process_epoch_change(self):
        self.own_tickets_current = self.own_tickets_next
        self.own_tickets_next = []
        self.tickets_queue = {}

