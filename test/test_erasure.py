"""GP 0.8.0 Appendix H, including the pinned upstream byte-level oracles."""

import json
from pathlib import Path

import pytest

from pyjamaz import erasure
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, valid_validator_count


FIXTURES = Path(__file__).parent / 'fixtures' / 'erasure'
VECTORS = [(count, path) for profile, count in [('tiny', 6), ('full', 1023)]
           for path in sorted((FIXTURES / profile).glob('*.json'))]


@pytest.fixture(autouse=True)
def full_validator_domain(monkeypatch):
    # Test Full and Tiny in one process without changing the configured profile.
    monkeypatch.setattr(erasure, 'valid_validator_count',
                        lambda count: valid_validator_count(count, core_count=341))


@pytest.mark.parametrize(('validator_count', 'path'), VECTORS,
                         ids=[f'{path.parent.name}-{path.stem}' for _, path in VECTORS])
@pytest.mark.parametrize('selection', ['systematic', 'parity', 'mixed'])
def test_upstream_erasure_vectors(validator_count, path, selection):
    vector = json.loads(path.read_text())
    data = bytes.fromhex(vector['data'][2:])
    expected = [bytes.fromhex(value[2:]) for value in vector['shards']]
    originals = erasure.erasure_data_shards(validator_count)
    assert erasure.encode_blob(validator_count, data) == expected
    if selection == 'systematic':
        indexes = range(originals)
    elif selection == 'parity':
        indexes = range(validator_count - originals, validator_count)
    else:
        indexes = list(range(0, originals, 2))
        indexes += list(range(originals, originals + originals - len(indexes)))
    # Shuffled input must retain global indexes and recover the original ordering.
    shards = {index: expected[index] for index in reversed(list(indexes))}
    padded = data + bytes(-len(data) % (2 * originals))
    pieces = len(padded) // (2 * originals)
    assert erasure.recover_chunks(validator_count, pieces, shards) == padded
    assert erasure.recover_blob(validator_count, len(data), shards) == data


def test_fixture_inventory():
    assert len(VECTORS) == 12


def test_every_supported_validator_count_recovers_parity():
    for validators in range(6, 1024, 3):
        originals = erasure.erasure_data_shards(validators)
        data = bytes((index * 29 + 7) % 256 for index in range(2 * originals))
        shards = erasure.encode_chunks(validators, 1, data)
        parity = {index: shards[index] for index in range(validators - originals, validators)}
        assert erasure.recover_chunks(validators, 1, parity) == data


@pytest.mark.parametrize('length', [0, 1, 5, 6, 7, 4104, 4105])
def test_blob_boundaries_and_surplus_shards(length):
    data = bytes(index % 251 for index in range(length))
    shards = erasure.encode_blob(6, data)
    assert erasure.recover_blob(6, length, dict(enumerate(shards))) == data
    assert erasure.recover_blob(6, length, {index: shards[index] for index in [5, 3, 4]}) == data


def test_complete_systematic_set_bypasses_native_recovery(monkeypatch):
    def unexpected(*_):
        pytest.fail('systematic reconstruction must not invoke the native decoder')

    monkeypatch.setattr(erasure, 'recover_shards', unexpected)
    assert erasure.recover_chunks(6, 1, {2: b'ef', 0: b'ab', 1: b'cd'}) == b'abcdef'
    # Even with surplus shards, the convenience function prefers the systematic set.
    assert erasure.recover_blob(6, 6, {5: b'zz', 2: b'ef', 1: b'cd', 0: b'ab'}) == b'abcdef'


def test_surplus_selection_is_deterministic(monkeypatch):
    selected = []

    def recover(originals, parity, chunks):
        selected.append(chunks)
        return b'abcdef'

    monkeypatch.setattr(erasure, 'recover_shards', recover)
    shards = {5: b'zz', 4: b'yy', 3: b'xx', 1: b'cd'}
    assert erasure.recover_blob(6, 6, shards) == b'abcdef'
    assert selected == [[(1, b'cd'), (3, b'xx'), (4, b'yy')]]


def test_segment_recovery():
    segment = bytes(index % 251 for index in range(EC_SEGMENT_SIZE))
    shards = erasure.encode_blob(6, segment)
    assert erasure.recover_segment(6, {index: shards[index] for index in [3, 4, 5]}) == segment


@pytest.mark.parametrize('piece_count', [-1, True, 1.5])
def test_invalid_piece_count(piece_count):
    with pytest.raises(ValueError, match='piece count'):
        erasure.recover_chunks(6, piece_count, {})


@pytest.mark.parametrize('validator_count', [-1, 0, 3, 7, True, 6.0, 1026])
def test_invalid_validator_count(validator_count):
    with pytest.raises(ValueError, match='assurer count'):
        erasure.recover_chunks(validator_count, 1, {})


@pytest.mark.parametrize('chunks', [
    {}, {0: b'ab', 1: b'cd'},
    {0: b'ab', 1: b'cd', 2: b'ef', 3: b'gh'},
])
def test_gp_recovery_requires_exact_threshold(chunks):
    with pytest.raises(ValueError, match='exactly D'):
        erasure.recover_chunks(6, 1, chunks)


@pytest.mark.parametrize('index', [-1, 6, True, 1.5, '0'])
def test_invalid_chunk_index(index):
    with pytest.raises(ValueError, match='index'):
        erasure.recover_chunks(6, 1, {index: b'ab', 2: b'cd', 3: b'ef'})


@pytest.mark.parametrize('chunk', [b'', b'a', b'abc', 'ab', bytearray(b'ab')])
def test_invalid_chunk_dimensions(chunk):
    with pytest.raises(ValueError, match='dimensions'):
        erasure.recover_chunks(6, 1, {0: chunk, 1: b'cd', 2: b'ef'})


def test_invalid_surplus_shards_are_checked():
    with pytest.raises(ValueError, match='dimensions'):
        erasure.recover_blob(6, 6, {0: b'ab', 1: b'cd', 2: b'ef', 5: b'odd'})
    with pytest.raises(ValueError, match='index'):
        erasure.recover_blob(6, 6, {0: b'ab', 1: b'cd', 2: b'ef', 6: b'gh'})


@pytest.mark.parametrize('length', [-1, True, 1.5])
def test_invalid_original_length(length):
    with pytest.raises(ValueError, match='blob length'):
        erasure.recover_blob(6, length, {})


def test_insufficient_shards():
    with pytest.raises(ValueError, match='insufficient'):
        erasure.recover_blob(6, 6, {3: b'ab', 4: b'cd'})


def test_nonzero_recovered_padding_is_rejected():
    shards = erasure.encode_blob(6, b'abcdef')
    with pytest.raises(ValueError, match='nonzero padding'):
        erasure.recover_blob(6, 5, {index: shards[index] for index in [3, 4, 5]})


def test_empty_data_needs_no_native_calls(monkeypatch):
    def unexpected(*_):
        pytest.fail('empty data must not invoke the native backend')

    monkeypatch.setattr(erasure, 'encode_shards', unexpected)
    monkeypatch.setattr(erasure, 'recover_shards', unexpected)
    assert erasure.encode_blob(6, b'') == [b''] * 6
    assert erasure.recover_blob(6, 0, {}) == b''
    assert erasure.recover_chunks(6, 0, {3: b'', 4: b'', 5: b''}) == b''
    with pytest.raises(ValueError, match='dimensions'):
        erasure.recover_blob(6, 0, {0: b'x'})


@pytest.mark.parametrize('recovered', [b'', b'abcde', b'abcdefg', 'abcdef'])
def test_malformed_native_recovery_is_rejected(monkeypatch, recovered):
    monkeypatch.setattr(erasure, 'recover_shards', lambda *_: recovered)
    with pytest.raises(RuntimeError, match='recovered dimensions'):
        erasure.recover_chunks(6, 1, {3: b'ab', 4: b'cd', 5: b'ef'})


@pytest.mark.parametrize('encoded', [[], [b'ab'] * 5, [b'a'] * 6])
def test_malformed_native_encoding_is_rejected(monkeypatch, encoded):
    monkeypatch.setattr(erasure, 'encode_shards', lambda *_: encoded)
    with pytest.raises(RuntimeError, match='shard dimensions'):
        erasure.encode_blob(6, b'abcdef')
