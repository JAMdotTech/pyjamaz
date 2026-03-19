import typing
from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import H256
from pyjamaz.models.block import Credential, Guarantee
from pyjamaz.models.common import WorkPackage, WorkPackageStatus, WorkReport


@dataclass
class WorkPackageQueueItem(Serializable):
    work_package: WorkPackage = field(metadata={'codec': WorkPackage.to_codec_def()})
    status: WorkPackageStatus = field(metadata={'codec': WorkPackageStatus.to_codec_def()})
    work_report: typing.Optional[WorkReport] = field(default=None, metadata={'codec': WorkReport.to_codec_def()})
    signatures: list[Credential] = field(default_factory=list, metadata={'codec': Credential.to_codec_def()})

    def create_guarantee(self, slot: int) -> Guarantee:
        return Guarantee(
            report=self.work_report,
            slot=slot,
            signatures=self.signatures
        )


@dataclass
class GuaranteeQueueItem(Serializable):
    work_package_hash: bytes = field(metadata={'codec': H256})
    signature: Credential = field(metadata={'codec': Credential.to_codec_def()})
