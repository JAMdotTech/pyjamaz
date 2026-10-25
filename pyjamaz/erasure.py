"""GP 0.8.0 Appendix H, backed by the JAM GF(2^16) implementation."""

from jam_erasure import encode_shards

from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, valid_validator_count


def erasure_data_shards(validator_count: int) -> int:
    # GP-0.8.0-eq:H.1: D(v) = max { d < v/3 + 2 | WG mod 2d = 0 }.
    if not valid_validator_count(validator_count):
        raise ValueError("invalid assurer count")
    return max(d for d in range(1, validator_count // 3 + 2) if EC_SEGMENT_SIZE % (2 * d) == 0)


def encode_chunks(validator_count: int, piece_count: int, data: bytes) -> list[bytes]:
    # GP-0.8.0-eq:H.5: C^v_k(d): B_(2k D(v)) -> [B_(2k)]_v.
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
