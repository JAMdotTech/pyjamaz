import asyncio
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from jamcodec.types import Bytes, U32, Vec

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.merkle import PatriciaMerkleTrie
from pyjamaz.models.block import Header
from pyjamaz.models.common import RefinementContext, WorkItem, WorkPackage
from pyjamaz.models.state import ServiceAccount
from pyjamaz.state.base import (
    state_key_constructor_preimage,
    state_key_constructor_preimage_availability,
    state_key_constructor_service_account,
)


REPOSITORY = Path(__file__).resolve().parents[1]


@pytest.fixture
def capture_module(monkeypatch):
    # Loading the executable script must not change the rest of pytest's profile
    # or import path, including when running the Full-profile test lane.
    with monkeypatch.context() as scoped:
        scoped.setenv('JAM_FUZZ', '1')
        scoped.setenv('JAM_FUZZ_SPEC', 'tiny')
        scoped.setattr(sys, 'path', list(sys.path))
        spec = importlib.util.spec_from_file_location(
            'capture_refinement_trace_under_test', REPOSITORY / 'scripts/capture_refinement_trace.py',
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def historical_case(capture_module):
    auth_code = Bytes.encode(b'authorizer metadata').to_bytes() + b'authorizer program'
    refine_code = Bytes.encode(b'refine metadata').to_bytes() + b'refine program'
    auth_hash, refine_hash = map(blake2b_256_hash, (auth_code, refine_code))
    account = ServiceAccount(
        code_hash=auth_hash, balance=10_000_000, gas_limit_accumulate=10,
        gas_limit_on_transfer=10, footprint_storage_bytes=200, deposit_offset=0,
        footprint_storage_items=4, storage_items={}, preimages={}, preimage_availability={},
        creation_slot=0, last_accumulation_slot=0, parent_service=0,
    )
    accounts = {
        0: account.to_serialized_bytes(),
        7: replace(account, code_hash=refine_hash).to_serialized_bytes(),
    }
    codes = {(0, auth_hash): auth_code, (7, refine_hash): refine_code}
    state = {state_key_constructor_service_account(sid): raw for sid, raw in accounts.items()}
    for (sid, code_hash), code in codes.items():
        state[state_key_constructor_preimage(sid, code_hash)] = code
        state[state_key_constructor_preimage_availability(sid, code_hash, len(code))] = (
            Vec(U32).encode([0]).to_bytes()
        )
    header = Header.default()
    header.parent_state_root = b'p' * 32
    spec = {
        'genesis_header': header.to_jam_bytes().to_bytes().hex(),
        'genesis_state': {key.hex(): value.hex() for key, value in state.items()},
    }
    genesis, services = capture_module.reference_genesis(spec)
    package = WorkPackage(
        auth_code_host=0,
        auth_code_hash=auth_hash,
        context=RefinementContext(
            anchor=b'a' * 32, state_root=b's' * 32, beefy_root=b'b' * 32,
            lookup_anchor=b'l' * 32, lookup_anchor_slot=42, prerequisites=[],
        ),
        authorization=b'',
        authorizer_config=b'',
        items=[WorkItem(7, refine_hash, 1_000_000, 1_000_000, 0, b'', [], [])],
    )

    class Rpc:
        def __init__(self):
            self.calls = []
            self.accounts = dict(accounts)
            self.codes = dict(codes)
            self.histories = {key: [0] for key in codes}

        async def request(self, method, params):
            self.calls.append((method, params))
            assert params[0] == capture_module.b64(package.context.lookup_anchor)
            sid = params[1]
            if method == 'serviceData':
                return capture_module.b64(self.accounts[sid])
            code_hash = base64.b64decode(params[2], validate=True)
            if method == 'servicePreimage':
                code = self.codes[(sid, code_hash)]
                return capture_module.b64(code) if code is not None else None
            assert method == 'serviceRequest'
            assert params[3] == len(codes[(sid, code_hash)])
            return self.histories[(sid, code_hash)]

    return SimpleNamespace(
        spec=spec, genesis=genesis, services=services, package=package,
        rpc=Rpc(), accounts=accounts, codes=codes,
    )


def verify(module, case):
    return asyncio.run(module.verify_genesis_inputs(
        case.rpc, case.genesis, case.services, case.package,
    ))


def test_decode_rejects_trailing_bytes(capture_module):
    header = Header.default()
    encoded = header.to_jam_bytes().to_bytes()
    assert capture_module.decode(Header, encoded).to_jam_bytes().to_bytes() == encoded

    with pytest.raises(ValueError, match='Noncanonical Header from PolkaJam'):
        capture_module.decode(Header, encoded + b'\x00')


def test_reference_genesis_preserves_encoded_header_and_state(capture_module, historical_case):
    spec = historical_case.spec
    original = deepcopy(spec)
    genesis, services = capture_module.reference_genesis(spec)
    keyvals = [(bytes.fromhex(key), bytes.fromhex(value))
               for key, value in spec['genesis_state'].items()]

    assert genesis.header.to_jam_bytes().to_bytes() == bytes.fromhex(spec['genesis_header'])
    assert genesis.state.keyvals == keyvals
    assert genesis.state.state_root == PatriciaMerkleTrie(keyvals).root()
    assert genesis.state.state_root != genesis.header.parent_state_root
    assert dict(services.state_storage.as_list()) == dict(keyvals)
    assert services.pending_changes.service_accounts == {}
    assert spec == original


def test_verify_genesis_inputs_checks_both_codes_at_exact_anchor(capture_module, historical_case):
    case = historical_case
    checks = verify(capture_module, case)

    assert checks == [
        {
            'service_id': sid, 'code_hash': code_hash.hex(), 'code_length': len(code),
            'availability_history': [0],
            'account_sha256': hashlib.sha256(case.accounts[sid]).hexdigest(),
        }
        for (sid, code_hash), code in case.codes.items()
    ]
    assert [method for method, _ in case.rpc.calls] == [
        'serviceData', 'servicePreimage', 'serviceRequest',
        'serviceData', 'servicePreimage', 'serviceRequest',
    ]


@pytest.mark.parametrize('service_id', [0, 7])
@pytest.mark.parametrize('changed', ['account', 'code', 'history', 'missing_code'])
def test_verify_genesis_inputs_rejects_changed_rpc_inputs(
        capture_module, historical_case, service_id, changed):
    case = historical_case
    code_hash = next(code_hash for sid, code_hash in case.codes if sid == service_id)
    if changed == 'account':
        case.rpc.accounts[service_id] += b'changed'
        message = f'Service {service_id} differs from genesis at the lookup anchor'
    elif changed == 'history':
        case.rpc.histories[(service_id, code_hash)] = [1]
        message = f'Service {service_id} preimage history differs from genesis'
    else:
        case.rpc.codes[(service_id, code_hash)] = b'changed' if changed == 'code' else None
        message = f'Service {service_id} historical code differs from genesis'

    with pytest.raises(ValueError, match=message):
        verify(capture_module, case)


@pytest.mark.parametrize('service_id', [0, 7])
def test_verify_genesis_inputs_requires_code_available_at_lookup_slot(
        capture_module, historical_case, service_id):
    case = historical_case
    code_hash = next(code_hash for sid, code_hash in case.codes if sid == service_id)
    code = case.codes[(service_id, code_hash)]
    # Bytes exist in genesis and the RPC, but they only become historically
    # available after this package's lookup slot. Current presence is insufficient.
    case.services.pending_changes.preimages_availability[(service_id, code_hash, len(code))] = [43]

    with pytest.raises(ValueError, match=f'Service {service_id} historical code differs from genesis'):
        verify(capture_module, case)
