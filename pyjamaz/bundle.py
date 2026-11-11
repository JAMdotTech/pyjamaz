"""Canonical GP-0.8.0-eq:14.16 bundle encoding for transport adapters.

These helpers check the representation. Hashes, authorization and Merkle proofs
are checked by the report computation after authorization, not by this codec.
"""

from dataclasses import dataclass

from jamcodec.base import JamBytes
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.types import H256, VarInt64, Vec

from pyjamaz.graypaper_constants import (
    EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, MAXIMUM_SIZE_AUDITABLE_BUNDLE,
)
from pyjamaz.models.common import WorkPackage


@dataclass
class BundleParts:
    package: WorkPackage
    extrinsics: list[bytes]
    segments: list[bytes]
    justifications: list[list[bytes]]


def decode_package(encoded: bytes) -> tuple[WorkPackage, int]:
    """Read the package prefix so a receiver can authorize before reading payloads."""
    if not isinstance(encoded, bytes) or len(encoded) > MAXIMUM_SIZE_AUDITABLE_BUNDLE:
        raise ValueError("invalid bundle size")
    stream = JamBytes(encoded)
    try:
        package = WorkPackage.from_jam_bytes(stream)
    except (ValueError, RemainingScaleBytesNotEmptyException) as exc:
        raise ValueError("malformed bundle package") from exc
    if package.to_jam_bytes().to_bytes() != encoded[:stream.offset]:
        raise ValueError("noncanonical bundle package")
    return package, stream.offset


def encode_bundle(package: WorkPackage, extrinsics: list[bytes], segments: list[bytes],
                  justifications: list[list[bytes]]) -> bytes:
    # GP-0.8.0-eq:14.16: E(p, X#(p_w), S_l#(p_w), J_l#(p_w)).
    # The manifests imply every length except the individual proof-path lengths.
    manifests = [entry for item in package.items for entry in item.extrinsic]
    import_count = sum(len(item.import_segments) for item in package.items)
    if len(extrinsics) != len(manifests):
        raise ValueError("extrinsic count does not match manifest")
    if len(segments) != import_count or len(justifications) != import_count:
        raise ValueError("import or justification count does not match manifest")
    if any(not isinstance(blob, bytes) or len(blob) != entry.len
           for entry, blob in zip(manifests, extrinsics)):
        raise ValueError("extrinsic length does not match manifest")
    if any(not isinstance(segment, bytes) or len(segment) != EC_SEGMENT_SIZE for segment in segments):
        raise ValueError("invalid imported segment size")
    if any(len(proof) > (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
           or any(not isinstance(h, bytes) or len(h) != 32 for h in proof) for proof in justifications):
        raise ValueError("invalid import proof dimensions")
    return (package.to_jam_bytes().to_bytes() + b''.join(extrinsics) + b''.join(segments)
            + b''.join(Vec(H256).encode(list(proof)).to_bytes() for proof in justifications))


def decode_bundle(encoded: bytes) -> BundleParts:
    """Decode B(p,l), rejecting noncanonical prefixes, truncation and trailing bytes."""
    package, offset = decode_package(encoded)
    stream = JamBytes(encoded)
    stream.offset = offset
    try:
        extrinsics = [bytes(stream.get_next_bytes(entry.len))
                      for item in package.items for entry in item.extrinsic]
        import_count = sum(len(item.import_segments) for item in package.items)
        segments = [bytes(stream.get_next_bytes(EC_SEGMENT_SIZE)) for _ in range(import_count)]
        proofs = []
        for _ in range(import_count):
            start = stream.offset
            count = VarInt64.decode(stream)
            if (count > (MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE - 1).bit_length()
                    or bytes(stream.data[start:stream.offset]) != VarInt64.encode(count).to_bytes()):
                raise ValueError("invalid or noncanonical import proof count")
            proofs.append([bytes(stream.get_next_bytes(32)) for _ in range(count)])
    except RemainingScaleBytesNotEmptyException as exc:
        raise ValueError("truncated bundle data") from exc
    if stream.get_remaining_length():
        raise ValueError("bundle has trailing bytes")
    return BundleParts(package, extrinsics, segments, proofs)
