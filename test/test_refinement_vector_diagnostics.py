"""Component diagnostics retain the oracle and isolate a bare-code adapter."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest
from jamcodec.types import Bytes, U32, Vec

from pyjamaz.availability import availability_spec
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import (
    RefinementContext, WorkDigest, WorkExecResult, WorkItem, WorkPackage, WorkReport,
)
from pyjamaz.pvm.constants import Opcode
from pyjamaz.pvm.types import PVMCode
from pyjamaz.state.base import state_key_constructor_preimage_availability


@pytest.fixture
def diagnostic_module(monkeypatch):
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, 'path', list(sys.path))
        spec = importlib.util.spec_from_file_location(
            'refinement_vector_diagnostics_under_test',
            Path(__file__).resolve().parents[1] / 'scripts/diagnose_refinement_vectors.py',
        )
        module = importlib.util.module_from_spec(spec)
        scoped.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def vector_factory(tmp_path):
    def create(*, metadata_wrapped=False):
        raw = bytes((Opcode.load_imm.value, 8, 0, 0, 0, 0, Opcode.jump_ind.value, 0))
        code = PVMCode(0, 0, len(raw), [], raw,
                       [True, False, False, False, False, False, True, False])
        encoded = code.to_jam_bytes().to_bytes()
        program = bytes(8) + (4096).to_bytes(3, 'little') + len(encoded).to_bytes(4, 'little') + encoded
        blob = Bytes.encode(b'').to_bytes() + program if metadata_wrapped else program
        code_hash = blake2b_256_hash(blob)
        context = RefinementContext(bytes(32), bytes(32), bytes(32), bytes(32), 0, [])
        item = WorkItem(1000, code_hash, 1000, 1000, 0, b'', [], [])
        package = WorkPackage(0, code_hash, context, b'', b'', [item])
        # The small program independently has an empty successful result and
        # consumes 22 gas. Preserve the corpus's deliberately raw authorizer
        # code hash so component success cannot manufacture a full-report pass.
        expected = WorkReport(
            availability_spec(package.hash(), package.to_jam_bytes().to_bytes(), [], 6),
            context, 0, code_hash, 1_000_000, b'auth', {},
            [WorkDigest.from_work_item(item, WorkExecResult(ok=b''), 22)],
        )
        availability_key = state_key_constructor_preimage_availability(1000, code_hash, len(blob))
        data = {
            'name': 'wrapped-code' if metadata_wrapped else 'bare-code',
            'core_idx': 0,
            'services': {'1000': {
                'service': {
                    'code_hash': '0x' + code_hash.hex(), 'balance': 1_000_000,
                    'min_item_gas': 1000, 'min_memo_gas': 1000, 'bytes': len(blob),
                    'items': 2, 'deposit_offset': 0, 'creation_slot': 0,
                    'last_accumulation_slot': 0, 'parent_service': 0,
                },
                'data': [{'key': '0x' + availability_key.hex(),
                          'value': '0x' + Vec(U32).encode([0]).to_bytes().hex()}],
                'preimage_blobs': [{'hash': '0x' + code_hash.hex(), 'blob': '0x' + blob.hex()}],
            }},
            'work_package': package.to_json(),
            'bundle': '0x' + package.to_jam_bytes().to_bytes().hex(),
            'expected': {'work_report': expected.to_json(), 'exported_segments': []},
        }
        source = tmp_path / (data['name'] + '.json')
        source.write_text(json.dumps(data, indent=2) + '\n')
        return source

    return create


def test_bare_blob_requires_explicit_adapter_to_reach_real_refinement(diagnostic_module, vector_factory):
    source = vector_factory()
    original = source.read_bytes()
    baseline = diagnostic_module.diagnose_vector(source)
    assert baseline['name'] == 'bare-code'
    assert baseline['items'][0]['pvm_entered'] is False
    assert baseline['items'][0]['gas_used'] == 0
    assert baseline['items'][0]['result_matches'] is False
    assert baseline['items_match'] is False
    assert baseline['full_report_matches'] is False
    assert baseline['source_unchanged'] is True
    assert source.read_bytes() == original


def test_adapter_matches_real_pvm_output_but_keeps_report_disagreement(diagnostic_module, vector_factory):
    source = vector_factory()
    original = source.read_bytes()
    result = diagnostic_module.diagnose_vector(source, bare_service_code=True)
    assert result['items'][0]['pvm_entered'] is True
    assert result['items'][0]['gas_used'] == 22
    assert result['items'][0]['result_matches'] is True
    assert result['items'][0]['gas_matches'] is True
    assert result['items_match'] is True
    assert result['exported_segments_match'] is True
    assert result['full_report_matches'] is False
    assert any('authorizer_hash' in difference for difference in result['report_differences'])
    assert result['assumptions']
    assert result['source_unchanged'] is True
    assert source.read_bytes() == original

    # A diagnostic adapter must not change extraction in subsequent calls.
    baseline = diagnostic_module.diagnose_vector(source)
    assert baseline['items'][0]['pvm_entered'] is False
    assert baseline['items_match'] is False


def test_metadata_wrapped_service_runs_without_adapter(diagnostic_module, vector_factory):
    source = vector_factory(metadata_wrapped=True)
    original = source.read_bytes()
    result = diagnostic_module.diagnose_vector(source)
    assert result['name'] == 'wrapped-code'
    assert result['items'][0]['pvm_entered'] is True
    assert result['items'][0]['gas_used'] == 22
    assert result['items_match'] is True
    assert result['exported_segments_match'] is True
    assert result['full_report_matches'] is False
    assert result['source_unchanged'] is True
    assert source.read_bytes() == original


def test_null_result_variants_compare_by_wire_value(diagnostic_module, vector_factory):
    source = vector_factory()
    data = json.loads(source.read_text())
    data['expected']['work_report']['results'][0]['result'] = {'panic': None}
    data['expected']['work_report']['results'][0]['refine_load']['gas_used'] = 0
    source.write_text(json.dumps(data))
    original = source.read_bytes()
    # Normal extraction of this bare blob fails before PVM entry. The actual
    # True marker and decoded Null marker encode the same panic variant.
    result = diagnostic_module.diagnose_vector(source)
    assert result['items'][0]['pvm_entered'] is False
    assert result['items'][0]['result_matches'] is True
    assert result['items_match'] is True
    assert source.read_bytes() == original
