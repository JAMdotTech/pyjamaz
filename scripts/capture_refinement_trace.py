#!/usr/bin/env python3
"""Capture a Tiny bootstrap refinement case from PolkaJam 0.1.29 / GP 0.8.0.

Run with the PyJAMaz environment; the ordinary ``jamt`` on PATH is not used.
The generated report always comes from PolkaJam, never from PyJAMaz execution.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

os.environ['JAM_FUZZ'] = '1'
os.environ['JAM_FUZZ_SPEC'] = 'tiny'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets
from jamcodec.base import JamBytes

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.app import StateDump, TraceGenesis
from pyjamaz.models.block import Header
from pyjamaz.models.common import WorkPackage, WorkReport
from pyjamaz.models.state import PendingChanges, ServicesState
from pyjamaz.fuzzer.v1.types import RefineBundle, WorkPackageBundle
from pyjamaz.state.base import state_key_constructor_service_account
from pyjamaz.state.storage import StateStorage
from pyjamaz.storage import InMemoryStorageEngine


# Bootstrap 0.1.29 decodes Instructions { instructions: Vec<Instruction>,
# salt: [u8; 32] }. Empty bytes (or the vector prefix alone) panic.
BOOTSTRAP_NOOP_PAYLOAD = bytes(33)


def b64(data):
    return base64.b64encode(data).decode('ascii')


def unb64(value):
    return base64.b64decode(value, validate=True)


def decode(cls, data):
    stream = JamBytes(data)
    result = cls.from_jam_bytes(stream)
    if stream.get_remaining_length() or result.to_jam_bytes().to_bytes() != data:
        raise ValueError(f'Noncanonical {cls.__name__} from PolkaJam')
    return result


def reference_genesis(spec):
    """Preserve the reference header and state; compute its posterior root."""
    header = decode(Header, bytes.fromhex(spec['genesis_header']))
    keyvals = [(bytes.fromhex(k), bytes.fromhex(v)) for k, v in spec['genesis_state'].items()]
    if any(len(key) != 31 for key, _ in keyvals):
        raise ValueError('Reference state keys must be 31 bytes')
    genesis = TraceGenesis(header, StateDump(PatriciaMerkleTrie(keyvals).root(), keyvals))
    services = ServicesState(services={})
    services.set_state_storage(StateStorage(InMemoryStorageEngine(dict(keyvals))))
    services.pending_changes = PendingChanges()
    return genesis, services


class Rpc:
    def __init__(self, url, journal):
        self.url, self.journal = url, journal
        self.counter = 0

    async def request(self, method, params=None):
        self.counter += 1
        request = {'jsonrpc': '2.0', 'id': self.counter, 'method': method, 'params': params or []}
        raw = json.dumps(request)
        self.journal.append({'client': 'capture', 'direction': 'request', 'raw': raw, 'message': request})
        async with websockets.connect(self.url, open_timeout=3, max_size=20 * 1024 * 1024) as ws:
            await ws.send(raw)
            while True:
                raw = await asyncio.wait_for(ws.recv(), 10)
                response = json.loads(raw)
                self.journal.append({'client': 'capture', 'direction': 'response', 'raw': raw, 'message': response})
                if response.get('id') == request['id']:
                    if 'error' in response:
                        raise RuntimeError(f'{method}: {response["error"]}')
                    return response.get('result')


async def verify_genesis_inputs(rpc, genesis, services, package):
    """Prove the two historical code lookups use unchanged reference inputs."""
    block = b64(package.context.lookup_anchor)
    checks = []
    required = [(package.auth_code_host, package.auth_code_hash)]
    required.extend((item.service, item.code_hash) for item in package.items)
    for service_id, code_hash in dict.fromkeys(required):
        account_bytes = services.state_storage.get(state_key_constructor_service_account(service_id))
        actual_account = await rpc.request('serviceData', [block, service_id])
        if actual_account is None or unb64(actual_account) != account_bytes:
            raise ValueError(f'Service {service_id} differs from genesis at the lookup anchor')
        expected_code = services.historical_preimage_lookup(
            service_id, package.context.lookup_anchor_slot, code_hash,
        )
        actual_code = await rpc.request('servicePreimage', [block, service_id, b64(code_hash)])
        if expected_code is None or actual_code is None or unb64(actual_code) != expected_code:
            raise ValueError(f'Service {service_id} historical code differs from genesis')
        if blake2b_256_hash(expected_code) != code_hash:
            raise ValueError('Reference preimage does not match its code hash')
        expected_history = services.retrieve_preimage_availability(service_id, code_hash, len(expected_code))
        actual_history = await rpc.request('serviceRequest', [block, service_id, b64(code_hash), len(expected_code)])
        if actual_history != expected_history:
            raise ValueError(f'Service {service_id} preimage history differs from genesis')
        checks.append({
            'service_id': service_id, 'code_hash': code_hash.hex(), 'code_length': len(expected_code),
            'availability_history': actual_history,
            'account_sha256': hashlib.sha256(account_bytes).hexdigest(),
        })
    return checks


async def command(argv, commands, *, cwd, timeout=30):
    commands.append([str(arg) for arg in argv])
    process = await asyncio.create_subprocess_exec(
        *map(str, argv), cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                process.kill()
                await process.wait()
        raise
    output = output.decode(errors='replace')
    if process.returncode:
        raise RuntimeError(f'{Path(argv[0]).name} exited {process.returncode}:\n{output[-6000:]}')
    return output


async def capture(args, work):
    commands, journal, processes, logs = [], [], [], []
    node, jamt = args.binaries / 'polkajam', args.binaries / 'jamt'
    versions = {}
    for binary in (node, jamt):
        version = await command([binary, '--version'], commands, cwd=work)
        if version.splitlines() != [f'{binary.name} 0.1.29', 'GP 0.8.0']:
            raise ValueError(f'Expected {binary.name} 0.1.29 / GP 0.8.0; got {version.strip()}')
        versions[binary.name] = version.strip()
    spec_path = work / 'dev-spec.json'
    await command([
        node, '--config-path', work / 'config', '--chain', f'dev:{args.base_port}',
        'dump-spec', spec_path,
    ], commands, cwd=work)
    spec = json.loads(spec_path.read_text())
    genesis, services = reference_genesis(spec)
    rpc_url = f'ws://127.0.0.1:{args.rpc_port}'
    rpc = Rpc(rpc_url, journal)
    proxy = None
    try:
        startup_deadline = time.monotonic() + args.timeout
        # The ordinary gateway uses the reference release's supported builder
        # path, avoiding validator-to-validator forwarding of builder traffic.
        for index in range(7):
            argv = [
                node, '--config-path', work / f'config-{index}', '--chain', spec_path,
                'run', '--data-path', work / f'node-{index}',
                '--listen-ip', '127.0.0.1', '--pvm-backend', 'interpreter', '--finality-mode', 'dummy',
            ]
            if index == 6:
                # This release requires peer-id@address. Use its own advertised
                # native identity instead of reconstructing its peer-ID codec.
                bootnode = None
                while time.monotonic() < startup_deadline:
                    match = re.search(r'This node is (\S+)', (work / 'node-0.log').read_text())
                    if match:
                        bootnode = match.group(1)
                        break
                    if processes[0].returncode is not None:
                        raise RuntimeError('Reference validator 0 exited during startup')
                    await asyncio.sleep(0.1)
                if bootnode is None:
                    raise TimeoutError('Reference validator did not advertise its bootnode identity')
                argv += ['--mode', 'ordinary', '--bootnode', bootnode,
                         '--rpc', '--rpc-listen-ip', '127.0.0.1', '--rpc-port', str(args.rpc_port)]
            else:
                argv += ['--dev-validator', str(index), '--no-rpc']
            commands.append([str(arg) for arg in argv])
            log = (work / f'node-{index}.log').open('wb')
            logs.append(log)
            processes.append(await asyncio.create_subprocess_exec(
                *map(str, argv), cwd=work, stdout=log, stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, 'RUST_LOG': 'info'},
            ))
        deadline = time.monotonic() + args.timeout
        while True:
            if any(process.returncode is not None for process in processes):
                raise RuntimeError('A reference node exited during startup')
            try:
                parameters = await rpc.request('parameters')
                best = await rpc.request('bestBlock')
                if best is not None:
                    break
            except (OSError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError('PolkaJam RPC did not become ready')
            await asyncio.sleep(0.5)
        reference_root = await rpc.request('stateRoot', [b64(genesis.header.hash)])
        if reference_root is None or unb64(reference_root) != genesis.state.state_root:
            raise ValueError('Exported genesis does not match PolkaJam stateRoot')

        submissions = []

        async def record(client):
            async with websockets.connect(rpc_url, max_size=20 * 1024 * 1024) as upstream:
                async def forward(source, destination, direction):
                    async for payload in source:
                        message = json.loads(payload)
                        journal.append({'client': 'jamt', 'direction': direction, 'raw': payload, 'message': message})
                        if direction == 'request' and message.get('method') == 'submitWorkPackage':
                            submissions.append(message['params'])
                        await destination.send(payload)
                tasks = [asyncio.create_task(forward(client, upstream, 'request')),
                         asyncio.create_task(forward(upstream, client, 'response'))]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

        proxy = await websockets.serve(record, '127.0.0.1', args.proxy_port, max_size=20 * 1024 * 1024)
        jamt_output = await command([
            jamt, '--rpc', f'ws://127.0.0.1:{args.proxy_port}', '--trace', '--force-core', '0',
            'item', '0', '0x' + BOOTSTRAP_NOOP_PAYLOAD.hex(),
            '--refine-gas', '1000000', '--accumulate-gas', '1000000',
        ], commands, cwd=work, timeout=args.timeout)
        if len(submissions) != 1:
            raise ValueError(f'Expected one work-package submission, got {len(submissions)}')
        core, encoded_package, encoded_extrinsics = submissions[0]
        package_bytes = unb64(encoded_package)
        package = decode(WorkPackage, package_bytes)
        if (core != 0 or len(package.items) != 1 or package.items[0].service != 0
                or package.items[0].payload != BOOTSTRAP_NOOP_PAYLOAD or package.items[0].export_count
                or package.items[0].import_segments or package.items[0].extrinsic or encoded_extrinsics
                or package.items[0].refine_gas_limit != 1_000_000
                or package.items[0].accumulate_gas_limit != 1_000_000):
            raise ValueError('Captured package is not the requested bootstrap no-op workload')
        checks = await verify_genesis_inputs(rpc, genesis, services, package)
        report_hash = None
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            best = await rpc.request('bestBlock')
            status = await rpc.request('workPackageStatus', [
                best['header_hash'], b64(package.hash()), b64(package.context.anchor),
            ])
            if status:
                if 'Failed' in status:
                    raise ValueError(f'PolkaJam rejected the work package: {status["Failed"]}')
                reported = status.get('Reported') or status.get('Ready')
                if reported:
                    report_hash = unb64(reported['report_hash'])
                    break
            await asyncio.sleep(0.5)
        if report_hash is None:
            raise TimeoutError('PolkaJam did not report the package within the capture timeout')
        report_bytes = unb64(await rpc.request('workReport', [b64(report_hash)]))
        report = decode(WorkReport, report_bytes)
        if (report.hash() != report_hash or report.package_spec.hash != package.hash()
                or report.core_index != core or report.package_spec.erasure_shards != 6
                or len(report.results) != 1 or report.results[0].result.ok is None):
            raise ValueError('Reference work report did not successfully refine the submitted package')
        request = RefineBundle(core, {}, 6, WorkPackageBundle(package, [], [], []))
        args.output.mkdir(parents=True, exist_ok=True)
        artifacts = {
            'genesis.bin': genesis.to_jam_bytes().to_bytes(),
            'refine.bin': request.to_jam_bytes().to_bytes(),
            'report.bin': report_bytes,
        }
        if any((args.output / name).exists() for name in (*artifacts, 'source.json', 'README.md')):
            raise FileExistsError('Output fixture already exists; choose a new output directory')
        for name, data in artifacts.items():
            (args.output / name).write_bytes(data)
        source = {
            'description': 'PolkaJam bootstrap refinement; unchanged genesis historical inputs verified at lookup anchor.',
            'gp_version': '0.8.0', 'profile': 'tiny', 'tools': versions,
            'binary_sha256': {binary.name: hashlib.sha256(binary.read_bytes()).hexdigest()
                              for binary in (node, jamt)},
            'commands': commands, 'parameters': parameters,
            'chainspec_sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            'genesis_header_hash': genesis.header.hash.hex(), 'genesis_state_root': genesis.state.state_root.hex(),
            'package_hash': package.hash().hex(), 'report_hash': report_hash.hex(),
            'lookup_anchor': package.context.lookup_anchor.hex(), 'lookup_anchor_slot': package.context.lookup_anchor_slot,
            'payload': {
                'hex': BOOTSTRAP_NOOP_PAYLOAD.hex(),
                'meaning': 'Empty Bootstrap 0.1.29 instruction vector followed by a zero 32-byte salt.',
                'schema_source': 'https://docs.rs/crate/jam-bootstrap-service-common/0.1.29/source/src/lib.rs',
                'empty_byte_payload': 'Rejected: native Bootstrap 0.1.29 panics while decoding Instructions.',
            },
            'verified_genesis_inputs': checks, 'jamt_output': jamt_output,
            'artifacts': {name: hashlib.sha256(data).hexdigest() for name, data in artifacts.items()},
            'rpc_capture': journal,
        }
        (args.output / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
        (args.output / 'README.md').write_text(readme(args))
        print(f'Captured package {package.hash().hex()} and report {report_hash.hex()} in {args.output}')
    except BaseException:
        (work / 'rpc_capture.json').write_text(json.dumps(journal, indent=2) + '\n')
        for log in logs:
            log.flush()
        for index in range(len(logs)):
            tail = (work / f'node-{index}.log').read_text(errors='replace')[-1800:]
            print(f'Reference node {index} log tail:\n{tail}', file=sys.stderr)
        raise
    finally:
        if proxy is not None:
            proxy.close()
            await proxy.wait_closed()
        for process in processes:
            if process.returncode is None:
                process.terminate()
        for process in processes:
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                process.kill()
                await process.wait()
        for log in logs:
            log.close()


def readme(args):
    return f'''# PolkaJam bootstrap refinement trace

Captured with PolkaJam/jamt 0.1.29, GP 0.8.0, Tiny (six validators).
The package contains one successful service-0 bootstrap item, an empty instruction list,
no imports/exports/extrinsics, and 1,000,000 gas for refinement and accumulation.
The full expected report is PolkaJam's RPC result, preserved without normalization.

Bootstrap 0.1.29 requires an `Instructions` structure: a vector of instructions
followed by a 32-byte salt. The no-op payload is therefore 33 zero bytes (empty
vector plus deterministic salt). An empty byte payload panics in the reference
service and cannot be used as a successful no-op. The source schema is
https://docs.rs/crate/jam-bootstrap-service-common/0.1.29/source/src/lib.rs.

`genesis.bin` is the real reference genesis. It is not a live-block snapshot.
The capture verifies the required account, code and preimage-availability inputs
are unchanged at the package's lookup anchor before using this genesis for replay.
`source.json` contains these checks, exact commands and raw RPC requests/responses.

## Capture again

From the PyJAMaz checkout, using its Python environment:

```sh
.venv/bin/python scripts/capture_refinement_trace.py \\
  --binaries {args.binaries} --output /tmp/bootstrap-refinement
```

## Replay

Start the target, then run the second command from another terminal:

```sh
JAM_FUZZ=1 JAM_FUZZ_SPEC=tiny .venv/bin/python -m pyjamaz.cli fuzzer target --socket-path /tmp/pyjamaz-refine.sock
JAM_FUZZ=1 JAM_FUZZ_SPEC=tiny .venv/bin/python -m pyjamaz.cli fuzzer traces {args.output} --socket-path /tmp/pyjamaz-refine.sock
```

Replay checks the entire work report (including gas and commitments) and verifies
that refinement leaves the initialized state unchanged. Genuine disagreements
are reported as failures; the reference report must not be rewritten to match.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binaries', type=Path, required=True, help='Directory with matching polkajam and jamt binaries')
    parser.add_argument('--output', type=Path, required=True, help='New fixture directory')
    parser.add_argument('--base-port', type=int, default=42000)
    parser.add_argument('--rpc-port', type=int, default=20890)
    parser.add_argument('--proxy-port', type=int, default=20891)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--work-dir', type=Path, help='Keep reference node data/logs here for diagnosis')
    args = parser.parse_args()
    args.binaries, args.output = args.binaries.resolve(), args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Output directory must be new or empty; existing fixture files are never overwritten')
    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=False)
        asyncio.run(capture(args, args.work_dir.resolve()))
    else:
        with tempfile.TemporaryDirectory(prefix='pyjamaz-refine-', dir='/tmp') as directory:
            asyncio.run(capture(args, Path(directory)))


if __name__ == '__main__':
    main()
