"""Small codecs for JAMNP-S v1, pinned to simple.md at e0b7d291.

Stream framing uses fixed little-endian u32 lengths. Protocol len++ fields use
canonical JAM natural numbers. Proof items retain their wire tags.
"""

from jamcodec.base import JamBytes
from jamcodec.types import VarInt64


class InvalidJAMNPSMessage(ValueError):
    pass


def frame(message: bytes) -> bytes:
    return len(message).to_bytes(4, "little") + message


def read_count(stream: JamBytes, maximum: int) -> int:
    start = stream.offset
    count = VarInt64.decode(stream)
    if count > maximum or bytes(stream.data[start:stream.offset]) != VarInt64.encode(count).to_bytes():
        raise InvalidJAMNPSMessage("invalid or noncanonical count")
    return count


def encode_justification(proof, segment_shard_size: int | None = None) -> bytes:
    if len(proof) > 32:
        raise InvalidJAMNPSMessage("too many proof items")
    encoded = []
    for item in proof:
        if len(item) == 32:
            tag = 0
        elif len(item) == 64:
            tag = 1
        elif segment_shard_size is not None and len(item) == segment_shard_size:
            tag = 2
        else:
            raise InvalidJAMNPSMessage("invalid proof item size")
        encoded.append(bytes([tag]) + item)
    return b"".join(encoded)


def decode_justification(data: bytes, segment_shard_size: int | None = None) -> tuple[bytes, ...]:
    stream = JamBytes(data)
    proof = []
    try:
        while stream.get_remaining_length():
            tag = stream.get_next_bytes(1)[0]
            size = {0: 32, 1: 64, 2: segment_shard_size}.get(tag)
            if size is None or len(proof) == 32:
                raise InvalidJAMNPSMessage("invalid proof tag or item count")
            proof.append(bytes(stream.get_next_bytes(size)))
    except Exception as exc:
        raise InvalidJAMNPSMessage("malformed justification") from exc
    return tuple(proof)


def _encode_indices(indices) -> bytes:
    if not indices or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i <= 65535 for i in indices):
        raise InvalidJAMNPSMessage("invalid segment indices")
    return VarInt64.encode(len(indices)).to_bytes() + b"".join(i.to_bytes(2, "little") for i in indices)


def encode_segment_request(root: bytes, shard_index: int, indices) -> bytes:
    if len(root) != 32 or not 0 <= shard_index <= 65535 or len(indices) > 6144:
        raise InvalidJAMNPSMessage("invalid coded segment request")
    return root + shard_index.to_bytes(2, "little") + _encode_indices(indices)


def encode_segment_indices(root: bytes, indices) -> bytes:
    if len(root) != 32 or len(indices) > 3072:
        raise InvalidJAMNPSMessage("invalid complete segment request")
    return root + _encode_indices(indices)


def _decode_requests(data: bytes, with_shard: bool):
    stream, result, total = JamBytes(data), [], 0
    maximum = 6144 if with_shard else 3072
    try:
        while stream.get_remaining_length():
            root = bytes(stream.get_next_bytes(32))
            shard = int.from_bytes(stream.get_next_bytes(2), "little") if with_shard else None
            count = read_count(stream, maximum - total)
            if not count:
                raise InvalidJAMNPSMessage("empty segment request")
            indices = tuple(int.from_bytes(stream.get_next_bytes(2), "little") for _ in range(count))
            result.append((root, shard, indices) if with_shard else (root, indices))
            total += count
        if not result:
            raise InvalidJAMNPSMessage("empty segment request")
    except Exception as exc:
        raise InvalidJAMNPSMessage("malformed segment request") from exc
    return result


def decode_segment_requests(data: bytes):
    return _decode_requests(data, True)


def decode_segment_indices(data: bytes):
    return _decode_requests(data, False)


def encode_import_proofs(proofs) -> bytes:
    if any(len(proof) > 12 or any(len(value) != 32 for value in proof) for proof in proofs):
        raise InvalidJAMNPSMessage("invalid import proofs")
    return b"".join(VarInt64.encode(len(proof)).to_bytes() + b"".join(proof) for proof in proofs)


def decode_import_proofs(data: bytes, count: int) -> tuple[tuple[bytes, ...], ...]:
    stream = JamBytes(data)
    try:
        proofs = tuple(tuple(bytes(stream.get_next_bytes(32)) for _ in range(read_count(stream, 12)))
                       for _ in range(count))
        if stream.get_remaining_length():
            raise InvalidJAMNPSMessage("trailing import proof data")
    except Exception as exc:
        raise InvalidJAMNPSMessage("malformed import proofs") from exc
    return proofs


def split_segments(data: bytes, count: int, size: int = 4104) -> tuple[bytes, ...]:
    if len(data) != count * size:
        raise InvalidJAMNPSMessage("incorrect segment payload length")
    return tuple(data[i * size:(i + 1) * size] for i in range(count))


def decode_mappings(data: bytes) -> dict[bytes, bytes]:
    stream = JamBytes(data)
    mappings = {}
    try:
        for _ in range(read_count(stream, 8)):
            package, root = bytes(stream.get_next_bytes(32)), bytes(stream.get_next_bytes(32))
            if package in mappings:
                raise InvalidJAMNPSMessage("duplicate package mapping")
            mappings[package] = root
        if stream.get_remaining_length():
            raise InvalidJAMNPSMessage("trailing package mappings")
    except Exception as exc:
        raise InvalidJAMNPSMessage("malformed package mappings") from exc
    return mappings
