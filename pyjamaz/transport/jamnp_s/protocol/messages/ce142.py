from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U32


@dataclass
class MsgCE142PreimageAnnouncement(Serializable):
    service_id: int = field(metadata={"codec": U32})
    hash: bytes = field(metadata={"codec": H256})
    preimage_length: int = field(metadata={"codec": U32})
