from jamcodec.base import JamBytes
from pyjamaz.availability import DataUnavailable
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import WorkReport
from pyjamaz.storage import StorageEngine


class DataAvailabilityStore:

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine = storage_engine

    def retrieve_segments(self, segment_root: bytes) -> D3LEntry:
        data = self.storage_engine.get(segment_root)
        if data is None:
            raise DataUnavailable("imported segments are unavailable")
        d3l_item = D3LEntry.from_jam_bytes(JamBytes(data))
        return d3l_item

    def store_segments(self, segments: D3LEntry):
        self.storage_engine.put(segments.segment_root, segments.to_jam_bytes().to_bytes())

    def segment_root_for_package(self, package_hash: bytes) -> bytes:
        root = self.storage_engine.get(b'package-root:' + package_hash)
        if root is None:
            raise DataUnavailable("segment-root mapping is unavailable")
        return root

    def store_work_report(self, report: WorkReport, bundle: bytes, exports: list[bytes]) -> None:
        """Retain the locally computed data and the 14.14 package-to-root correspondence."""
        spec = report.package_spec
        self.store_segments(D3LEntry(spec.exports_root, exports))
        self.storage_engine.put(b'bundle:' + spec.hash, bundle)
        self.storage_engine.put(b'package-root:' + spec.hash, spec.exports_root)


