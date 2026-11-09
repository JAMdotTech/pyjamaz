"""Recover imports using H.6 and verify the 14.12/14.15 proof construction."""

from dataclasses import replace

import pytest
from jamcodec.types import H256, Vec

from pyjamaz import erasure
from pyjamaz.availability import (
    ImportedSegment, decode_paged_proof, import_justification, paged_proof_segments,
    recover_import, verify_import,
)
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, valid_validator_count
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import WorkPackageSpec


def source(count, validators=6):
    segments = [index.to_bytes(4, 'little') * (EC_SEGMENT_SIZE // 4) for index in range(count)]
    tree = ConstantDepthMerkleTree(segments)
    spec = WorkPackageSpec(b'p' * 32, 0, b'e' * 32, tree.root(), count, erasure_shards=validators)
    return segments, tree, spec


def parity_shards(validators, data):
    encoded = erasure.encode_blob(validators, data)
    originals = erasure.erasure_data_shards(validators)
    return {index: encoded[index] for index in reversed(range(validators - originals, validators))}


@pytest.mark.parametrize('count', [1, 2, 63, 64, 65, 127, 128, 129, 3072])
def test_recovered_pages_produce_the_original_direct_proof(count):
    segments, tree, spec = source(count)
    pages = paged_proof_segments(segments)
    # Check both sides of a page boundary as well as the final partial page.
    for index in sorted({0, min(63, count - 1), min(64, count - 1), count - 1}):
        shards = parity_shards(6, segments[index])
        page_index = index // 64
        path, leaves = decode_paged_proof(pages[page_index], count, page_index)
        assert len(leaves) == min(64, count - 64 * page_index)
        assert path == tuple(tree.trace(index)[:max(0, (count - 1).bit_length() - 6)])
        expected = ImportedSegment(segments[index], tuple(tree.trace(index)))
        assert recover_import(spec, index, shards, justification=expected.justification) == expected
        assert recover_import(spec, index, shards,
                              proof_page_shards=parity_shards(6, pages[page_index])) == expected


@pytest.mark.parametrize('validators', [6, 9, 15, 1020, 1023])
def test_recovery_uses_the_source_reports_validator_count(monkeypatch, validators):
    monkeypatch.setattr(erasure, 'valid_validator_count',
                        lambda value: valid_validator_count(value, core_count=341))
    segments, tree, spec = source(65, validators)
    page = paged_proof_segments(segments)[1]
    # The segment and proof page can be reconstructed from different index sets.
    page_shards = dict(enumerate(erasure.encode_blob(validators, page)))
    originals = erasure.erasure_data_shards(validators)
    page_shards = {index: page_shards[index] for index in range(originals)}
    imported = recover_import(spec, 64, parity_shards(validators, segments[64]),
                              proof_page_shards=page_shards)
    assert imported == ImportedSegment(segments[64], tuple(tree.trace(64)))


@pytest.mark.parametrize('fault', ['missing', 'both', 'bad_root', 'bad_depth', 'bad_hash',
                                  'bad_segment', 'insufficient_segment', 'insufficient_page'])
def test_invalid_recovery_inputs_are_rejected(fault):
    segments, tree, spec = source(65)
    index = 64
    shards = parity_shards(6, segments[index])
    kwargs = {'justification': tuple(tree.trace(index))}
    if fault == 'missing':
        kwargs = {}
    elif fault == 'both':
        kwargs['proof_page_shards'] = parity_shards(6, paged_proof_segments(segments)[1])
    elif fault == 'bad_root':
        spec = replace(spec, exports_root=b'!' * 32)
    elif fault == 'bad_depth':
        kwargs['justification'] = kwargs['justification'][:-1]
    elif fault == 'bad_hash':
        kwargs['justification'] = (b'!' * 32,) + kwargs['justification'][1:]
    elif fault == 'bad_segment':
        shards = parity_shards(6, b'!' * EC_SEGMENT_SIZE)
    elif fault == 'insufficient_segment':
        shards.pop(3)
    elif fault == 'insufficient_page':
        kwargs = {'proof_page_shards': {}}
    with pytest.raises(ProcessWorkpackageError):
        recover_import(spec, index, shards, **kwargs)


@pytest.mark.parametrize('field,value', [('exports_count', 0), ('exports_count', 3073),
                                       ('exports_count', True), ('erasure_shards', 7)])
def test_invalid_source_spec(field, value):
    segments, _, spec = source(1)
    with pytest.raises(ProcessWorkpackageError):
        recover_import(replace(spec, **{field: value}), 0, parity_shards(6, segments[0]), justification=())


@pytest.mark.parametrize('index', [-1, 1, 3072, True, 0.5])
def test_invalid_segment_index(index):
    segments, _, spec = source(1)
    with pytest.raises(ProcessWorkpackageError):
        recover_import(spec, index, parity_shards(6, segments[0]), justification=())


@pytest.mark.parametrize('fault', ['path_count', 'leaf_count', 'noncanonical_path',
                                  'noncanonical_leaves', 'padding', 'short', 'long'])
def test_malformed_proof_pages_are_rejected(fault):
    segments, _, _ = source(1)
    original = paged_proof_segments(segments)[0]
    page = bytearray(original)
    if fault == 'path_count':
        page[0] = 1
    elif fault == 'leaf_count':
        page[1] = 0
    elif fault == 'noncanonical_path':
        page = b'\x80\x00' + original[:-1]
    elif fault == 'noncanonical_leaves':
        page = original[:1] + b'\x80\x01' + original[2:-1]
    elif fault == 'padding':
        page[-1] = 1
    elif fault == 'short':
        page = page[:-1]
    elif fault == 'long':
        page.append(0)
    with pytest.raises(ProcessWorkpackageError):
        decode_paged_proof(bytes(page), 1, 0)


@pytest.mark.parametrize('count,index', [(0, 0), (3073, 0), (True, 0), (1, -1),
                                        (1, 1), (65, 2), (65, True)])
def test_invalid_page_context(count, index):
    with pytest.raises(ProcessWorkpackageError):
        decode_paged_proof(bytes(EC_SEGMENT_SIZE), count, index)


@pytest.mark.parametrize('count,index,segment', [(None, 0, bytes(4104)),
                                               (65, 65, bytes(4104)),
                                               (1, 0, bytes(4103)), (1, 0, None)])
def test_justification_rejects_invalid_context_or_segment(count, index, segment):
    segments, _, spec = source(65 if count == 65 else 1)
    page = paged_proof_segments(segments)[-1]
    with pytest.raises(ProcessWorkpackageError):
        import_justification(segment, index, page, count, spec.exports_root)


@pytest.mark.parametrize('hash_index', [0, 1, 64])
def test_altered_page_path_or_leaves_cannot_justify_an_import(hash_index):
    segments, _, spec = source(65)
    page = paged_proof_segments(segments)[0]
    path, leaves = decode_paged_proof(page, 65, 0)
    hashes = list(path + leaves)
    hashes[hash_index] = b'!' * 32
    encoded = Vec(H256).encode(hashes[:1]).to_bytes() + Vec(H256).encode(hashes[1:]).to_bytes()
    altered = encoded + bytes(EC_SEGMENT_SIZE - len(encoded))
    with pytest.raises(ProcessWorkpackageError):
        import_justification(segments[0], 0, altered, 65, spec.exports_root)
    with pytest.raises(ProcessWorkpackageError):
        recover_import(spec, 0, parity_shards(6, segments[0]), proof_page_shards=parity_shards(6, altered))


@pytest.mark.parametrize('root,index,imported', [
    (b'x', 0, ImportedSegment(bytes(4104), ())),
    (b'x' * 32, True, ImportedSegment(bytes(4104), ())),
    (b'x' * 32, 3072, ImportedSegment(bytes(4104), ())),
    (b'x' * 32, 0, ImportedSegment(bytes(4103), ())),
    (b'x' * 32, 0, ImportedSegment(bytes(4104), (b'x',))),
    (b'x' * 32, 0, ImportedSegment(bytes(4104), (b'x' * 32,) * 13)),
])
def test_import_verification_rejects_invalid_dimensions(root, index, imported):
    with pytest.raises(ProcessWorkpackageError):
        verify_import(root, index, imported)
