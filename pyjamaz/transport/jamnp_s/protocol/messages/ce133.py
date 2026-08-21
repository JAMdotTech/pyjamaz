from __future__ import annotations

from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import U16, U8, Vec

from pyjamaz.models.common import WorkPackage


@dataclass
class MsgCE133WorkPackageSubmission(Serializable):
    core_index: int = field(metadata={"codec": U16})
    work_package: WorkPackage = field(metadata={"codec": WorkPackage.to_codec_def()})


@dataclass
class MsgCE133Extrinsic(Serializable):
    bytes_: bytes = field(metadata={"codec": Vec(U8)})
