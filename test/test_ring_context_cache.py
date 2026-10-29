from pathlib import Path
from unittest.mock import Mock

import bandersnatch_vrfs
import pytest

from pyjamaz import signing


KEYS = [index.to_bytes(32, "little") for index in range(6)]


@pytest.fixture(autouse=True)
def clear_ring_cache():
    signing._cached_ring_context.cache_clear()
    yield
    signing._cached_ring_context.cache_clear()


@pytest.fixture
def constructor(monkeypatch):
    constructor = Mock(side_effect=lambda *_args, **_kwargs: object())
    monkeypatch.setattr(signing.bandersnatch_vrfs, "RingContext", constructor)
    return constructor


def test_equivalent_ring_inputs_reuse_context(constructor):
    context = signing.jam_ring_context(b"srs", KEYS)

    assert signing.jam_ring_context(
        memoryview(b"srs"), (memoryview(key) for key in KEYS)
    ) is context
    constructor.assert_called_once_with(
        b"srs", KEYS, ring_capacity=signing.VALIDATOR_COUNT,
    )


@pytest.mark.parametrize("change", ["srs", "key", "order", "capacity"])
def test_different_ring_inputs_create_contexts(constructor, monkeypatch, change):
    context = signing.jam_ring_context(b"srs", KEYS)
    ring_data, keys = b"srs", KEYS.copy()
    if change == "srs":
        ring_data = b"other srs"
    elif change == "key":
        keys[0] = bytes([255]) * 32
    elif change == "order":
        keys.reverse()
    else:
        monkeypatch.setattr(signing, "VALIDATOR_COUNT", signing.VALIDATOR_COUNT + 3)

    changed_context = signing.jam_ring_context(ring_data, keys)

    assert changed_context is not context
    assert signing.jam_ring_context(ring_data, keys) is changed_context
    assert constructor.call_count == 2


@pytest.mark.skipif(signing.VALIDATOR_COUNT < 9, reason="requires a larger profile")
def test_different_membership_count_creates_context(constructor):
    keys = [index.to_bytes(32, "little") for index in range(9)]

    assert signing.jam_ring_context(b"srs", keys) is not signing.jam_ring_context(
        b"srs", keys[:6],
    )
    assert constructor.call_count == 2


@pytest.mark.parametrize("change", ["srs", "key"])
def test_mutable_inputs_are_snapshotted(constructor, change):
    ring_data = bytearray(b"srs")
    keys = [bytearray(key) for key in KEYS]
    context = signing.jam_ring_context(ring_data, keys)
    changed_input = ring_data if change == "srs" else keys[0]

    changed_input[0] ^= 1
    assert signing.jam_ring_context(ring_data, keys) is not context
    changed_input[0] ^= 1
    assert signing.jam_ring_context(ring_data, keys) is context
    assert constructor.call_count == 2


def test_old_ring_contexts_are_evicted(constructor):
    context = signing.jam_ring_context(b"old srs", KEYS)
    cache_size = signing._cached_ring_context.cache_parameters()["maxsize"]
    for index in range(cache_size):
        signing.jam_ring_context(index.to_bytes(4, "little"), KEYS)

    assert signing.jam_ring_context(b"old srs", KEYS) is not context
    assert constructor.call_count == cache_size + 2


def test_failed_construction_can_be_retried(constructor):
    context = object()
    constructor.side_effect = [ValueError("invalid srs"), context]

    with pytest.raises(ValueError, match="invalid srs"):
        signing.jam_ring_context(b"srs", KEYS)
    assert signing.jam_ring_context(b"srs", KEYS) is context
    assert constructor.call_count == 2


def test_cached_native_context_still_verifies_each_proof():
    ring_data = (
        Path(__file__).resolve().parents[1]
        / "pyjamaz/data/zcash-srs-2-11-uncompressed.bin"
    ).read_bytes()
    secrets = [bandersnatch_vrfs.secret_from_seed(key) for key in KEYS]
    keys = [bandersnatch_vrfs.public_from_secret(secret) for secret in secrets]
    context = signing.jam_ring_context(ring_data, keys)
    vrf_input = b"jam_ticket_seal" + bytes(33)
    proof = context.ring_vrf_sign(0, secrets[0], vrf_input, b"")
    expected_output = bandersnatch_vrfs.vrf_output(secrets[0], vrf_input)

    cached_context = signing.jam_ring_context(ring_data, keys.copy())
    assert cached_context is context
    assert cached_context.ring_vrf_verify(vrf_input, b"", proof) == expected_output
    with pytest.raises(ValueError):
        cached_context.ring_vrf_verify(vrf_input + b"changed", b"", proof)
    with pytest.raises(ValueError):
        cached_context.ring_vrf_verify(vrf_input, b"", proof[:-1])

    rotated_context = signing.jam_ring_context(ring_data, keys[::-1])
    assert rotated_context.commitment != context.commitment
    with pytest.raises(ValueError):
        rotated_context.ring_vrf_verify(vrf_input, b"", proof)
    assert context.ring_vrf_verify(vrf_input, b"", proof) == expected_output
