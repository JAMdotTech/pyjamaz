"""Epoch-marker cardinality is a block-validity check, within a bounded codec."""

import pytest

from jamcodec.base import JamBytes
from jamcodec.types import VarInt64
from pyjamaz.fuzzer.v1.types import FuzzerMessage
from pyjamaz.graypaper_constants import CORE_COUNT
from pyjamaz.models.block import Block, EpochMark, Extrinsic, Header
from pyjamaz.models.state import ValidatorPoolState


MAX_VALIDATORS = 3 * CORE_COUNT
COUNTS = sorted({0, 3, 5, 6, MAX_VALIDATORS} | ({7} if MAX_VALIDATORS >= 7 else set()))


@pytest.mark.parametrize('count', COUNTS)
def test_marker_count_can_reach_block_validation(count):
    encoded = bytes(64) + VarInt64.encode(count).to_bytes() + bytes(64 * count)
    marker = EpochMark.from_jam_bytes(JamBytes(encoded))
    assert len(marker.validators) == count
    assert marker.to_jam_bytes().to_bytes() == encoded

    header = Header.default()
    header.epoch_marker = marker
    request = FuzzerMessage(import_block=Block(header, Extrinsic.default()))
    decoded = FuzzerMessage.from_jam_bytes(request.to_jam_bytes())
    assert decoded.import_block.header.epoch_marker == marker
    assert decoded.import_block.header.hash == header.hash


def test_marker_decoder_keeps_the_maximum_size_bound():
    encoded = bytes(64) + VarInt64.encode(MAX_VALIDATORS + 1).to_bytes()
    with pytest.raises(ValueError, match='invalid sequence length'):
        EpochMark.from_jam_bytes(JamBytes(encoded))


def test_validator_state_decoder_remains_strict():
    with pytest.raises(ValueError, match='invalid sequence length'):
        ValidatorPoolState.from_jam_bytes(JamBytes(VarInt64.encode(5).to_bytes()))
