#!/usr/bin/env python3
"""Run real refine components under explicit corpus assumptions, outside conformance.

The strict fuzzer remains unchanged. Authorization is a fixed test dependency
(b'auth', 1,000,000 gas), not a successful IsAuthorized invocation. Package
domain checks and import verification are recorded separately. The optional
bare-code adapter operates only during this script's component invocation.
No package, source preimage, proof or expected report is rewritten.
"""

import argparse
import hashlib
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jamcodec.base import JamBytes

from pyjamaz.availability import BundleData, availability_spec, validate_work_package
from pyjamaz.cli import _report_differences
from pyjamaz.fuzzer.refinement_vectors import load_refinement_vector
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_SIZE_ENCODED_WORK_REPORT
from pyjamaz.hostcalls.invocation import pvm_invoke_refine
from pyjamaz.models.common import Preimage, WorkDigest, WorkExecResult, WorkReport
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.pvm.invocation import PVMInvocation
from pyjamaz.pvm.types import PVMCode, PVMProgram
from pyjamaz.settings import GP_VERSION, PVM_INTERPRETER, TEST_SUITE
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


AUTH_OUTPUT = b'auth'
AUTH_GAS = 1_000_000
# Only the two observed foreign-encoded child programs are adapted. This is
# diagnostic evidence, not a permissive fallback in the production decoder.
SCALE_CHILD_CODES = {
    bytes.fromhex('00041832000000ffff01'): bytes.fromhex('00040632000000ffff01'),
    bytes.fromhex('0004080a0003'): bytes.fromhex('0004020a0003'),
}


def _groups(flat, lengths):
    groups, start = [], 0
    for length in lengths:
        groups.append(flat[start:start + length])
        start += length
    assert start == len(flat)
    return groups


def diagnose_vector(source: Path, bare_service_code: bool = False, scale_inner_code: bool = False):
    source = Path(source)
    raw = source.read_bytes()
    original = json.loads(raw)
    genesis, request, expected = load_refinement_vector(source)
    package, wire = request.bundle.work_package, request.bundle
    engine = InMemoryStorageEngine(dict(genesis.state.keyvals))
    services = ServicesState(services={})
    services.set_state_storage(StateStorage(engine))
    services.pending_changes = PendingChanges()

    assumptions = [
        'component diagnostic only; strict fuzzer validation is unchanged',
        "fixed external authorization dependency: output=b'auth', gas=1000000; no IsAuthorized execution",
        'invoke items outside the package gas-domain check',
        'supply original import bytes to the component without accepting their proof as valid',
    ]
    gates = {}
    try:
        validate_work_package(package)
        gates['package_domain'] = None
    except Exception as exc:
        gates['package_domain'] = str(exc)
    data = BundleData.from_parts(package, wire.extrinsics, wire.import_segments, wire.justifications)
    try:
        for item in package.items:
            data.import_segments(request.segment_root_lookup, item)
        gates['imports'] = None
    except Exception as exc:
        gates['imports'] = str(exc)
    package.set_authorization_code(services)
    gates['authorization_code_available'] = package.authorization_code is not None

    original_extract = Preimage.extract
    metadata = []
    bare_blobs = set()
    for item in package.items:
        blob = services.historical_preimage_lookup(item.service, package.context.lookup_anchor_slot, item.code_hash)
        if blob is None:
            continue
        parsed = original_extract(blob)
        raw_program_valid = PVMProgram.from_serialized_bytes(blob, b'', 'diagnostic') is not None
        metadata.append({'service': item.service, 'blob_length': len(blob),
                         'normal_metadata_length': len(parsed.metadata),
                         'bare_program_valid': raw_program_valid})
        if bare_service_code:
            if not raw_program_valid:
                raise ValueError('bare-service-code assumption requested for an invalid bare program')
            bare_blobs.add(bytes(blob))

    def extract(blob):
        if bytes(blob) in bare_blobs:
            return Preimage(b'', 0, 'bare service component diagnostic', '', '', [], bytes(blob))
        return original_extract(blob)

    imports = _groups(wire.import_segments, [len(item.import_segments) for item in package.items])
    extrinsics = _groups(wire.extrinsics, [len(item.extrinsic) for item in package.items])
    digests, exports, items = [], [], []
    size, offset = len(AUTH_OUTPUT), 0
    vm_entries = []
    original_invoke = PVMInvocation.pvm_invoke_host_call
    original_deblob = PVMCode.from_jam_bytes
    inner_adaptations = []

    def deblob(cls, stream, strict_decoding=True):
        raw_child = bytes(stream.data[stream.offset:])
        if raw_child in SCALE_CHILD_CODES:
            adapted = SCALE_CHILD_CODES[raw_child]
            decoded = original_deblob(JamBytes(adapted), strict_decoding=strict_decoding)
            stream.get_next_bytes(len(raw_child))
            inner_adaptations.append({'original': raw_child.hex(), 'diagnostic_header': adapted.hex()})
            return decoded
        return original_deblob(stream, strict_decoding=strict_decoding)

    def invoke(instance, *args, **kwargs):
        vm_entries.append(True)
        return original_invoke(instance, *args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(PVMInvocation, 'pvm_invoke_host_call', invoke))
        if bare_service_code:
            assumptions.append('interpret supplied preimage bytes directly as a bare standard PVM program')
            stack.enter_context(patch.object(Preimage, 'extract', extract))
        if scale_inner_code:
            assumptions.append('decode the two observed child-code length headers as SCALE compact; original input bytes unchanged')
            stack.enter_context(patch.object(PVMCode, 'from_jam_bytes', classmethod(deblob)))
        for index, item in enumerate(package.items):
            entered_before = len(vm_entries)
            output = pvm_invoke_refine(
                core_index=request.core_index, work_item_index=index, work_package=package,
                authorizer_output=AUTH_OUTPUT, work_items_import_segments=imports,
                export_segment_offset=offset, services_state=services, extrinsics=extrinsics,
            )
            # Apply the same GP 14.13 report-result rules as Refinement; the
            # native output and VM-entry evidence remain visible separately.
            result, item_exports = output.work_exec_result, output.export_segments
            if size + len(result.ok or b'') > MAXIMUM_SIZE_ENCODED_WORK_REPORT:
                result = WorkExecResult(digest_oversize=True)
            elif len(item_exports) != item.export_count:
                result = WorkExecResult(bad_exports=True)
            if result.ok is None:
                item_exports = [bytes(EC_SEGMENT_SIZE)] * item.export_count
            else:
                size += len(result.ok)
            digest = WorkDigest.from_work_item(item, result, output.gas_used)
            oracle = expected.results[index] if index < len(expected.results) else None
            items.append({
                'index': index, 'pvm_entered': len(vm_entries) > entered_before,
                'native_result': output.work_exec_result.to_json(),
                'reported_result': result.to_json(), 'gas_used': output.gas_used,
                'expected_gas': oracle.refine_load.gas_used if oracle else None,
                'result_matches': oracle is not None and result.to_jam_bytes().to_bytes() == oracle.result.to_jam_bytes().to_bytes(),
                'gas_matches': oracle is not None and output.gas_used == oracle.refine_load.gas_used,
            })
            digests.append(digest)
            exports.extend(item_exports)
            offset += item.export_count

    # Keep our computed authorizer hash and availability commitments. Never
    # copy those fields from the oracle to manufacture a report match.
    report = WorkReport(
        availability_spec(package.hash(), bytes.fromhex(original['bundle'][2:]), exports, request.erasure_shards),
        package.context, request.core_index, package.authorizer_hash(), AUTH_GAS,
        AUTH_OUTPUT, request.segment_root_lookup, digests,
    )
    expected_exports = [bytes.fromhex(value[2:]) for value in original['expected']['exported_segments']]
    return {
        'name': original['name'], 'source': str(source.resolve()),
        'source_sha256': hashlib.sha256(raw).hexdigest(), 'assumptions': assumptions,
        'strict_gates': gates, 'code_packaging': metadata, 'items': items,
        'inner_code_adaptations': inner_adaptations,
        'items_match': len(digests) == len(expected.results) and all(
            actual.to_jam_bytes().to_bytes() == oracle.to_jam_bytes().to_bytes()
            for actual, oracle in zip(digests, expected.results)),
        'exported_segments_match': exports == expected_exports,
        'exported_segments_count': len(exports),
        'full_report_matches': report.to_jam_bytes().to_bytes() == expected.to_jam_bytes().to_bytes(),
        'report_differences': list(_report_differences(expected.to_json(), report.to_json())),
        'actual_report': report.to_json(),
        'source_unchanged': source.read_bytes() == raw,
        'state_storage_unchanged': dict(services.state_storage.as_list()) == dict(genesis.state.keyvals),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='New JSON diagnostic report')
    parser.add_argument('--bare-service-code', action='store_true')
    parser.add_argument('--scale-inner-code', action='store_true', help='Adapt only the two observed SCALE-encoded child-code headers')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a new file')
    files = sorted(args.source.glob('*.json')) if args.source.is_dir() else [args.source]
    if not files:
        parser.error('no JSON vectors found')
    results = []
    for file in files:
        try:
            result = diagnose_vector(file, args.bare_service_code, args.scale_inner_code)
            print(f"{file.stem}: PVM entries={sum(item['pvm_entered'] for item in result['items'])}, "
                  f"items_match={result['items_match']}, exports_match={result['exported_segments_match']}, "
                  f"full_report_matches={result['full_report_matches']}", flush=True)
        except Exception as exc:
            result = {'name': file.stem, 'error': f'{type(exc).__name__}: {exc}'}
            print(f"{file.stem}: {result['error']}", flush=True)
        results.append(result)
    summary = {'diagnostic_only': True, 'profile': TEST_SUITE, 'backend': PVM_INTERPRETER,
               'graypaper_version': GP_VERSION, 'bare_service_code': args.bare_service_code,
               'scale_inner_code': args.scale_inner_code,
               'total': len(results), 'errors': sum('error' in row for row in results),
               'pvm_entries': sum(sum(item['pvm_entered'] for item in row.get('items', [])) for row in results),
               'cases_with_matching_items': sum(row.get('items_match', False) for row in results),
               'cases_with_matching_exports': sum(row.get('exported_segments_match', False) for row in results),
               'matching_full_reports': sum(row.get('full_report_matches', False) for row in results),
               'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(summary, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: value for key, value in summary.items() if key != 'results'}), flush=True)
    # Full report mismatches remain visible and keep the command nonzero.
    return 0 if summary['matching_full_reports'] == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
