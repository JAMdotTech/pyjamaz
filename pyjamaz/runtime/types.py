import typing
from dataclasses import dataclass, field

from jamcodec.mixins import Serializable
from jamcodec.types import Bytes, H256, Option, U16
from pyjamaz.models.common import WorkPackage, WorkPackageStatus, WorkReport, Credential, Guarantee


@dataclass
class WorkPackageQueueItem(Serializable):
    work_package: WorkPackage = field(metadata={'codec': WorkPackage.to_codec_def()})
    status: WorkPackageStatus = field(metadata={'codec': WorkPackageStatus.to_codec_def()})
    work_report: typing.Optional[WorkReport] = field(default=None, metadata={'codec': WorkReport.to_codec_def()})
    signatures: list[Credential] = field(default_factory=list, metadata={'codec': Credential.to_codec_def()})
    core_index: typing.Optional[int] = field(default=None, metadata={'codec': Option(U16)})
    bundle: typing.Optional[bytes] = field(default=None, metadata={'codec': Option(Bytes)})

    @property
    def authorization_context(self):
        """A local snapshot-bound authorization; never part of a wire message."""
        return getattr(self, '_authorization_context', None)

    @authorization_context.setter
    def authorization_context(self, value):
        self._authorization_context = value

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
