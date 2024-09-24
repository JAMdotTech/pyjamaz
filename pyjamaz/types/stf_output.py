import enum
from dataclasses import dataclass, field
from typing import Optional

from jamcodec.mixins import Serializable
from jamcodec.types import Option, Enum
from pyjamaz.types.block import OutputMarks


class SafroleErrorCode(Serializable, enum.Enum):
    bad_slot = 0  # Timeslot value must be strictly monotonic.
    unexpected_ticket = 1  # Received a ticket while in epoch's tail.
    bad_ticket_order = 2  # Tickets must be sorted.
    bad_ticket_proof = 3  # Invalid ticket ring proof.
    bad_ticket_attempt = 4  # Invalid ticket attempt value.
    reserved = 5  # Reserved
    duplicate_ticket = 6  # Found a ticket duplicate.
    too_many_tickets = 7  # Found amount of tickets > K


@dataclass
class SafroleOutput(Serializable):
    ok: Optional[OutputMarks] = field(default=None, metadata={'codec': Option(OutputMarks.to_codec_def())})  # Markers
    err: Optional[SafroleErrorCode] = field(default=None, metadata={'codec': Option(SafroleErrorCode.to_codec_def())})  # Error code (not specified in the Graypaper)

    _codec_type_def = Enum(
        ok=OutputMarks.to_codec_def(),
        err=SafroleErrorCode.to_codec_def()
    )

    def serialize(self) -> dict:
        if self.err is not None:
            return {'err': self.err.serialize()}
        else:
            return {'ok': self.ok.serialize()}


@dataclass
class STFOutput(Serializable):
    safrole: SafroleOutput
