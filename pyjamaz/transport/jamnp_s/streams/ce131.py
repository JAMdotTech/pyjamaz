from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from jamcodec.base import JamBytes

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.models.block import TicketEnvelope
from pyjamaz.transport.jamnp_s.streams.base import ContextualStreamHandler
from pyjamaz.transport.jamnp_s.message_types import (
    MsgCE131SafroleTicket,
    MsgCE131SafroleTicketDistribution,
)
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE131StreamState:
    active: bool = True


class CE131Handler(ContextualStreamHandler):
    kind = StreamKind.CE131_SafroleTicketDistributionStep1

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE131StreamState()

    async def broadcast_own_ticket(self, data) -> int:
        epoch_index, attempt, proof = data
        msg = MsgCE131SafroleTicketDistribution(
            epoch_index=epoch_index,
            ticket=MsgCE131SafroleTicket(attempt=attempt, proof=proof),
        )

        distributed_count = 0
        for conn in self.context.connections.values():
            if not conn.is_connected():
                continue

            try:
                stream = self.open_outgoing(conn)
                logger.info(f"Send ticker announcement on stream id: {stream.stream_id} to {conn.host}:{conn.port}")
                conn.send(
                    stream.stream_id,
                    stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
                    end_stream=True,
                )
                distributed_count += 1
            except Exception as exc:
                logger.error(f"Failed to distribute ticket to peer {conn.host}:{conn.port}: {exc}")

        logger.info(f"Distributed ticket to {distributed_count} peers")
        return distributed_count

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE131 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE131 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug(f"CE131 acceptor stream {stream.stream_id} received ticket")
        self._handle_received_ticket(
            stream,
            MsgCE131SafroleTicketDistribution.from_jam_bytes(JamBytes(data)),
        )

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.info("Finished with FIN")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.info("Finished with FIN")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)

    def _handle_received_ticket(self, stream: ManagedStream, msg: MsgCE131SafroleTicketDistribution) -> None:
        logger.info(f"Received ticket for epoch {msg.epoch_index}")

        current_epoch = self.context.app.working_state.timeslot.number // EPOCH_TIMESLOTS
        if msg.epoch_index < current_epoch:
            logger.warning(f"Invalid epoch index {msg.epoch_index}, current epoch is {current_epoch}")
            stream.send_reset(1)
            return

        try:
            ring_public_keys = [v.bandersnatch for v in self.context.app.working_state.safrole.validators]
            entropy = self.context.app.working_state.entropy.entropy[2]
            ticket_envelope = TicketEnvelope(attempt=msg.ticket.attempt, signature=msg.ticket.proof)
            ticket_body = self.context.app.block_extrinsic.create_ticket_body(
                ticket_envelope,
                ring_public_keys,
                entropy,
            )

            if ticket_body in self.context.app.working_state.safrole.ticket_accumulator:
                logger.info("Ticket already in accumulator")
                stream.send_reset(2)
                return

            asyncio.create_task(
                self.context.app.block_extrinsic.add_ticket_body(
                    ticket_envelope,
                    ticket_body,
                )
            )
            logger.info(f"Ticket added for epoch {msg.epoch_index}")
        except ValueError as exc:
            logger.error(f"Invalid ticket: {exc}")
            stream.send_reset(3)
            return

        stream.conn.send(stream.stream_id, b"", end_stream=True)
