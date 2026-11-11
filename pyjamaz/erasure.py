"""GP 0.8.0 Appendix H, backed by the JAM GF(2^16) implementation."""

from jam_erasure import encode_shards, recover_shards

from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, valid_validator_count


def erasure_data_shards(validator_count: int) -> int:
    # GP-0.8.0-eq:H.1: D(v) = max { d < v/3 + 2 | WG mod 2d = 0 }.
    if not valid_validator_count(validator_count):
        raise ValueError("invalid assurer count")
    return max(d for d in range(1, validator_count // 3 + 2) if EC_SEGMENT_SIZE % (2 * d) == 0)


def encode_chunks(validator_count: int, piece_count: int, data: bytes) -> list[bytes]:
    # GP-0.8.0-eq:H.5: C^v_k(d): B_(2k D(v)) -> [B_(2k)]_v.
    # validator_count=v, piece_count=k, data=d.
    originals = erasure_data_shards(validator_count)
    if isinstance(piece_count, bool) or not isinstance(piece_count, int) or piece_count < 0:
        raise ValueError("invalid erasure piece count")
    if len(data) != 2 * piece_count * originals:
        raise ValueError("data length does not match erasure dimensions")
    if piece_count == 0:
        return [b''] * validator_count
    shards = encode_shards(data, originals, validator_count - originals)
    if len(shards) != validator_count or any(len(shard) != 2 * piece_count for shard in shards):
        raise RuntimeError("erasure backend returned invalid shard dimensions")
    return shards


def _validate_chunks(validator_count: int, chunk_size: int, chunks: dict[int, bytes]) -> None:
    if not isinstance(chunks, dict):
        raise ValueError("erasure chunks must map validator indexes to bytes")
    for index, chunk in chunks.items():
        if (isinstance(index, bool) or not isinstance(index, int)
                or not 0 <= index < validator_count):
            raise ValueError("invalid erasure chunk index")
        if not isinstance(chunk, bytes) or len(chunk) != chunk_size:
            raise ValueError("chunk length does not match erasure dimensions")


def recover_chunks(validator_count: int, piece_count: int, chunks: dict[int, bytes]) -> bytes:
    # GP-0.8.0-eq:H.6: R^v_k(c): {(B_(2k), N_v)}_(D(v)) -> B_(2k D(v)).
    # validator_count=v, piece_count=k, chunks=c (validator index -> chunk).
    originals = erasure_data_shards(validator_count)
    if isinstance(piece_count, bool) or not isinstance(piece_count, int) or piece_count < 0:
        raise ValueError("invalid erasure piece count")
    _validate_chunks(validator_count, 2 * piece_count, chunks)
    if len(chunks) != originals:
        raise ValueError("recovery requires exactly D(v) chunks")
    if piece_count == 0:
        return b''
    # H.6's first case: sort the original chunks by their validator index and join.
    if all(index in chunks for index in range(originals)):
        return b''.join(chunks[index] for index in range(originals))
    recovered = recover_shards(originals, validator_count - originals, sorted(chunks.items()))
    if not isinstance(recovered, bytes) or len(recovered) != 2 * piece_count * originals:
        raise RuntimeError("erasure backend returned invalid recovered dimensions")
    return recovered


def encode_blob(validator_count: int, data: bytes) -> list[bytes]:
    """Pad a blob and apply H.5; this convenience function is not a separate GP transform."""
    originals = erasure_data_shards(validator_count)
    if not isinstance(data, bytes):
        raise ValueError("erasure data must be bytes")
    # GP-0.8.0-eq:14.19: P_(2 D(v))(data), followed by H.5.
    alignment = 2 * originals
    padded = data + bytes(-len(data) % alignment)
    return encode_chunks(validator_count, len(padded) // alignment, padded)


def recover_blob(validator_count: int, original_length: int, shards: dict[int, bytes]) -> bytes:
    """Select a threshold for H.6, check zero padding, then return the original blob.

    This convenience function requires the known unpadded length. Authentication
    of the recovered bytes belongs to the availability layer.
    """
    originals = erasure_data_shards(validator_count)
    if isinstance(original_length, bool) or not isinstance(original_length, int) or original_length < 0:
        raise ValueError("invalid original blob length")
    piece_count = (original_length + 2 * originals - 1) // (2 * originals)
    _validate_chunks(validator_count, 2 * piece_count, shards)
    if original_length == 0:
        return b''
    if len(shards) < originals:
        raise ValueError("insufficient erasure shards")
    # Prefer H.6's systematic case; otherwise use the lowest distinct indexes.
    indexes = (range(originals) if all(index in shards for index in range(originals))
               else sorted(shards)[:originals])
    padded = recover_chunks(validator_count, piece_count, {index: shards[index] for index in indexes})
    # GP-0.8.0-eq:14.19: only the zero extension of P_(2 D(v)) may be discarded.
    if any(padded[original_length:]):
        raise ValueError("recovered blob has nonzero padding")
    return padded[:original_length]


def recover_segment(validator_count: int, shards: dict[int, bytes]) -> bytes:
    """Apply H.6 with k = WG / (2 D(v)); segments need no padding (Appendix H.1)."""
    return recover_blob(validator_count, EC_SEGMENT_SIZE, shards)
