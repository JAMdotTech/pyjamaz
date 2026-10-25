"""GP 0.8.0 bundle assembly and availability commitments (section 14)."""

from dataclasses import dataclass, field

from jamcodec.types import H256, Vec

from pyjamaz.erasure import encode_chunks, erasure_data_shards
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import (
    EC_SEGMENT_SIZE, GAS_ACCUMULATION, GAS_REFINE, MAXIMUM_DEPENDENCIES_WORK_REPORT,
    MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE,
    MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE, MAXIMUM_SIZE_WORK_PACKAGE, MAXIMUM_WORK_ITEMS,
)
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import ConstantDepthMerkleTree, WellBalancedMerkleTree
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
    if (sum(w.refine_gas_limit for w in package.items) >= GAS_REFINE
            or sum(w.accumulate_gas_limit for w in package.items) >= GAS_ACCUMULATION):
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
            proof = imported.justification
            if (len(imported.segment) != EC_SEGMENT_SIZE
                    or entry.segment_index >= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE
                    or len(proof) > (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
                    or not ConstantDepthMerkleTree.verify(
                        imported.segment, entry.segment_index, proof,
                        resolve_import_root(mappings, import_reference(entry)),
                    )):
                raise ProcessWorkpackageError("invalid import segment justification")
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
        output = bytearray(package.to_jam_bytes().to_bytes())
        for item in package.items:
            for blob in self.extrinsic_data(item):
                output.extend(blob)
        for item in package.items:
            for segment in self.import_segments(mappings, item):
                output.extend(segment)
        for item in package.items:
            for proof in self.import_justifications(mappings, item):
                output.extend(Vec(H256).encode(list(proof)).to_bytes())
        return bytes(output)


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


def availability_spec(package_hash: bytes, bundle: bytes, exports: list[bytes],
                      validator_count: int) -> WorkPackageSpec:
    # GP-0.8.0-eq:14.18: A(h,b,s,v) -> (h, |b|, u, v, M(s), |s|).
    if not isinstance(package_hash, bytes) or len(package_hash) != 32:
        raise ValueError("work-package hash must be 32 bytes")
    if len(exports) > MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE or any(len(s) != EC_SEGMENT_SIZE for s in exports):
        raise ProcessWorkpackageError("invalid exported segments")
    originals = erasure_data_shards(validator_count)
    alignment = 2 * originals
    padded_bundle = zero_pad(alignment, bundle)
    bundle_shards = encode_chunks(validator_count, len(padded_bundle) // alignment, padded_bundle)
    segments = exports + paged_proof_segments(exports)
    segment_shard_size = EC_SEGMENT_SIZE // originals
    # H.4-H.5: transpose segments so every validator row contains one shard of each segment.
    transposed = b''.join(
        segment[i * segment_shard_size:(i + 1) * segment_shard_size]
        for i in range(originals) for segment in segments
    )
    rows = encode_chunks(validator_count, len(transposed) // alignment, transposed)
    leaves = []
    for bundle_shard, row in zip(bundle_shards, rows):
        chunks = [row[i:i + segment_shard_size] for i in range(0, len(row), segment_shard_size)]
        leaves.append(blake2b_256_hash(bundle_shard) + WellBalancedMerkleTree(chunks).root())
    return WorkPackageSpec(
        hash=package_hash, length=len(bundle), erasure_root=WellBalancedMerkleTree(leaves).root(),
        erasure_shards=validator_count, exports_root=ConstantDepthMerkleTree(exports).root(),
        exports_count=len(exports),
    )
