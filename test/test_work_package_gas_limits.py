from unittest.mock import Mock

import pytest

import pyjamaz.refinement as refinement_module
import pyjamaz.graypaper_constants as gp_const
from pyjamaz.availability import BundleData
from pyjamaz.exceptions import ProcessWorkpackageError
from pyjamaz.hostcalls.models import PvmIsAuthorizedOutput, PvmRefineOutput
from pyjamaz.models.common import RefinementContext, WorkExecResult, WorkItem, WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.refinement import Refinement


@pytest.mark.parametrize('field,limit', [
    ('refine_gas_limit', gp_const.GAS_REFINE),
    ('accumulate_gas_limit', gp_const.GAS_ACCUMULATION),
])
@pytest.mark.parametrize('split,offset,rejected', [
    (False, -1, False),
    (False, 0, False),
    (False, 1, True),
    (True, -1, False),
    (True, 0, False),
    (True, 1, True),
])
def test_declared_package_gas_limits(monkeypatch, field, limit, split, offset, rejected):
    budgets = [limit // 2, limit - limit // 2 + offset] if split else [limit + offset]
    items = []
    for budget in budgets:
        item = WorkItem(service=42, code_hash=bytes(32), refine_gas_limit=1, accumulate_gas_limit=1,
                        export_count=0, payload=b'', import_segments=[], extrinsic=[])
        setattr(item, field, budget)
        items.append(item)
    context = RefinementContext(anchor=bytes(32), anchor_slot=0, state_root=bytes(32),
                                beefy_root=bytes(32), lookup_anchor=bytes(32), lookup_anchor_slot=0,
                                lookup_anchor_state_root=bytes(32), prerequisites=[])
    package = WorkPackage(auth_code_host=42, auth_code_hash=bytes(32), context=context,
                          authorization=b'', authorizer_config=b'', items=items)
    authorize = Mock(return_value=PvmIsAuthorizedOutput(WorkExecResult(ok=b''), 0))
    refine = Mock(return_value=PvmRefineOutput(WorkExecResult(ok=b''), [], 0))
    monkeypatch.setattr(WorkPackage, 'set_authorization_code', lambda *_: None)
    monkeypatch.setattr(refinement_module, 'pvm_invoke_is_authorized', authorize)
    monkeypatch.setattr(refinement_module, 'pvm_invoke_refine', refine)
    execution = Refinement(ServicesState(), BundleData())

    if rejected:
        with pytest.raises(ProcessWorkpackageError, match='work-package gas limits exceed core limits'):
            execution.compute_work_report(package, 0, {}, gp_const.VALIDATOR_COUNT)
        authorize.assert_not_called()
        refine.assert_not_called()
        assert execution.bundle == b''
        assert execution.exported_segments == []
    else:
        report = execution.compute_work_report(package, 0, {}, gp_const.VALIDATOR_COUNT)
        assert len(report.results) == len(items)
        authorize.assert_called_once_with(package, 0)
        assert refine.call_count == len(items)
