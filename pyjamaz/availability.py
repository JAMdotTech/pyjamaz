"""GP 0.8.0 import recovery, bundle assembly and availability commitments (section 14)."""

from dataclasses import dataclass, field

from jamcodec.base import JamBytes
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException, ScaleDecodeException
from jamcodec.types import H256, VarInt64, Vec

from pyjamaz.erasure import encode_chunks, erasure_data_shards, recover_segment
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import (
    EC_SEGMENT_SIZE, GAS_ACCUMULATION, GAS_REFINE, MAXIMUM_DEPENDENCIES_WORK_REPORT,
    MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE,
    MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE, MAXIMUM_SIZE_WORK_PACKAGE, MAXIMUM_WORK_ITEMS,
)
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import BinaryMerkleTree, ConstantDepthMerkleTree, WellBalancedMerkleTree
from pyjamaz.models.common import ImportSegment, WorkItem, WorkPackage, WorkPackageSpec


class DataUnavailable(ProcessWorkpackageError):
    """A runtime dependency may become available on a later attempt."""


def validate_work_package(package: WorkPackage) -> None:
    # GP-0.8.0-eq:14.2-14.9: package domain, dependencies, bandwidth, footprint and gas.
    if not 1 <= len(package.items) <= MAXIMUM_WORK_ITEMS:
        raise ProcessWorkpackageError("invalid work-item count")
    totals = (
        (sum(len(w.extrinsic) for w in package.items), MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE),
        (sum(len(w.import_segments) for w in package.items), MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE),
        (sum(w.export_count for w in package.items), MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE),
    )
    if any(count > limit for count, limit in totals):
        raise ProcessWorkpackageError("work-package manifest exceeds its limits")
    dependencies = {
        entry.tree_root for item in package.items for entry in item.import_segments
        if entry.is_work_package_hash
    }
    if len(dependencies) + len(package.context.prerequisites) > MAXIMUM_DEPENDENCIES_WORK_REPORT:
        raise ProcessWorkpackageError("too many work-package dependencies")
    import_footprint = EC_SEGMENT_SIZE + 32 * (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
    footprint = len(package.authorization) + len(package.authorizer_config) + sum(
        len(w.payload) + len(w.import_segments) * import_footprint + sum(x.len for x in w.extrinsic)
        for w in package.items
    )
    if footprint > MAXIMUM_SIZE_WORK_PACKAGE:
        raise ProcessWorkpackageError("work-package footprint exceeds its limit")
    # GP-0.8.0-eq:14.9, with inclusive limits from graypaper PR #563.
    if (sum(w.refine_gas_limit for w in package.items) > GAS_REFINE
            or sum(w.accumulate_gas_limit for w in package.items) > GAS_ACCUMULATION):
        raise ProcessWorkpackageError("work-package gas limits exceed core limits")



@dataclass(frozen=True)
class WorkPackageHash:
    """The tagged H+ import-reference variant from GP 14.3 and C.35."""

    value: bytes


def import_reference(entry: ImportSegment) -> bytes | WorkPackageHash:
    # GP-0.8.0-eq:C.35: the upper index bit distinguishes H+ from a segment root.
    return WorkPackageHash(entry.tree_root) if entry.is_work_package_hash else entry.tree_root


def resolve_import_root(mappings: dict[bytes, bytes], reference: bytes | WorkPackageHash) -> bytes:
    # GP-0.8.0-eq:14.15: L_l(r): H union H+ -> H, parameterized by l.
    if isinstance(reference, WorkPackageHash):
        try:
            return mappings[reference.value]
        except KeyError as exc:
            raise ProcessWorkpackageError("missing segment-root mapping") from exc
    return reference


@dataclass(frozen=True)
class ImportedSegment:
    segment: bytes
    justification: tuple[bytes, ...]


def verify_import(root: bytes, index: int, imported: ImportedSegment) -> None:
    """Check one S_l / J_l pair from GP-0.8.0-eq:14.15 against L_l(r)."""
    if (not isinstance(root, bytes) or len(root) != 32
            or isinstance(index, bool) or not isinstance(index, int)
            or not 0 <= index < MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE):
        raise ProcessWorkpackageError("invalid import root or segment index")
    if (not isinstance(imported.segment, bytes) or len(imported.segment) != EC_SEGMENT_SIZE
            or len(imported.justification) > (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
            or any(not isinstance(h, bytes) or len(h) != 32 for h in imported.justification)
            or not ConstantDepthMerkleTree.verify(imported.segment, index, imported.justification, root)):
        raise ProcessWorkpackageError("invalid import segment justification")


@dataclass
class BundleData:
    """The data lookups assumed by X, S_l and J_l; no storage or network access."""

    extrinsics: dict[bytes, bytes] = field(default_factory=dict)
    imports: dict[tuple[bytes, int], ImportedSegment] = field(default_factory=dict)

    @classmethod
    def from_parts(cls, package: WorkPackage, extrinsics: list[bytes], segments: list[bytes],
                   justifications: list[list[bytes]]) -> "BundleData":
        """Adapt the fuzzer's flat wire sequences, checking their manifest cardinalities."""
        manifests = [x for item in package.items for x in item.extrinsic]
        imports = [entry for item in package.items for entry in item.import_segments]
        if len(extrinsics) != len(manifests):
            raise ProcessWorkpackageError("extrinsic count does not match manifest")
        if len(segments) != len(imports) or len(justifications) != len(imports):
            raise ProcessWorkpackageError("import or justification count does not match manifest")
        data = cls()
        for manifest, blob in zip(manifests, extrinsics):
            if len(blob) != manifest.len or blake2b_256_hash(blob) != manifest.hash:
                raise ProcessWorkpackageError("extrinsic hash or length does not match manifest")
            data.extrinsics[manifest.hash] = bytes(blob)
        for entry, segment, proof in zip(imports, segments, justifications):
            key = (entry.tree_root, entry.index)
            imported = ImportedSegment(bytes(segment), tuple(bytes(h) for h in proof))
            if key in data.imports and data.imports[key] != imported:
                raise ProcessWorkpackageError("conflicting data for duplicate imports")
            data.imports[key] = imported
        return data

    def extrinsic_data(self, item: WorkItem) -> list[bytes]:
        # GP-0.8.0-eq:14.15: X(w) = [d | (H(d), |d|) in w_x], in manifest order.
        blobs = []
        for manifest in item.extrinsic:
            blob = self.extrinsics.get(manifest.hash)
            if blob is None or len(blob) != manifest.len or blake2b_256_hash(blob) != manifest.hash:
                raise ProcessWorkpackageError("extrinsic data is unavailable or invalid")
            blobs.append(blob)
        return blobs

    def _verified_imports(self, mappings: dict[bytes, bytes], item: WorkItem) -> list[ImportedSegment]:
        imports = []
        for entry in item.import_segments:
            imported = self.imports.get((entry.tree_root, entry.index))
            if imported is None:
                raise ProcessWorkpackageError("import segment is unavailable")
            verify_import(resolve_import_root(mappings, import_reference(entry)), entry.segment_index, imported)
            imports.append(imported)
        return imports

    def import_segments(self, mappings: dict[bytes, bytes], item: WorkItem) -> list[bytes]:
        # GP-0.8.0-eq:14.15: S_l(w) = [b[n] | M(b) = L_l(r), (r,n) in w_i].
        return [entry.segment for entry in self._verified_imports(mappings, item)]

    def import_justifications(self, mappings: dict[bytes, bytes], item: WorkItem) -> list[tuple[bytes, ...]]:
        # GP-0.8.0-eq:14.15: J_l(w) = [var(J_0(b,n)) | M(b) = L_l(r), (r,n) in w_i].
        return [entry.justification for entry in self._verified_imports(mappings, item)]

    def assemble_bundle(self, package: WorkPackage, mappings: dict[bytes, bytes]) -> bytes:
        # GP-0.8.0-eq:14.16: B(p,l) = E(p, X#(p_w), S_l#(p_w), J_l#(p_w)).
        from pyjamaz.bundle import encode_bundle

        extrinsics = [blob for item in package.items for blob in self.extrinsic_data(item)]
        imports = [entry for item in package.items for entry in self._verified_imports(mappings, item)]
        return encode_bundle(package, extrinsics, [entry.segment for entry in imports],
                             [list(entry.justification) for entry in imports])


def zero_pad(alignment: int, data: bytes) -> bytes:
    # GP-0.8.0-eq:14.19: P_n(x) pads x to a multiple of n octets.
    if alignment < 1:
        raise ValueError("padding alignment must be positive")
    return data + bytes(-len(data) % alignment)


def paged_proof_segments(exports: list[bytes]) -> list[bytes]:
    # GP-0.8.0-eq:14.12: P(s) = [P_WG(E(var(J_6(s,i)), var(L_6(s,i))))].
    tree = ConstantDepthMerkleTree(exports)
    hashes = [blake2b_256_hash(b'leaf' + segment) for segment in exports]
    page_depth = max(0, (len(exports) - 1).bit_length() - 6)
    pages = []
    for start in range(0, len(exports), 64):
        path = tree.trace(start)[:page_depth]
        encoded = Vec(H256).encode(path).to_bytes() + Vec(H256).encode(hashes[start:start + 64]).to_bytes()
        pages.append(zero_pad(EC_SEGMENT_SIZE, encoded))
    return pages


def decode_paged_proof(proof_segment: bytes, export_count: int,
                      page_index: int) -> tuple[tuple[bytes, ...], tuple[bytes, ...]]:
    """Decode P(s)[page_index] into J_6(s,page_index) and L_6(s,page_index)."""
    # GP-0.8.0-eq:14.12: P(s) contains two variable-length hash sequences, padded to WG.
    if (isinstance(export_count, bool) or not isinstance(export_count, int)
            or not 1 <= export_count <= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
            or isinstance(page_index, bool) or not isinstance(page_index, int)
            or not 0 <= page_index < (export_count + 63) // 64):
        raise ProcessWorkpackageError("invalid proof page index or export count")
    if not isinstance(proof_segment, bytes) or len(proof_segment) != EC_SEGMENT_SIZE:
        raise ProcessWorkpackageError("invalid proof page size")
    path_count = max(0, (export_count - 1).bit_length() - 6)
    leaf_count = min(64, export_count - page_index * 64)
    stream = JamBytes(proof_segment)
    sequences = []
    try:
        for expected_count in (path_count, leaf_count):
            start = stream.offset
            count = VarInt64.decode(stream)
            if (count != expected_count
                    or bytes(stream.data[start:stream.offset]) != VarInt64.encode(count).to_bytes()):
                raise ProcessWorkpackageError("invalid or noncanonical proof page count")
            sequences.append(tuple(bytes(stream.get_next_bytes(32)) for _ in range(count)))
    except (RemainingScaleBytesNotEmptyException, ScaleDecodeException) as exc:
        raise ProcessWorkpackageError("malformed proof page") from exc
    if any(stream.get_remaining_bytes()):
        raise ProcessWorkpackageError("proof page has nonzero padding")
    return sequences[0], sequences[1]


def import_justification(segment: bytes, segment_index: int, proof_segment: bytes,
                        export_count: int, exports_root: bytes) -> tuple[bytes, ...]:
    """Derive J_0(s,segment_index) from one recovered P(s) page."""
    # GP-0.8.0-eq:14.12, E.5-E.7: append the page-local co-path to J_6, root first.
    if (isinstance(segment_index, bool) or not isinstance(segment_index, int)
            or segment_index < 0):
        raise ProcessWorkpackageError("import segment index out of range")
    path, leaves = decode_paged_proof(proof_segment, export_count, segment_index // 64)
    if segment_index >= export_count:
        raise ProcessWorkpackageError("import segment index out of range")
    if not isinstance(segment, bytes) or len(segment) != EC_SEGMENT_SIZE:
        raise ProcessWorkpackageError("invalid import segment size")
    local_index = segment_index % 64
    if leaves[local_index] != blake2b_256_hash(b'leaf' + segment):
        raise ProcessWorkpackageError("import segment does not match its proof page")
    width = min(64, 1 << (export_count - 1).bit_length())
    nodes = list(leaves) + [bytes(32)] * (width - len(leaves))
    tree = BinaryMerkleTree(nodes)
    proof = list(path)
    while len(nodes) > 1:
        split = len(nodes) // 2
        if local_index < split:
            proof.append(tree.node(nodes[split:]))
            nodes = nodes[:split]
        else:
            proof.append(tree.node(nodes[:split]))
            nodes = nodes[split:]
            local_index -= split
    imported = ImportedSegment(segment, tuple(proof))
    verify_import(exports_root, segment_index, imported)
    return imported.justification


def recover_import(spec: WorkPackageSpec, segment_index: int, shards: dict[int, bytes], *,
                  justification: tuple[bytes, ...] | None = None,
                  proof_page_shards: dict[int, bytes] | None = None) -> ImportedSegment:
    """Recover and verify one import using a source report's availability specification.

    This composes H.6 and 14.12 to supply the segment/proof pair required by 14.15;
    it is a local convenience function, not an additional GP-defined function.
    """
    if (isinstance(spec.exports_count, bool) or not isinstance(spec.exports_count, int)
            or not 1 <= spec.exports_count <= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
            or isinstance(segment_index, bool) or not isinstance(segment_index, int)
            or not 0 <= segment_index < spec.exports_count):
        raise ProcessWorkpackageError("import segment index or export count out of range")
    if (justification is None) == (proof_page_shards is None):
        raise ProcessWorkpackageError("supply either an import justification or proof page shards")
    try:
        # GP-0.8.0-eq:H.6: k = WG / (2 D(v)); v is the source report's shard count.
        segment = recover_segment(spec.erasure_shards, shards)
        if proof_page_shards is not None:
            page = recover_segment(spec.erasure_shards, proof_page_shards)
            proof = import_justification(segment, segment_index, page, spec.exports_count, spec.exports_root)
        else:
            proof = tuple(justification)
            if len(proof) != (spec.exports_count - 1).bit_length():
                raise ProcessWorkpackageError("invalid import justification depth")
    except ValueError as exc:
        raise ProcessWorkpackageError(str(exc)) from exc
    # GP-0.8.0-eq:14.15: S_l and J_l may contain only data justified against L_l(r).
    imported = ImportedSegment(segment, proof)
    verify_import(spec.exports_root, segment_index, imported)
    return imported


@dataclass(frozen=True)
class ValidatorShard:
    """One validator row of 14.18 and its E.2 co-path (JAMNP-S CE 137)."""

    shard_index: int
    bundle_shard: bytes
    segment_shards: tuple[bytes, ...]
    justification: tuple[bytes, ...]


@dataclass(frozen=True)
class AvailabilityArtifacts:
    """The retained data behind A(h,b,s,v), rather than a new GP transform."""

    spec: WorkPackageSpec
    shards: tuple[ValidatorShard, ...]


def build_availability_artifacts(package_hash: bytes, bundle: bytes, exports: list[bytes],
                                 validator_count: int) -> AvailabilityArtifacts:
    """Build A(h,b,s,v) and retain its encoded chunks and distribution proofs."""
    # GP-0.8.0-eq:14.18: package_hash=h, bundle=b, exports=s, validator_count=v.
    if not isinstance(package_hash, bytes) or len(package_hash) != 32:
        raise ValueError("work-package hash must be 32 bytes")
    if len(exports) > MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE or any(len(s) != EC_SEGMENT_SIZE for s in exports):
        raise ProcessWorkpackageError("invalid exported segments")
    originals = erasure_data_shards(validator_count)
    alignment = 2 * originals
    # GP-0.8.0-eq:14.18: k = ceil(|b| / z), where z = 2 D(v).
    piece_count = (len(bundle) + alignment - 1) // alignment
    padded_bundle = zero_pad(alignment, bundle)
    bundle_shards = encode_chunks(validator_count, piece_count, padded_bundle)
    segments = exports + paged_proof_segments(exports)
    segment_shard_size = EC_SEGMENT_SIZE // originals
    # H.4-H.5: transpose segments so every validator row contains one shard of each segment.
    transposed = b''.join(
        segment[i * segment_shard_size:(i + 1) * segment_shard_size]
        for i in range(originals) for segment in segments
    )
    rows = encode_chunks(validator_count, len(transposed) // alignment, transposed)
    segment_rows = []
    leaves = []
    for bundle_shard, row in zip(bundle_shards, rows):
        chunks = tuple(row[i:i + segment_shard_size] for i in range(0, len(row), segment_shard_size))
        segment_rows.append(chunks)
        leaves.append(blake2b_256_hash(bundle_shard) + WellBalancedMerkleTree(list(chunks)).root())
    tree = WellBalancedMerkleTree(leaves)
    spec = WorkPackageSpec(
        hash=package_hash, length=len(bundle), erasure_root=tree.root(),
        erasure_shards=validator_count, exports_root=ConstantDepthMerkleTree(exports).root(),
        exports_count=len(exports),
    )
    shards = tuple(ValidatorShard(index, bundle_shards[index], segment_rows[index], tuple(tree.trace(index)))
                   for index in range(validator_count))
    return AvailabilityArtifacts(spec, shards)


def availability_spec(package_hash: bytes, bundle: bytes, exports: list[bytes],
                      validator_count: int) -> WorkPackageSpec:
    # GP-0.8.0-eq:14.18: A(h,b,s,v) -> (h, |b|, u, v, M(s), |s|).
    # package_hash=h, bundle=b, exports=s, validator_count=v.
    return build_availability_artifacts(package_hash, bundle, exports, validator_count).spec


def _shard_dimensions(spec: WorkPackageSpec) -> tuple[int, int, int]:
    """Return the bundle chunk size, segment chunk size and combined segment count."""
    from pyjamaz.graypaper_constants import MAXIMUM_SIZE_AUDITABLE_BUNDLE

    try:
        originals = erasure_data_shards(spec.erasure_shards)
    except ValueError as exc:
        raise ProcessWorkpackageError(str(exc)) from exc
    if (isinstance(spec.length, bool) or not isinstance(spec.length, int)
            or not 0 <= spec.length <= MAXIMUM_SIZE_AUDITABLE_BUNDLE
            or isinstance(spec.exports_count, bool) or not isinstance(spec.exports_count, int)
            or not 0 <= spec.exports_count <= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
            or not isinstance(spec.erasure_root, bytes) or len(spec.erasure_root) != 32):
        raise ProcessWorkpackageError("invalid availability specification")
    # GP-0.8.0-eq:14.18: z=2D(v), bundle chunks have 2 ceil(|b|/z) bytes.
    bundle_size = 2 * ((spec.length + 2 * originals - 1) // (2 * originals))
    segment_count = spec.exports_count + (spec.exports_count + 63) // 64
    return bundle_size, EC_SEGMENT_SIZE // originals, segment_count


def _trace_sizes(index: int, count: int, leaf_size: int) -> tuple[int, ...]:
    """E.2 siblings are raw leaves for singleton subtrees, otherwise hashes."""
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < count:
        raise ProcessWorkpackageError("shard index out of range")
    sizes = []
    while count > 1:
        split = (count + 1) // 2
        if index < split:
            other_count = count - split
            count = split
        else:
            other_count = split
            count -= split
            index -= split
        sizes.append(leaf_size if other_count == 1 else 32)
    return tuple(sizes)


def _check_proof_sizes(proof, sizes: tuple[int, ...]) -> None:
    if (not isinstance(proof, (list, tuple)) or len(proof) != len(sizes)
            or any(not isinstance(value, bytes) or len(value) != size
                   for value, size in zip(proof, sizes))):
        raise ProcessWorkpackageError("invalid shard justification dimensions")


def verify_validator_shard(shard: ValidatorShard, spec: WorkPackageSpec) -> None:
    """Verify one full validator row against A(h,b,s,v)'s erasure root."""
    # GP-0.8.0-eq:14.18, E.2-E.3; JAMNP-S e0b7d291 CE 137.
    bundle_size, segment_size, segment_count = _shard_dimensions(spec)
    sizes = _trace_sizes(shard.shard_index, spec.erasure_shards, 64)
    if (not isinstance(shard.bundle_shard, bytes) or len(shard.bundle_shard) != bundle_size
            or len(shard.segment_shards) != segment_count
            or any(not isinstance(value, bytes) or len(value) != segment_size for value in shard.segment_shards)):
        raise ProcessWorkpackageError("invalid validator shard dimensions")
    _check_proof_sizes(shard.justification, sizes)
    leaf = blake2b_256_hash(shard.bundle_shard) + WellBalancedMerkleTree(list(shard.segment_shards)).root()
    if not WellBalancedMerkleTree.verify(leaf, shard.shard_index, spec.erasure_shards,
                                        shard.justification, spec.erasure_root):
        raise ProcessWorkpackageError("validator shard does not match the erasure root")


def audit_shard_justification(shard: ValidatorShard) -> tuple[bytes, ...]:
    """JAMNP-S e0b7d291 CE 138: append the segment-row root to CE 137's co-path."""
    return shard.justification + (WellBalancedMerkleTree(list(shard.segment_shards)).root(),)


def verify_audit_shard(bundle_shard: bytes, shard_index: int, proof: tuple[bytes, ...],
                       spec: WorkPackageSpec) -> None:
    """Verify a bundle chunk using the CE 138 co-path to the 14.18 erasure root."""
    bundle_size, _, _ = _shard_dimensions(spec)
    sizes = _trace_sizes(shard_index, spec.erasure_shards, 64) + (32,)
    _check_proof_sizes(proof, sizes)
    if not isinstance(bundle_shard, bytes) or len(bundle_shard) != bundle_size:
        raise ProcessWorkpackageError("invalid audit shard size")
    leaf = blake2b_256_hash(bundle_shard) + proof[-1]
    if not WellBalancedMerkleTree.verify(leaf, shard_index, spec.erasure_shards,
                                        proof[:-1], spec.erasure_root):
        raise ProcessWorkpackageError("audit shard does not match the erasure root")


def segment_shard_justification(shard: ValidatorShard, segment_index: int) -> tuple[bytes, ...]:
    """JAMNP-S e0b7d291 CE 140: outer co-path, bundle hash, then segment co-path."""
    path = WellBalancedMerkleTree(list(shard.segment_shards)).trace(segment_index)
    return shard.justification + (blake2b_256_hash(shard.bundle_shard),) + tuple(path)


def verify_segment_shard(segment_shard: bytes, segment_index: int, shard_index: int,
                         proof: tuple[bytes, ...], spec: WorkPackageSpec) -> None:
    """Verify an export/proof-page chunk against the GP-0.8.0-eq:14.18 erasure root."""
    # JAMNP-S e0b7d291 CE 140: j ++ [H(bundle shard)] ++ T(segment row, segment_index).
    _, segment_size, segment_count = _shard_dimensions(spec)
    outer_sizes = _trace_sizes(shard_index, spec.erasure_shards, 64)
    inner_sizes = _trace_sizes(segment_index, segment_count, segment_size)
    _check_proof_sizes(proof, outer_sizes + (32,) + inner_sizes)
    if not isinstance(segment_shard, bytes) or len(segment_shard) != segment_size:
        raise ProcessWorkpackageError("invalid segment shard size")
    outer_depth = len(outer_sizes)
    segment_root = WellBalancedMerkleTree([]).root_from_trace(
        segment_shard, segment_index, segment_count, proof[outer_depth + 1:], single_item_hashed=True,
    )
    leaf = proof[outer_depth] + segment_root
    if not WellBalancedMerkleTree.verify(leaf, shard_index, spec.erasure_shards,
                                        proof[:outer_depth], spec.erasure_root):
        raise ProcessWorkpackageError("segment shard does not match the erasure root")
