from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from itertools import islice
from typing import Optional

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.decoding import decode_to_object
from jamcodec.exceptions import InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException
from jamcodec.types import Bytes, H256, Option, U32, Vec

from pyjamaz.availability import DataUnavailable, ImportedSegment, verify_import
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, EPOCH_TIMESLOTS, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import WellBalancedMerkleTree
from pyjamaz.models.app import D3LEntry
from pyjamaz.models.common import ValidatorData, WorkReport
from pyjamaz.storage import StorageEngine


@dataclass
class AvailabilitySource(Serializable):
    """Chain-backed routing and retention metadata; never populated from builder mappings."""

    report: WorkReport = field(metadata={'codec': WorkReport.to_codec_def()})
    validators: list[ValidatorData] = field(metadata={'codec': Vec(ValidatorData.to_codec_def())})
    guarantors: list[ValidatorData] = field(metadata={'codec': Vec(ValidatorData.to_codec_def())})
    registered_block: bytes = field(metadata={'codec': H256})
    registered_slot: int = field(metadata={'codec': U32})
    assured_block: Optional[bytes] = field(default=None, metadata={'codec': Option(H256)})
    assured_slot: Optional[int] = field(default=None, metadata={'codec': Option(U32)})

    @property
    def spec(self):
        return self.report.package_spec

    @property
    def identity(self):
        return blake2b_256_hash(self.registered_block + self.report.hash())


class DataAvailabilityStore:

    LOCAL_REPORT_BACKFILL_BATCH_SIZE = 64

    def __init__(self, storage_engine: StorageEngine):
        self.storage_engine = storage_engine
        self._active_roots = {}
        self._local_report_keys = None

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

    def store_work_report(self, report: WorkReport, bundle: bytes, exports: list[bytes], *, artifacts=None) -> None:
        """Retain the locally computed data and the 14.14 package-to-root correspondence."""
        spec = report.package_spec
        if artifacts is not None:
            from pyjamaz.availability import verify_validator_shard

            if (artifacts.spec != spec or len(artifacts.shards) != spec.erasure_shards
                    or {shard.shard_index for shard in artifacts.shards} != set(range(spec.erasure_shards))):
                raise ProcessWorkpackageError("availability artifacts differ from report")
            for shard in artifacts.shards:
                verify_validator_shard(shard, spec)
            for shard in artifacts.shards:
                self.store_validator_shard(spec, shard)
        self.store_segments(D3LEntry(spec.exports_root, exports))
        self.storage_engine.put(b'bundle:' + spec.hash, bundle)
        self.storage_engine.put(b'package-root:' + spec.hash, spec.exports_root)
        self.storage_engine.put(b'local-report-v1:' + spec.erasure_root, report.to_jam_bytes().to_bytes())
        self._add_index(b'local-exports-v1:' + spec.exports_root, spec.erasure_root)

    def _index(self, key: bytes) -> list[bytes]:
        try:
            raw = self._retrieve(key, 'availability index is unavailable')
        except DataUnavailable:
            return []
        try:
            entries = decode_to_object(Vec(H256), JamBytes(raw))
            if entries != sorted(set(entries)) or Vec(H256).encode(entries).to_bytes() != raw:
                raise ValueError('noncanonical availability index')
            return entries
        except (ValueError, InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException) as exc:
            raise DataUnavailable('stored availability index is invalid') from exc

    def _add_index(self, key: bytes, identity: bytes) -> None:
        entries = sorted(set(self._index(key)) | {identity})
        self.storage_engine.put(key, Vec(H256).encode(entries).to_bytes())

    @staticmethod
    def _validate_source(source: AvailabilitySource) -> None:
        from pyjamaz.availability import _shard_dimensions

        _shard_dimensions(source.spec)
        if len(source.validators) != source.spec.erasure_shards:
            raise ProcessWorkpackageError('source validator count differs from report')
        if len({v.ed25519 for v in source.validators}) != len(source.validators):
            raise ProcessWorkpackageError('duplicate source validator identity')
        # Verified guarantee signers may belong to the previous rotation's set.
        if len({v.ed25519 for v in source.guarantors}) != len(source.guarantors):
            raise ProcessWorkpackageError('duplicate guarantor identity')
        if (not isinstance(source.registered_block, bytes) or len(source.registered_block) != 32
                or isinstance(source.registered_slot, bool) or not isinstance(source.registered_slot, int)
                or not 0 <= source.registered_slot < 2**32
                or (source.assured_block is None) != (source.assured_slot is None)
                or (source.assured_block is not None
                    and (not isinstance(source.assured_block, bytes) or len(source.assured_block) != 32
                         or isinstance(source.assured_slot, bool) or not isinstance(source.assured_slot, int)
                         or not source.registered_slot <= source.assured_slot < 2**32))):
            raise ProcessWorkpackageError('invalid source block references')

    def register_source(self, source: AvailabilitySource) -> None:
        # GP-0.8.0-eq:14.14 / sec:14.4: the accepted report fixes the source set and core.
        self._validate_source(source)
        try:
            encoded = source.to_jam_bytes().to_bytes()
        except (ValueError, InvalidScaleTypeValueException) as exc:
            raise ProcessWorkpackageError('invalid source metadata encoding') from exc
        identity = source.identity
        self.storage_engine.put(b'source-v1:' + identity, encoded)
        for kind, value in ((b'package', source.spec.hash), (b'exports', source.spec.exports_root),
                            (b'erasure', source.spec.erasure_root)):
            self._add_index(b'source-index-v1:' + kind + value, identity)
        self._add_index(b'source-list-v1', identity)

    def _source(self, identity: bytes) -> AvailabilitySource:
        raw = self._retrieve(b'source-v1:' + identity, 'source metadata is unavailable')
        try:
            source = AvailabilitySource.from_jam_bytes(JamBytes(raw))
            self._validate_source(source)
            if source.identity != identity or source.to_jam_bytes().to_bytes() != raw:
                raise ValueError('noncanonical or mismatched source metadata')
            return source
        except (ValueError, InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException,
                ProcessWorkpackageError) as exc:
            raise DataUnavailable('stored source metadata is invalid') from exc

    def sources(self) -> list[AvailabilitySource]:
        sources = []
        for identity in self._index(b'source-list-v1'):
            try:
                sources.append(self._source(identity))
            except DataUnavailable:
                # Keep the index entry so retained blocks can repair this record later.
                continue
        return sources

    def source_for(self, *, package_hash=None, exports_root=None, erasure_root=None, canonical=None):
        kind, value = ((b'package', package_hash) if package_hash is not None else
                       (b'exports', exports_root) if exports_root is not None else (b'erasure', erasure_root))
        if not isinstance(value, bytes) or len(value) != 32:
            raise DataUnavailable('invalid source lookup')
        candidates = []
        for identity in self._index(b'source-index-v1:' + kind + value):
            try:
                source = self._source(identity)
            except DataUnavailable:
                continue
            actual = {b'package': source.spec.hash, b'exports': source.spec.exports_root,
                      b'erasure': source.spec.erasure_root}[kind]
            if actual != value:
                raise DataUnavailable('stored source index does not match its metadata')
            if canonical is None or canonical(source.registered_block):
                candidates.append(source)
        if not candidates:
            raise DataUnavailable('chain-backed source metadata is unavailable')
        return max(candidates, key=lambda source: (source.registered_slot, source.identity))

    def mark_assured(self, report: WorkReport, block_hash: bytes, slot: int, canonical) -> None:
        report_hash = report.hash()
        candidates = []
        for identity in self._index(b'source-index-v1:erasure' + report.package_spec.erasure_root):
            try:
                source = self._source(identity)
            except DataUnavailable:
                continue
            if (source.report.hash() == report_hash and source.registered_slot <= slot
                    and canonical(source.registered_block)):
                candidates.append(source)
        if not candidates:
            raise DataUnavailable('matching source registration is unavailable')
        source = max(candidates, key=lambda record: (record.registered_slot, record.identity))
        if source.assured_block is not None and canonical(source.assured_block):
            return  # Replaying history must preserve an already known canonical assurance.
        self.register_source(replace(source, assured_block=block_hash, assured_slot=slot))

    def specification(self, erasure_root: bytes, canonical=None):
        try:
            return self.source_for(erasure_root=erasure_root, canonical=canonical).spec
        except DataUnavailable:
            return self._local_report(erasure_root).package_spec

    def _local_report(self, erasure_root: bytes) -> WorkReport:
        from pyjamaz.availability import _shard_dimensions

        raw = self._retrieve(b'local-report-v1:' + erasure_root, 'unknown erasure root')
        try:
            report = WorkReport.from_jam_bytes(JamBytes(raw))
            _shard_dimensions(report.package_spec)
            if report.package_spec.erasure_root != erasure_root or report.to_jam_bytes().to_bytes() != raw:
                raise ValueError('noncanonical or mismatched local report')
            return report
        except (ValueError, InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException,
                ProcessWorkpackageError) as exc:
            raise DataUnavailable('stored local report is invalid') from exc

    def _indexed_local_report_for_exports(self, exports_root: bytes) -> Optional[WorkReport]:
        # The same exports may have several bundle/validator specifications.
        for erasure_root in reversed(self._index(b'local-exports-v1:' + exports_root)):
            try:
                report = self._local_report(erasure_root)
            except DataUnavailable:
                continue
            if report.package_spec.exports_root != exports_root:
                raise DataUnavailable('stored local exports index does not match its report')
            return report
        return None

    def _backfill_local_report_indexes(self) -> None:
        """Index reports retained before the exports-to-report index was introduced."""
        if self._local_report_keys is None:
            self._local_report_keys = self.storage_engine.iter_keys()
        prefix = b'local-report-v1:'
        # Advance once through keys, without reading bundle or shard payloads.
        for key in islice(self._local_report_keys, self.LOCAL_REPORT_BACKFILL_BATCH_SIZE):
            if not key.startswith(prefix) or len(key) != len(prefix) + 32:
                continue
            try:
                report = self._local_report(key[len(prefix):])
                self._add_index(b'local-exports-v1:' + report.package_spec.exports_root,
                                report.package_spec.erasure_root)
            except DataUnavailable:
                continue

    def local_report_for_exports(self, exports_root: bytes) -> WorkReport:
        """Find a locally computed source without claiming chain-backed availability."""
        if not isinstance(exports_root, bytes) or len(exports_root) != 32:
            raise DataUnavailable('invalid exports root')
        report = self._indexed_local_report_for_exports(exports_root)
        if report is None:
            self._backfill_local_report_indexes()
            report = self._indexed_local_report_for_exports(exports_root)
        if report is None:
            raise DataUnavailable('locally computed source metadata is unavailable')
        return report

    def _source_index_complete(self, kind, value, sources) -> bool:
        """Missing source context protects only payloads whose indexes reference it."""
        try:
            identities = set(self._index(b'source-index-v1:' + kind + value))
        except DataUnavailable:
            return False
        fields = {b'package': 'hash', b'exports': 'exports_root', b'erasure': 'erasure_root'}
        expected = {source.identity for source in sources.values()
                    if getattr(source.spec, fields[kind]) == value}
        return bool(identities) and identities == expected

    @staticmethod
    def _shard_key(prefix, spec, index):
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < spec.erasure_shards:
            raise ProcessWorkpackageError('invalid validator shard index')
        return prefix + spec.erasure_root + index.to_bytes(2, 'little')

    def store_validator_shard(self, spec, shard) -> None:
        from pyjamaz.availability import verify_validator_shard

        verify_validator_shard(shard, spec)
        key = self._shard_key(b'row-v1:', spec, shard.shard_index)
        row = (blake2b_256_hash(shard.bundle_shard)
               + Vec(Bytes).encode(list(shard.segment_shards)).to_bytes()
               + Vec(Bytes).encode(list(shard.justification)).to_bytes())
        self.storage_engine.put(self._shard_key(b'audit-v1:', spec, shard.shard_index), shard.bundle_shard)
        self.storage_engine.put(key, row)
        # Metadata is published only after both payload records have been written.
        self._add_index(b'row-index-v1:' + spec.erasure_root, shard.shard_index.to_bytes(32, 'little'))

    def _row(self, spec, index):
        try:
            data = self._retrieve(self._shard_key(b'row-v1:', spec, index), 'assigned shard is unavailable')
            stream = JamBytes(data)
            bundle_hash = bytes(stream.get_next_bytes(32))
            row = tuple(decode_to_object(Vec(Bytes), stream))
            proof = tuple(decode_to_object(Vec(Bytes), stream))
            from pyjamaz.erasure import erasure_data_shards

            count = spec.exports_count + (spec.exports_count + 63) // 64
            if (stream.get_remaining_length() or len(row) != count
                    or any(len(chunk) != EC_SEGMENT_SIZE // erasure_data_shards(spec.erasure_shards) for chunk in row)
                    or bundle_hash + Vec(Bytes).encode(list(row)).to_bytes()
                    + Vec(Bytes).encode(list(proof)).to_bytes() != data
                    or not WellBalancedMerkleTree.verify(bundle_hash + WellBalancedMerkleTree(list(row)).root(),
                                                        index, spec.erasure_shards, proof, spec.erasure_root)):
                raise ValueError('invalid assigned shard commitment')
            return bundle_hash, row, proof
        except (ValueError, InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException) as exc:
            raise DataUnavailable('stored assigned shard is invalid') from exc

    def retrieve_validator_shard(self, spec, index):
        from pyjamaz.availability import ValidatorShard, verify_validator_shard

        bundle_hash, row, proof = self._row(spec, index)
        bundle = self._retrieve(self._shard_key(b'audit-v1:', spec, index), 'audit shard is unavailable')
        shard = ValidatorShard(index, bundle, row, proof)
        try:
            verify_validator_shard(shard, spec)
        except ProcessWorkpackageError as exc:
            raise DataUnavailable('stored audit shard is invalid') from exc
        return shard

    def retrieve_segment_shard(self, spec, shard_index, segment_index):
        # JAMNP-S-e0b7d291:CE140: outer path ++ bundle hash ++ row-local path.
        bundle_hash, row, proof = self._row(spec, shard_index)
        if isinstance(segment_index, bool) or not isinstance(segment_index, int) or not 0 <= segment_index < len(row):
            raise ProcessWorkpackageError('segment shard index out of range')
        return row[segment_index], proof + (bundle_hash,) + tuple(WellBalancedMerkleTree(list(row)).trace(segment_index))

    @contextmanager
    def hold(self, erasure_root):
        self._active_roots[erasure_root] = self._active_roots.get(erasure_root, 0) + 1
        try:
            yield
        finally:
            self._active_roots[erasure_root] -= 1
            if not self._active_roots[erasure_root]:
                del self._active_roots[erasure_root]

    def prune(self, finalized_slot: int, canonical, finalized) -> None:
        # GP-0.8.0-sec:14.3.1: audit data until assurance finality; D3L at least 672 epochs.
        sources = self.sources()
        by_identity = {source.identity: source for source in sources}
        for root in {source.spec.erasure_root for source in sources}:
            records = [source for source in sources if source.spec.erasure_root == root and canonical(source.registered_block)]
            if (not records or root in self._active_roots
                    or not self._source_index_complete(b'erasure', root, by_identity)):
                continue
            spec = records[0].spec
            audit_expired = all(source.assured_block is not None and finalized(source.assured_block) for source in records)
            exports_expired = all(finalized_slot >= source.registered_slot + 672 * EPOCH_TIMESLOTS for source in records)
            for encoded_index in self._index(b'row-index-v1:' + root):
                index = int.from_bytes(encoded_index, 'little')
                if audit_expired:
                    self.storage_engine.delete(self._shard_key(b'audit-v1:', spec, index))
                # CE 137/138 still need the row's root and co-path until audit finality.
                if exports_expired and audit_expired:
                    self.storage_engine.delete(self._shard_key(b'row-v1:', spec, index))
            for source in records:
                shared = [s for s in sources if s.spec.hash == source.spec.hash and canonical(s.registered_block)]
                if (audit_expired and self._source_index_complete(b'package', source.spec.hash, by_identity)
                        and all(s.assured_block is not None and finalized(s.assured_block)
                                and s.spec.erasure_root not in self._active_roots for s in shared)):
                    self.storage_engine.delete(b'bundle:' + source.spec.hash)
            same_exports = [source for source in sources if source.spec.exports_root == spec.exports_root]
            if (exports_expired and self._source_index_complete(b'exports', spec.exports_root, by_identity)
                    and all(finalized_slot >= source.registered_slot + 672 * EPOCH_TIMESLOTS
                            and source.spec.erasure_root not in self._active_roots for source in same_exports)):
                self.storage_engine.delete(spec.exports_root)
                for index in range(spec.exports_count):
                    self.storage_engine.delete(self._import_key(spec.exports_root, index))


