import asyncio
import logging
from typing import Dict, List, Optional

from bandersnatch_vrfs import RingContext, vrf_output

from pyjamaz.constants import MESSAGE_TYPES
from pyjamaz.graypaper_constants import TICKET_ENTRIES, MAXIMUM_EXTRINSIC_TICKETS, TICKET_SUBMISSION_END_SLOT, \
    EPOCH_TIMESLOTS
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.block import TicketEnvelope, Guarantee, Assurance, Preimage, Block
from pyjamaz.models.common import TicketBody, WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.models.stf_output import SafroleErrorCode
from pyjamaz.signing import BandersnatchKeypair
from pyjamaz.transport.pubsub import PubSub, PubSubSignal
from pyjamaz.utils import vrf_input_ticket_seal, format_hash


class BlockExtrinsicAccumulator:

    def __init__(self, ring_data: bytes):
        self.tickets_queue: Dict[bytes, TicketEnvelope] = {}
        self.own_tickets_next: List[bytes] = []
        self.own_tickets_current: List[bytes] = []
        self.guarentees_queue: List[Guarantee] = []
        self.assurances_queue: List[Assurance] = []
        self.preimage_queue: List[Preimage] = []
        self.ring_data = ring_data

        self._ticket_queue_lock = asyncio.Lock()

    def create_ticket_body(self, ticket_data: TicketEnvelope, ring_context: RingContext, entropy: bytes) -> TicketBody:
        if ticket_data.attempt >= TICKET_ENTRIES:
            raise ValueError(SafroleErrorCode.bad_ticket_attempt)

        vrf_input_data = ticket_data.generate_vrf_input(entropy)

        aux_data = b''

        try:
            logging.DEBUG and logging.debug(f'Validating ticket with entropy {entropy.hex()}')
            ring_vrf_output = ring_context.ring_vrf_verify(vrf_input_data, aux_data, bytes(ticket_data.signature))

        except ValueError as e:
            raise ValueError(SafroleErrorCode.bad_ticket_proof)

        return TicketBody(id=ring_vrf_output, attempt=ticket_data.attempt)

    async def add_ticket(self, ticket_data: TicketEnvelope, ring_public_keys: List[bytes], entropy: bytes):
        ring_context = RingContext(self.ring_data, ring_public_keys)
        ticket_body = self.create_ticket_body(ticket_data, ring_context, entropy)
        async with self._ticket_queue_lock:
            self.tickets_queue[ticket_body.id] = ticket_data

    def can_add_own_ticket(self, timeslot: int) -> bool:
        return len(self.own_tickets_next) < TICKET_ENTRIES and timeslot % EPOCH_TIMESLOTS < TICKET_SUBMISSION_END_SLOT

    async def add_own_ticket(
            self, ring_context: RingContext, entropy: bytes, keypair: BandersnatchKeypair, author_index: int,
            epoch_index: int = None, pubsub: PubSub = None
    ):

        if len(self.tickets_queue) > TICKET_ENTRIES:
            raise ValueError("Too many tickets")

        attempt = len(self.own_tickets_next)

        # GP-0.7.2-eq:6.31
        vrf_input_data = vrf_input_ticket_seal(entropy, attempt)
        aux_data = b''

        signature = ring_context.ring_vrf_sign(author_index, keypair.private_key, vrf_input_data, aux_data)

        ticket = TicketEnvelope(
            attempt=attempt,
            signature=signature
        )

        ticket_id = vrf_output(keypair.private_key, vrf_input_data)

        logging.info(f'🎫 Generated ticket: {format_hash(ticket_id)}')
        logging.DEBUG and logging.debug(f'Generated ticket: id = {format_hash(ticket_id)} with entropy {format_hash(entropy)}')

        async with self._ticket_queue_lock:
            self.tickets_queue[ticket_id] = ticket
        self.own_tickets_next.append(ticket_id)

        # Notify new ticket is added
        if pubsub and epoch_index is not None:
            await pubsub.publish(PubSubSignal(topic=MESSAGE_TYPES.TICKET_ADD, data=[epoch_index, attempt, signature]))


    async def collect_tickets(self) -> List[TicketEnvelope]:
        """
        Collect tickets to include in a block

        Returns
        -------
        List[TicketEnvelope]
        """

        async with self._ticket_queue_lock:
            collected_tickets = sorted(self.tickets_queue.items())[:MAXIMUM_EXTRINSIC_TICKETS]

            # Remove from queue
            for key in [key for key, _ in collected_tickets]:
                self.tickets_queue.pop(key)

        return [ticket for _, ticket in collected_tickets]

    def is_own_ticket(self, ticket_id: bytes) -> bool:
        pass

    def own_ticket_count(self) -> int:
        return len(self.own_tickets_next)

    async def clear_own_tickets(self):
        async with self._ticket_queue_lock:
            for ticket_id in self.own_tickets_next:
                del self.tickets_queue[ticket_id]
        self.own_tickets_next = []

    async def clear_tickets(self):
        async with self._ticket_queue_lock:
            self.tickets_queue = {}
        self.own_tickets_next = []

    async def process_epoch_change(self):
        self.own_tickets_current = self.own_tickets_next
        self.own_tickets_next = []
        async with self._ticket_queue_lock:
            self.tickets_queue = {}

    def add_guarantee(self, guarantee: Guarantee):
        self.guarentees_queue.append(guarantee)

    async def collect_guarantees(self) -> List[Guarantee]:
        guarentees = self.guarentees_queue
        self.guarentees_queue = []
        return guarentees

    def add_assurance(self, assurance: Assurance):
        self.assurances_queue.append(assurance)

    def collect_assurances(self) -> List[Assurance]:
        assurances = self.assurances_queue
        self.assurances_queue = []
        return assurances

    def add_preimage(self, preimage: Preimage):
        self.preimage_queue.append(preimage)
        logging.info(f"🖼️ Added preimage: {format_hash(blake2b_256_hash(preimage.blob))} for service: {preimage.requester}")

    def collect_preimages(self, service_state: ServicesState) -> List[Preimage]:
        # Check which of present preimages are actually requested
        preimages = []
        new_queue = []

        # Sort preimages as requited per GP
        self.preimage_queue = sorted(self.preimage_queue, key=lambda p: p.sort_key())

        for preimage in self.preimage_queue:
            if service_state.is_preimage_needed(preimage):
                preimages.append(preimage)
            else:
                new_queue.append(preimage)

        self.preimage_queue = new_queue

        return preimages


    async def process_block(self, block: Block):
        """
        Inspects and cleans up the ExtrinsicQueue for data that is already present in the block

        Parameters
        ----------
        block: A succesfully imported Block

        Returns
        -------

        """
        delete_queue = []
        for ticket_data in block.extrinsic.tickets:
            # TODO: make a reverse lookup
            for queued_ticket_id, queued_ticket_data in self.tickets_queue.items():
                if queued_ticket_data == ticket_data:
                    #del self.tickets_queue[queued_ticket_id]
                    delete_queue.append(queued_ticket_id)

        async with self._ticket_queue_lock:
            for queued_ticket_id in delete_queue:
                del self.tickets_queue[queued_ticket_id]


class WorkpackageExtrinsicAccumulator:

    def __init__(self):
        self.extrinsic_data: Dict[bytes, Dict[bytes, bytes]] = {}

    def add(self, work_package: WorkPackage, extrinsics: List[bytes]):
        self.extrinsic_data[work_package.hash()] = {blake2b_256_hash(e): e for e in extrinsics}

    def get(self, work_package: WorkPackage, extrinsic_hash: bytes, extrinsic_length: int) -> Optional[bytes]:
        extrinsic = self.extrinsic_data.get(work_package.hash(), {}).get(extrinsic_hash, None)

        if extrinsic is not None and extrinsic_length == len(extrinsic):
            return extrinsic
        else:
            return None

    def clear(self, work_package: WorkPackage):
        self.extrinsic_data.pop(work_package.hash(), None)
