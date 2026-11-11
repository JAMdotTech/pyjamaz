"""The JAM adapter supplies membership; the native library supplies padding."""

from pathlib import Path

import bandersnatch_vrfs
import pytest

from pyjamaz import signing


MEMBER_COUNTS = sorted(
    {count for count in (6, 9, 300, signing.VALIDATOR_COUNT)
     if count <= signing.VALIDATOR_COUNT}
)


@pytest.mark.parametrize("count", MEMBER_COUNTS)
def test_jam_ring_context_forwards_members_and_profile_capacity(monkeypatch, count):
    keys = [index.to_bytes(32, "little") for index in range(count)]
    expected_context = object()

    def construct(ring_data, public_keys, *, ring_capacity):
        assert ring_data == b"ring parameters"
        assert public_keys == keys
        assert all(type(key) is bytes for key in public_keys)
        assert ring_capacity == signing.VALIDATOR_COUNT
        return expected_context

    monkeypatch.setattr(signing.bandersnatch_vrfs, "RingContext", construct)

    assert signing.jam_ring_context(
        b"ring parameters", (memoryview(key) for key in keys)
    ) is expected_context


@pytest.mark.parametrize("count", [0, 3, 7, signing.VALIDATOR_COUNT + 3])
def test_jam_ring_context_rejects_invalid_member_count(monkeypatch, count):
    def construct(*_args, **_kwargs):
        pytest.fail("invalid validator membership reached the native backend")

    monkeypatch.setattr(signing.bandersnatch_vrfs, "RingContext", construct)

    with pytest.raises(ValueError, match="invalid JAM validator ring"):
        signing.jam_ring_context(b"", [bytes(32)] * count)


@pytest.mark.parametrize("key_length", [0, 31, 33])
def test_jam_ring_context_rejects_invalid_key_length(monkeypatch, key_length):
    def construct(*_args, **_kwargs):
        pytest.fail("malformed public key reached the native backend")

    monkeypatch.setattr(signing.bandersnatch_vrfs, "RingContext", construct)

    with pytest.raises(ValueError, match="invalid JAM validator ring"):
        signing.jam_ring_context(b"", [bytes(32)] * 5 + [bytes(key_length)])


@pytest.fixture(scope="module")
def native_ring_material():
    ring_data = (
        Path(__file__).resolve().parents[1]
        / "pyjamaz/data/zcash-srs-2-11-uncompressed.bin"
    ).read_bytes()
    secrets = [
        bandersnatch_vrfs.secret_from_seed(index.to_bytes(8, "little"))
        for index in range(signing.VALIDATOR_COUNT)
    ]
    public_keys = [bandersnatch_vrfs.public_from_secret(key) for key in secrets]
    return ring_data, secrets, public_keys


@pytest.mark.parametrize("count", MEMBER_COUNTS)
def test_native_padding_preserves_commitments_and_proofs(native_ring_material, count):
    ring_data, secrets, public_keys = native_ring_material
    keys = public_keys[:count]
    context = signing.jam_ring_context(ring_data, keys)
    # Previous caller-side padding is an interoperability oracle, never members
    # supplied by the production JAM adapter after the native API migration.
    padding_point = bytes.fromhex(
        "92ca79e61dd90c1573a8693f199bf6e1e86835cc715cdcf93f5ef222560023aa"
    )
    legacy = bandersnatch_vrfs.RingContext(
        ring_data, keys + [padding_point] * (signing.VALIDATOR_COUNT - count)
    )
    assert context.commitment == legacy.commitment

    index = count - 1
    vrf_input, aux_data = b"jam_ticket_seal" + bytes(33), b""
    expected_output = bandersnatch_vrfs.vrf_output(secrets[index], vrf_input)
    for prover, verifier in ((context, legacy), (legacy, context)):
        proof = prover.ring_vrf_sign(index, secrets[index], vrf_input, aux_data)
        assert len(proof) == 784
        assert verifier.ring_vrf_verify(vrf_input, aux_data, proof) == expected_output

    # Reserved capacity must not enlarge the set of usable member indices.
    for invalid_index in {count, signing.VALIDATOR_COUNT}:
        with pytest.raises(ValueError, match="supplied public key"):
            context.ring_vrf_sign(invalid_index, secrets[0], vrf_input, aux_data)
