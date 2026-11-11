from unittest.mock import Mock

import pytest

import pyjamaz.refinement as refinement_module
from pyjamaz.availability import BundleData
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_SIZE_ENCODED_WORK_REPORT, VALIDATOR_COUNT
from pyjamaz.hostcalls.models import PvmIsAuthorizedOutput, PvmRefineOutput
from pyjamaz.merkle import ConstantDepthMerkleTree
from pyjamaz.models.common import RefinementContext, WorkExecResult, WorkItem, WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.refinement import Refinement


@pytest.fixture
def produce_report(monkeypatch):
    def produce(declared, outputs):
        items = [WorkItem(service=42, code_hash=bytes(32), refine_gas_limit=10, accumulate_gas_limit=10,
                          export_count=count, payload=b'', import_segments=[], extrinsic=[])
                 for count in declared]
        context = RefinementContext(anchor=bytes(32), anchor_slot=0, state_root=bytes(32),
                                    beefy_root=bytes(32), lookup_anchor=bytes(32), lookup_anchor_slot=0,
                                    lookup_anchor_state_root=bytes(32), prerequisites=[])
        package = WorkPackage(auth_code_host=42, auth_code_hash=bytes(32), context=context,
                              authorization=b'', authorizer_config=b'', items=items)
        monkeypatch.setattr(WorkPackage, 'set_authorization_code', lambda *_: None)
        monkeypatch.setattr(refinement_module, 'pvm_invoke_is_authorized',
                            lambda *args: PvmIsAuthorizedOutput(WorkExecResult(ok=b''), 0))
        refine = Mock(side_effect=outputs)
        monkeypatch.setattr(refinement_module, 'pvm_invoke_refine', refine)
        execution = Refinement(ServicesState(), BundleData())
        report = execution.compute_work_report(package, 0, {}, VALIDATOR_COUNT)
        return report, execution.exported_segments, refine
    return produce


@pytest.mark.parametrize('declared,actual,result,expected_error', [
    (2, 2, 'ok', 'ok'),
    (2, 1, 'ok', 'bad_exports'),
    (1, 2, 'ok', 'bad_exports'),
    (2, 0, 'panic', 'bad_exports'),
    (2, 2, 'panic', 'panic'),
    (0, 0, 'panic', 'panic'),
    (2, 0, 'oversize', 'digest_oversize'),
])
def test_failed_exports_are_padded_to_declared_count(produce_report, declared, actual, result, expected_error):
    returned = [bytes([i + 1]) * EC_SEGMENT_SIZE for i in range(actual)]
    execution = (WorkExecResult(panic=True) if result == 'panic' else
                 WorkExecResult(ok=b'x' * (MAXIMUM_SIZE_ENCODED_WORK_REPORT + 1) if result == 'oversize' else b'ok'))
    report, segments, _ = produce_report([declared], [PvmRefineOutput(execution, returned, 10)])
    assert report.results[0].result.enum_value()[0] == expected_error
    assert report.package_spec.exports_count == sum(r.refine_load.exports for r in report.results) == declared
    expected = returned if expected_error == 'ok' else [bytes(EC_SEGMENT_SIZE)] * declared
    assert segments == expected
    assert report.package_spec.exports_root == ConstantDepthMerkleTree(expected).root()


def test_padding_preserves_subsequent_segment_positions(produce_report):
    final_segment = b'z' * EC_SEGMENT_SIZE
    report, segments, refine = produce_report([2, 1], [
        PvmRefineOutput(WorkExecResult(ok=b'first'), [], 10),
        PvmRefineOutput(WorkExecResult(ok=b'second'), [final_segment], 10),
    ])
    assert segments == [bytes(EC_SEGMENT_SIZE), bytes(EC_SEGMENT_SIZE), final_segment]
    assert report.package_spec.exports_count == sum(r.refine_load.exports for r in report.results) == 3
    assert refine.call_args_list[1].kwargs['export_segment_offset'] == 2
