from __future__ import annotations

from dataclasses import dataclass

from pyjamaz.transport.jamnp_s.protocol.messages.ce131 import (
    MsgCE131SafroleTicket,
    MsgCE131SafroleTicketDistribution,
)


@dataclass
class MsgCE132SafroleTicket(MsgCE131SafroleTicket):
    pass


@dataclass
class MsgCE132SafroleTicketDistribution(MsgCE131SafroleTicketDistribution):
    pass
