from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from jamcodec.base import JamBytes

from pyjamaz.graypaper_constants import EPOCH_TIMESLOTS
from pyjamaz.models.block import TicketEnvelope
from pyjamaz.transport.jamnp_s.protocol.base import StreamHandler
from pyjamaz.transport.jamnp_s.protocol.messages.ce132 import MsgCE132SafroleTicketDistribution
from pyjamaz.transport.jamnp_s.types import ManagedStream, StreamKind

logger = logging.getLogger("pyjamaz.transport.jamnp_s")


@dataclass
class CE132StreamState:
    active: bool = True


class CE132Handler(StreamHandler):
    kind = StreamKind.CE132_SafroleTicketDistributionStep2

    def __init__(self, context) -> None:
        super().__init__(context)
        self._streams = {}

    def init_stream(self, stream: ManagedStream) -> None:
        self._streams[stream.stream_key] = CE132StreamState()

    def initiate_ticket_distribution(self, conn, msg: MsgCE132SafroleTicketDistribution) -> ManagedStream:
        stream = self.open_outgoing(conn)
        logger.info(f"Distribute ticket on stream id: {stream.stream_id} to {conn.host}:{conn.port}")
        conn.send(
            stream.stream_id,
            stream.create_message(msg.to_jam_bytes().to_bytes(), add_stream_type=True),
            end_stream=True,
        )
        return stream

    def initiator_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.warning(f"Unexpected data in CE132 initiator: {len(data)} bytes")
        raise ValueError("Unexpected data in CE132 initiator")

    def acceptor_message(self, stream: ManagedStream, data: bytes) -> None:
        logger.debug(f"CE132 acceptor stream {stream.stream_id} received ticket")
        self._handle_received_ticket(
            stream,
            MsgCE132SafroleTicketDistribution.from_jam_bytes(JamBytes(data)),
        )

    def initiator_fin(self, stream: ManagedStream) -> None:
        logger.debug("Success with code 0")

    def acceptor_fin(self, stream: ManagedStream) -> None:
        logger.debug("Success with code 0")

    def initiator_reset(self, stream: ManagedStream, reset_code: int) -> None:
        logger.error(f"Failed with code {reset_code}")

    def acceptor_reset(self, stream: ManagedStream, reset_code: int) -> None:
        logger.error(f"Failed with code {reset_code}")

    def on_close(self, stream: ManagedStream) -> None:
        self._streams.pop(stream.stream_key, None)

    def _handle_received_ticket(self, stream: ManagedStream, msg: MsgCE132SafroleTicketDistribution) -> None:
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
                logger.info("Ticket already in accumulator (via CE132), ignoring")
                stream.conn.send(stream.stream_id, b"", end_stream=True)
                return

            asyncio.create_task(
                self.context.app.block_extrinsic.add_ticket_body(
                    ticket_envelope,
                    ticket_body,
                )
            )
            logger.info(f"Valid ticket received via CE132 (forwarded) for epoch {msg.epoch_index}")
        except ValueError as exc:
            logger.error(f"Invalid ticket: {exc}")
            stream.send_reset(3)
            return

        stream.conn.send(stream.stream_id, b"", end_stream=True)
