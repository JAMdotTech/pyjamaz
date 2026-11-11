"""Deferred contract tests for batch continuation and JSON result reporting.

Re-enable this module when ``fuzzer traces`` implements ``--results-file`` and
``--continue-on-error``, including the result schema asserted below.
"""

import asyncio
import json
from copy import deepcopy

import pytest
from asyncclick.testing import CliRunner

from pyjamaz import cli
from pyjamaz.fuzzer.v1.types import FuzzerMessage
from test.test_fuzzer_refinement_traces import case, fake_session


pytestmark = pytest.mark.skip(
    reason='Deferred: fuzzer traces batch reporting and continuation are not implemented',
)


def replay(folder, results_file, *options):
    return asyncio.run(CliRunner().invoke(cli.main, [
        'fuzzer', 'traces', str(folder), '--results-file', str(results_file), *options,
    ]))


def test_batch_continues_after_rejection_and_preserves_expected_reports(case, fake_session):
    case.write(case.folder / 'second')
    expected_before = {file: file.read_bytes() for file in case.folder.rglob('report.bin')}
    session = fake_session()
    send = session.send_request
    attempts = []

    async def respond(request):
        if request.refine_bundle is not None:
            attempts.append(request)
            if len(attempts) == 1:
                return FuzzerMessage(error='Unauthorized')
        return await send(request)

    session.send_request = respond
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code != 0
    report = json.loads(report_file.read_text())
    assert (report['total'], report['passed'], report['failed']) == (2, 1, 1)
    assert [row['status'] for row in report['results']] == ['failed', 'passed']
    assert report['results'][0]['response_error'] == 'Unauthorized'
    assert 'Unauthorized' in '\n'.join(report['results'][0]['failures'])
    assert all(row['state_unchanged'] is True for row in report['results'])
    assert session.connections == session.closes == 2
    assert sum(request.initialize is not None for request in session.requests) == 2
    assert sum(request.get_state is not None for request in session.requests) == 2
    assert len(attempts) == 2
    assert all(file.read_bytes() == raw for file, raw in expected_before.items())


def test_results_file_records_first_failure_before_default_fail_fast(case, fake_session):
    case.write(case.folder / 'second')
    session = fake_session(response=FuzzerMessage(error='Unauthorized'))
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file)
    assert result.exit_code != 0
    report = json.loads(report_file.read_text())
    assert (report['total'], report['passed'], report['failed']) == (1, 0, 1)
    assert report['results'][0]['response_error'] == 'Unauthorized'
    assert session.connections == session.closes == 1
    assert sum(request.initialize is not None for request in session.requests) == 1


def test_batch_preserves_rejection_and_get_state_failure_before_next_case(case, fake_session):
    case.write(case.folder / 'second')
    session = fake_session()
    send = session.send_request
    attempts = []

    async def respond(request):
        if request.refine_bundle is not None:
            attempts.append(request)
            if len(attempts) == 1:
                return FuzzerMessage(error='Unauthorized')
        if request.get_state is not None and len(attempts) == 1:
            raise RuntimeError('GetState disconnected')
        return await send(request)

    session.send_request = respond
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code != 0
    report = json.loads(report_file.read_text())
    assert (report['total'], report['passed'], report['failed']) == (2, 1, 1)
    first, second = report['results']
    assert first['status'] == 'failed'
    assert first['response_error'] == 'Unauthorized'
    assert first['state_unchanged'] is None
    failures = '\n'.join(first['failures'])
    assert 'Unauthorized' in failures
    assert 'GetState disconnected' in failures
    assert second['status'] == 'passed'
    assert second['state_unchanged'] is True
    assert len(attempts) == 2
    assert session.connections == session.closes == 2
    assert sum(request.initialize is not None for request in session.requests) == 2


def test_batch_report_records_field_differences_and_state_mutation(case, fake_session):
    actual = deepcopy(case.report)
    actual.auth_gas_used += 1
    actual.results[0].result.ok = b'different output'
    fake_session(response=FuzzerMessage(work_report=actual), state=[(b'm' * 31, b'changed')])
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code != 0
    report = json.loads(report_file.read_text())
    assert report['failed'] == report['total'] == 1
    row = report['results'][0]
    assert row['status'] == 'failed'
    assert row['response_error'] is None
    assert row['state_unchanged'] is False
    differences = '\n'.join(row['report_differences'])
    assert 'auth_gas_used' in differences
    assert 'results[0].result.ok' in differences
    assert 'expected=' in differences and 'actual=' in differences
    assert any('Refinement changed initialized state' in failure for failure in row['failures'])


def test_successful_batch_has_zero_exit_and_complete_summary(case, fake_session):
    case.write(case.folder / 'second')
    session = fake_session()
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code == 0, result.output or result.exception
    report = json.loads(report_file.read_text())
    assert (report['total'], report['passed'], report['failed']) == (2, 2, 0)
    assert all(row['status'] == 'passed' for row in report['results'])
    assert all(row['failures'] == [] for row in report['results'])
    assert all(row['state_unchanged'] is True for row in report['results'])
    assert session.connections == session.closes == 2


def test_batch_records_incomplete_case_and_runs_remaining_case(case, fake_session):
    case.write(case.folder / 'second')
    (case.folder / 'second' / 'genesis.bin').unlink()
    session = fake_session()
    report_file = case.folder / 'results.json'
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code != 0
    report = json.loads(report_file.read_text())
    assert (report['total'], report['passed'], report['failed']) == (2, 1, 1)
    failed = next(row for row in report['results'] if row['status'] == 'failed')
    assert 'genesis.bin' in '\n'.join(failed['failures'])
    assert failed['state_unchanged'] is None
    assert sum(request.initialize is not None for request in session.requests) == 1


def test_results_file_cannot_overwrite_fixture_input(case, fake_session):
    session = fake_session()
    report_file = case.folder / 'report.bin'
    expected_before = report_file.read_bytes()
    result = replay(case.folder, report_file, '--continue-on-error')
    assert result.exit_code != 0
    assert report_file.read_bytes() == expected_before
    assert session.requests == []


def test_continue_on_error_rejects_mixed_block_and_refinement_inputs(case, fake_session):
    (case.folder / '00000001.bin').write_bytes(b'block trace')
    session = fake_session()
    result = replay(case.folder, case.folder / 'results.json', '--continue-on-error')
    assert result.exit_code != 0
    assert 'refinement' in result.output.lower()
    assert session.requests == []
