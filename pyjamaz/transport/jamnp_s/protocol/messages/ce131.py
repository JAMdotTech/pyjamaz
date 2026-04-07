from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import Array, U8, U32


@dataclass
class MsgCE131SafroleTicket(Serializable):
    attempt: int = field(metadata={"codec": U8})
    proof: bytes = field(metadata={"codec": Array(U8, 784)})


@dataclass
class MsgCE131SafroleTicketDistribution(Serializable):
    epoch_index: int = field(metadata={"codec": U32})
    ticket: MsgCE131SafroleTicket = field(metadata={"codec": MsgCE131SafroleTicket.to_codec_def()})
