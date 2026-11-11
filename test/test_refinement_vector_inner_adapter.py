"""Nested-code compatibility is explicit, narrow and confined to diagnostics."""

import pytest
from jamcodec.base import JamBytes
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException

from pyjamaz.pvm.types import PVMCode
from test.test_refinement_vector_diagnostics import diagnostic_module, vector_factory


@pytest.mark.parametrize('child,canonical', [
    ('00041832000000ffff01', '00040632000000ffff01'),
    ('0004080a0003', '0004020a0003'),
])
def test_observed_child_adapter_is_opt_in_and_restored(
        diagnostic_module, vector_factory, monkeypatch, child, canonical):
    source = vector_factory()
    original_source = source.read_bytes()
    original_decoder = PVMCode.from_jam_bytes.__func__
    invoke = diagnostic_module.pvm_invoke_refine

    def decode_child_then_invoke(**kwargs):
        # Exercise a nonzero stream offset as well as complete consumption.
        stream = JamBytes(b'prefix' + bytes.fromhex(child))
        stream.get_next_bytes(6)
        decoded = PVMCode.from_jam_bytes(stream)
        assert stream.get_remaining_length() == 0
        assert decoded.to_jam_bytes().to_bytes() == bytes.fromhex(canonical)
        assert decoded.is_valid(0)
        return invoke(**kwargs)

    monkeypatch.setattr(diagnostic_module, 'pvm_invoke_refine', decode_child_then_invoke)
    with pytest.raises(RemainingScaleBytesNotEmptyException, match='No more bytes available'):
        diagnostic_module.diagnose_vector(source, bare_service_code=True)

    result = diagnostic_module.diagnose_vector(
        source, bare_service_code=True, scale_inner_code=True,
    )
    assert result['inner_code_adaptations'] == [
        {'original': child, 'diagnostic_header': canonical},
    ]
    assert result['items'][0]['pvm_entered'] is True
    assert result['items'][0]['gas_used'] == 22
    assert result['items_match'] is True
    assert result['full_report_matches'] is False
    assert any('authorizer_hash' in entry for entry in result['report_differences'])
    assert source.read_bytes() == original_source
    assert PVMCode.from_jam_bytes.__func__ is original_decoder
    with pytest.raises(RemainingScaleBytesNotEmptyException, match='No more bytes available'):
        PVMCode.from_jam_bytes(JamBytes(bytes.fromhex(child)))


def test_unrecognized_child_is_rejected_and_adapter_restored_after_error(
        diagnostic_module, vector_factory, monkeypatch):
    source = vector_factory()
    original_source = source.read_bytes()
    original_decoder = PVMCode.from_jam_bytes.__func__

    def reject_unknown_child(**kwargs):
        # This malformed blob differs from either recognized child; the
        # diagnostic must not broadly accept SCALE or malformed programs.
        return PVMCode.from_jam_bytes(JamBytes(bytes.fromhex('00041832000000ffff02')))

    monkeypatch.setattr(diagnostic_module, 'pvm_invoke_refine', reject_unknown_child)
    with pytest.raises(RemainingScaleBytesNotEmptyException, match='No more bytes available'):
        diagnostic_module.diagnose_vector(source, bare_service_code=True, scale_inner_code=True)
    assert source.read_bytes() == original_source
    assert PVMCode.from_jam_bytes.__func__ is original_decoder
