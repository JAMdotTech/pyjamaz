from jamcodec.base import JamBytes
from jamcodec.decoding import decode_to_object
from jamcodec.exceptions import InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException
from jamcodec.types import H256, Vec

from pyjamaz.availability import DataUnavailable, ImportedSegment, verify_import
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import WorkReport
from pyjamaz.storage import StorageEngine


class DataAvailabilityStore:

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine = storage_engine

    def _retrieve(self, key: bytes, message: str) -> bytes:
        try:
            data = self.storage_engine.get(key)
        except FileNotFoundError as exc:
            raise DataUnavailable(message) from exc
        if data is None:
            raise DataUnavailable(message)
        return data

    def retrieve_segments(self, segment_root: bytes) -> D3LEntry:
        data = self._retrieve(segment_root, "imported segments are unavailable")
        try:
            d3l_item = D3LEntry.from_jam_bytes(JamBytes(data))
            if (d3l_item.segment_root != segment_root
                    or d3l_item.to_jam_bytes().to_bytes() != data):
                raise ValueError("noncanonical or mismatched stored exports")
        except (ValueError, InvalidScaleTypeValueException,
                RemainingScaleBytesNotEmptyException) as exc:
            raise DataUnavailable("stored export segments are invalid") from exc
        return d3l_item

    def store_segments(self, segments: D3LEntry):
        self.storage_engine.put(segments.segment_root, segments.to_jam_bytes().to_bytes())

    @staticmethod
    def _import_key(root: bytes, index: int) -> bytes:
        if (not isinstance(root, bytes) or len(root) != 32
                or isinstance(index, bool) or not isinstance(index, int)
                or not 0 <= index < MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE):
            raise ProcessWorkpackageError("invalid import root or index")
        return b'import-v1:' + root + index.to_bytes(2, 'little')

    def store_import(self, root: bytes, index: int, imported: ImportedSegment) -> None:
        """Retain one verified segment and its direct proof, without establishing a package mapping."""
        key = self._import_key(root, index)
        verify_import(root, index, imported)
        encoded = imported.segment + Vec(H256).encode(list(imported.justification)).to_bytes()
        self.storage_engine.put(key, encoded)

    def retrieve_import(self, root: bytes, index: int) -> ImportedSegment:
        """Return a verified import; absent or corrupt cache data remains retryable."""
        data = self._retrieve(self._import_key(root, index), "import segment is unavailable")
        max_proof_depth = (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
        try:
            if not EC_SEGMENT_SIZE < len(data) <= EC_SEGMENT_SIZE + 1 + 32 * max_proof_depth:
                raise ValueError("invalid stored import length")
            stream = JamBytes(data)
            segment = bytes(stream.get_next_bytes(EC_SEGMENT_SIZE))
            proof = tuple(decode_to_object(Vec(H256), stream))
            imported = ImportedSegment(segment, proof)
            if segment + Vec(H256).encode(list(proof)).to_bytes() != data:
                raise ValueError("noncanonical stored import")
            verify_import(root, index, imported)
        except (ValueError, InvalidScaleTypeValueException,
                RemainingScaleBytesNotEmptyException, ProcessWorkpackageError) as exc:
            raise DataUnavailable("stored import is invalid") from exc
        return imported

    def segment_root_for_package(self, package_hash: bytes) -> bytes:
        return self._retrieve(b'package-root:' + package_hash, "segment-root mapping is unavailable")

    def store_work_report(self, report: WorkReport, bundle: bytes, exports: list[bytes]) -> None:
        """Retain the locally computed data and the 14.14 package-to-root correspondence."""
        spec = report.package_spec
        self.store_segments(D3LEntry(spec.exports_root, exports))
        self.storage_engine.put(b'bundle:' + spec.hash, bundle)
        self.storage_engine.put(b'package-root:' + spec.hash, spec.exports_root)


