"""GP 14.18 artifacts and JAMNP-S e0b7d291 CE 137/138/140 co-paths."""

from dataclasses import replace

import pytest

from pyjamaz import erasure
from pyjamaz.availability import (
    audit_shard_justification, availability_spec, build_availability_artifacts,
    paged_proof_segments, segment_shard_justification, verify_audit_shard,
    verify_segment_shard, verify_validator_shard,
)
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_SIZE_AUDITABLE_BUNDLE, valid_validator_count
from pyjamaz.hashing import blake2b_256_hash as hash_blob
from pyjamaz.merkle import ConstantDepthMerkleTree, WellBalancedMerkleTree


@pytest.fixture(autouse=True)
def full_validator_domain(monkeypatch):
    monkeypatch.setattr(erasure, 'valid_validator_count',
                        lambda count: valid_validator_count(count, core_count=341))


def exports(count):
    return [index.to_bytes(4, 'little') * (EC_SEGMENT_SIZE // 4) for index in range(count)]


def test_well_balanced_trace_matches_three_leaf_definition():
    a, b, c = b'a' * 64, b'b' * 64, b'c' * 64
    ab = hash_blob(b'node' + a + b)
    tree = WellBalancedMerkleTree([a, b, c])
    assert tree.root() == hash_blob(b'node' + ab + c)
    assert tree.trace(0) == [c, b]
    assert tree.trace(1) == [c, a]
    assert tree.trace(2) == [ab]


@pytest.mark.parametrize('count', [1, 2, 3, 5, 6, 9, 17])
@pytest.mark.parametrize('leaf_size', [12, 32, 64, 1368])
def test_well_balanced_proofs_use_exact_index_and_leaf_count(count, leaf_size):
    leaves = [bytes([index]) * leaf_size for index in range(count)]
    tree = WellBalancedMerkleTree(leaves)
    for index, leaf in enumerate(leaves):
        proof = tree.trace(index)
        assert tree.verify(leaf, index, count, proof, tree.root())
        assert not tree.verify(leaf + b'x', index, count, proof, tree.root())
        assert not tree.verify(leaf, index, count, proof + [bytes(32)], tree.root())
        assert not tree.verify(leaf, index, count, proof, bytes(32))
    if count == 1:
        assert tree.root() == hash_blob(leaves[0])
        assert tree.root_from_trace(leaves[0], 0, 1, []) == leaves[0]
        assert not tree.verify(hash_blob(leaves[0]), 0, 1, [], tree.root())


@pytest.mark.parametrize('index,count', [(True, 1), (0, True), (-1, 1), (1, 1), (0, 0)])
def test_invalid_merkle_positions(index, count):
    assert not WellBalancedMerkleTree.verify(b'a', index, count, (), bytes(32))


@pytest.mark.parametrize('validators', [6, 9, 1020, 1023])
@pytest.mark.parametrize('count', [0, 1, 65])
def test_artifacts_match_independent_per_segment_construction(validators, count):
    segments = exports(count)
    bundle = b'canonical bundle contents' * 3
    artifacts = build_availability_artifacts(b'p' * 32, bundle, segments, validators)
    bundle_shards = erasure.encode_blob(validators, bundle)
    segment_columns = [erasure.encode_blob(validators, segment)
                       for segment in segments + paged_proof_segments(segments)]
    rows = list(zip(*segment_columns)) if segment_columns else [()] * validators
    leaves = [hash_blob(bundle_shard) + WellBalancedMerkleTree(list(row)).root()
              for bundle_shard, row in zip(bundle_shards, rows)]
    assert artifacts.spec.hash == b'p' * 32
    assert artifacts.spec.length == len(bundle)
    assert artifacts.spec.erasure_shards == validators
    assert artifacts.spec.exports_count == count
    assert artifacts.spec.exports_root == ConstantDepthMerkleTree(segments).root()
    assert artifacts.spec.erasure_root == WellBalancedMerkleTree(leaves).root()
    assert len(artifacts.shards) == validators
    for index, shard in enumerate(artifacts.shards):
        assert shard.shard_index == index
        assert shard.bundle_shard == bundle_shards[index]
        assert shard.segment_shards == rows[index]
        verify_validator_shard(shard, artifacts.spec)
        verify_audit_shard(shard.bundle_shard, index, audit_shard_justification(shard), artifacts.spec)
    originals = erasure.erasure_data_shards(validators)
    selected = artifacts.shards[validators - originals:]
    assert erasure.recover_blob(validators, len(bundle),
                               {row.shard_index: row.bundle_shard for row in selected}) == bundle
    if count:
        combined = segments + paged_proof_segments(segments)
        for segment_index in {0, count - 1, count, len(combined) - 1}:
            assert erasure.recover_segment(validators, {
                row.shard_index: row.segment_shards[segment_index] for row in selected
            }) == combined[segment_index]


@pytest.mark.parametrize('count', [0, 1, 63, 64, 65, 129, 3072])
def test_distribution_proofs_cover_page_boundaries_and_export_limit(count):
    artifacts = build_availability_artifacts(bytes(32), b'bundle', exports(count), 6)
    for row in artifacts.shards:
        verify_validator_shard(row, artifacts.spec)
        if not row.segment_shards:
            with pytest.raises(ProcessWorkpackageError, match='index'):
                verify_segment_shard(b'', 0, row.shard_index, (), artifacts.spec)
            continue
        positions = {0, count - 1, count, len(row.segment_shards) - 1}
        for index in positions:
            proof = segment_shard_justification(row, index)
            verify_segment_shard(row.segment_shards[index], index, row.shard_index, proof, artifacts.spec)


def test_spec_api_returns_only_the_same_specification():
    args = (b'p' * 32, b'bundle', exports(3), 6)
    assert availability_spec(*args) == build_availability_artifacts(*args).spec


@pytest.fixture
def example():
    artifacts = build_availability_artifacts(b'p' * 32, b'bundle', exports(3), 6)
    return artifacts.spec, artifacts.shards[1]


@pytest.mark.parametrize('fault', ['index', 'bundle', 'row_count', 'chunk_size', 'proof_size', 'proof_hash'])
def test_invalid_validator_rows_are_rejected(example, fault):
    spec, shard = example
    if fault == 'index':
        shard = replace(shard, shard_index=True)
    elif fault == 'bundle':
        shard = replace(shard, bundle_shard=bytes(len(shard.bundle_shard)))
    elif fault == 'row_count':
        shard = replace(shard, segment_shards=shard.segment_shards[:-1])
    elif fault == 'chunk_size':
        shard = replace(shard, segment_shards=(b'x',) + shard.segment_shards[1:])
    elif fault == 'proof_size':
        shard = replace(shard, justification=shard.justification[:-1])
    else:
        shard = replace(shard, justification=(bytes(len(shard.justification[0])),) + shard.justification[1:])
    with pytest.raises(ProcessWorkpackageError):
        verify_validator_shard(shard, spec)


@pytest.mark.parametrize('fault', ['chunk', 'chunk_size', 'proof', 'missing', 'index'])
def test_invalid_audit_proofs_are_rejected(example, fault):
    spec, shard = example
    chunk, index, proof = shard.bundle_shard, shard.shard_index, audit_shard_justification(shard)
    if fault == 'chunk':
        chunk = bytes(len(chunk))
    elif fault == 'chunk_size':
        chunk += b'x'
    elif fault == 'proof':
        proof = proof[:-1] + (bytes(32),)
    elif fault == 'missing':
        proof = ()
    else:
        index = 6
    with pytest.raises(ProcessWorkpackageError):
        verify_audit_shard(chunk, index, proof, spec)


@pytest.mark.parametrize('fault', ['chunk', 'chunk_size', 'segment_index', 'shard_index',
                                  'bundle_hash', 'inner_leaf', 'outer_leaf', 'truncated'])
def test_invalid_combined_segment_proofs_are_rejected(example, fault):
    spec, shard = example
    index, shard_index = 0, shard.shard_index
    chunk = shard.segment_shards[index]
    proof = segment_shard_justification(shard, index)
    if fault == 'chunk':
        chunk = b'!' * len(chunk)
    elif fault == 'chunk_size':
        chunk += b'x'
    elif fault == 'segment_index':
        index = len(shard.segment_shards)
    elif fault == 'shard_index':
        shard_index = -1
    elif fault == 'bundle_hash':
        depth = len(shard.justification)
        proof = proof[:depth] + (bytes(32),) + proof[depth + 1:]
    elif fault == 'inner_leaf':
        proof = proof[:-1] + (bytes(len(proof[-1])),)
    elif fault == 'outer_leaf':
        proof = (bytes(len(proof[0])),) + proof[1:]
    else:
        proof = proof[:-1]
    with pytest.raises(ProcessWorkpackageError):
        verify_segment_shard(chunk, index, shard_index, proof, spec)


@pytest.mark.parametrize('field,value', [('length', -1), ('length', MAXIMUM_SIZE_AUDITABLE_BUNDLE + 1),
                                       ('length', True), ('exports_count', -1), ('exports_count', 3073),
                                       ('erasure_shards', 7), ('erasure_root', b'x')])
def test_invalid_specs_are_rejected(example, field, value):
    spec, shard = example
    with pytest.raises(ProcessWorkpackageError):
        verify_validator_shard(shard, replace(spec, **{field: value}))
