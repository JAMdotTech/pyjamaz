from dataclasses import dataclass, field
from typing import List

from pyjamaz.types.safrole import TicketEnvelope

from pyjamaz.serialization import Serializable
from pyjamaz.state.base import State


@dataclass
class Header(Serializable, State):
    timeslot: int = field(metadata={'length': 4})  # Block's timeslot
    vrf_signature: bytes = field(metadata={'length': 32})  # entropy-yielding VRF signature


@dataclass
class Extrinsic(Serializable, State):
    tickets: List[TicketEnvelope] = field(metadata={})


@dataclass
class Block(Serializable, State):
    header: Header
    extrinsic: Extrinsic
