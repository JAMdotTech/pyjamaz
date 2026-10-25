import asyncio
from types import SimpleNamespace

import pytest

from pyjamaz import refinement as refinement_module, graypaper_constants as gp_const
from pyjamaz.availability import availability_spec
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine
from pyjamaz.models.common import (
    RefinementContext, WorkExecResult, WorkItem, WorkPackage, WorkReport,
)
from pyjamaz.runtime.pipelines import refine


@pytest.fixture
def work_package():
    return WorkPackage(
        auth_code_host=0,
        auth_code_hash=bytes(32),
        context=RefinementContext(bytes(32), bytes(32), bytes(32), bytes(32), 0, []),
        authorization=b"",
        authorizer_config=b"",
        items=[WorkItem(0, bytes(32), 1000, 1000, 0, b"", [], [])],
    )


@pytest.mark.parametrize("assurer_count", [6, 9])
def test_refine_dispatch_preserves_assurer_count_across_live_set_change(
    monkeypatch, work_package, assurer_count,
):
    if assurer_count > gp_const.VALIDATOR_COUNT:
        pytest.skip("Nine validators exceed the Tiny validator maximum")

    services = ServicesState()
    services.set_state_storage(StateStorage(InMemoryStorageEngine()))
    services.pending_changes = PendingChanges()
    app = SimpleNamespace(
        working_state=SimpleNamespace(
            services=services,
            state_root=bytes(32),
            timeslot=SimpleNamespace(number=0),
            recent_history=SimpleNamespace(recent_blocks=[]),
            validator_pool=SimpleNamespace(validators=[SimpleNamespace(ed25519=bytes([i]) * 32) for i in range(assurer_count)]),
            safrole=SimpleNamespace(validators=[None] * gp_const.VALIDATOR_COUNT),
        ),
        get_core_assigment=lambda: 0,
        retrieve_block_hash=lambda _: bytes(32),
        d3l_store=None,
    )
    monkeypatch.setattr(WorkPackage, "set_authorization_code", lambda *_: None)
    monkeypatch.setattr(refinement_module, "pvm_invoke_is_authorized", lambda *_: SimpleNamespace(
        work_exec_result=WorkExecResult(ok=b"authorized"), gas_used=1,
    ))
    monkeypatch.setattr(refinement_module, "pvm_invoke_refine", lambda **_: SimpleNamespace(
        work_exec_result=WorkExecResult(ok=b"result"), gas_used=2, export_segments=[],
    ))
    reports = []

    async def dispatch(compute, *args):
        # Model a live epoch change after worker arguments have been captured.
        app.working_state.validator_pool.validators = [SimpleNamespace(ed25519=bytes([i % 256]) * 32) for i in range(gp_const.VALIDATOR_COUNT)]
        reports.append(compute(*args))
        # Stop this worker after inspecting the real report-construction path.
        raise asyncio.CancelledError

    monkeypatch.setattr(refine.anyio.to_thread, "run_sync", dispatch)

    async def run_worker():
        pipeline = refine.RefinePipeline(app)
        pipeline.add_work_package(work_package, [])
        await pipeline._refine_queue.put(pipeline._pending_work_packages[work_package.hash()])
        with pytest.raises(asyncio.CancelledError):
            await pipeline._refine_worker()

    asyncio.run(run_worker())

    assert len(reports) == 1
    report = reports[0]
    assert report.package_spec.erasure_shards == assurer_count
    decoded = WorkReport.from_jam_bytes(report.to_jam_bytes())
    assert decoded.package_spec.erasure_shards == assurer_count
    assert decoded.results[0].result.ok == b"result"


@pytest.mark.parametrize("count", [0, 5, 7, 3 * gp_const.CORE_COUNT + 3, True])
def test_package_spec_rejects_invalid_assurer_count(work_package, count):
    with pytest.raises(ValueError, match="invalid assurer count"):
        availability_spec(work_package.hash(), b'bundle', [], count)
