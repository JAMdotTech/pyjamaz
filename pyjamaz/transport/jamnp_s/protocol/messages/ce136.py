from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256, U8, Vec


@dataclass
class MsgCE136HashRequest(Serializable):
    hash: bytes = field(metadata={"codec": H256})


@dataclass
class MsgCE136WorkReport(Serializable):
    report: bytes = field(metadata={"codec": Vec(U8)})
