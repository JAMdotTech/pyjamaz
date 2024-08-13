from dataclasses import dataclass, field
from typing import List

from pyjamaz.types.safrole import TicketEnvelope

from pyjamaz.mixins import SerializableMixin
from pyjamaz.state.base import State
from scalecodec.types import U32, Vec, H512, H256


@dataclass
class Header(SerializableMixin, State):
    timeslot: int = field(metadata={'scale': U32})  # Block's timeslot
    vrf_signature: bytes = field(metadata={'scale': H256})  # entropy-yielding VRF signature


@dataclass
class Extrinsic(SerializableMixin, State):
    tickets: List[TicketEnvelope] = field(metadata={'scale': Vec(TicketEnvelope.scale_type_def())})


@dataclass
class Block(SerializableMixin, State):
    header: Header
    extrinsic: Extrinsic
