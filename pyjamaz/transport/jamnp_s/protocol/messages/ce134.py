from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from jamcodec.mixins import Serializable
from jamcodec.types import H256, H512, Map, U16

from pyjamaz.models.common import WorkPackage


@dataclass
class MsgCE134WorkPackageSharing(Serializable):
    core_index: int = field(metadata={"codec": U16})
    segment_root_map: Dict[bytes, bytes] = field(metadata={"codec": Map(H256, H256)})


@dataclass
class MsgCE134WorkPackageBundle(Serializable):
    work_package: WorkPackage = field(metadata={"codec": WorkPackage.to_codec_def()})


@dataclass
class MsgCE134RefineResponse(Serializable):
    report_hash: bytes = field(metadata={"codec": H256})
    signature: bytes = field(metadata={"codec": H512})
