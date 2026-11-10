"""GP-0.8.0-eq:B.13: normal returns override yielded output only when they are hashes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyjamaz.hostcalls import invocation
from pyjamaz.models.state import BeefyCommitmentMap, EntropyState
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import PvmMarshallingOutput


RETURNED_HASH = b'r' * 32
YIELDED_HASH = b'y' * 32


@pytest.mark.parametrize('returned,yielded,expected', [
    (b'', None, None),
    (b'r' * 31, None, None),
    (RETURNED_HASH, None, RETURNED_HASH),
    (b'r' * 33, None, None),
    (b'', YIELDED_HASH, YIELDED_HASH),
    (b'r' * 31, YIELDED_HASH, YIELDED_HASH),
    (RETURNED_HASH, YIELDED_HASH, RETURNED_HASH),
    (b'r' * 33, YIELDED_HASH, YIELDED_HASH),
])
def test_normal_return_selects_a_valid_accumulation_hash(monkeypatch, returned, yielded, expected):
    services = Mock()
    services.retrieve_service_account.return_value = SimpleNamespace(code_hash=bytes(32))
    services.retrieve_preimage.return_value = b'code'
    state = SimpleNamespace(services=services)
    context = SimpleNamespace(context=SimpleNamespace(
        state_context=state, deferred_transfers=[], invocation_output=yielded, preimages=[],
    ))
    monkeypatch.setattr(invocation.Preimage, 'extract', lambda blob: SimpleNamespace(
        serialized_program=b'', program_name='test',
    ))
    monkeypatch.setattr(invocation.AccumulateInvocationContext, 'create_from_accumulation_state',
                        lambda **kwargs: context)
    monkeypatch.setattr(invocation.PVMInvocation, 'pvm_invoke_marshalling',
                        lambda self, **kwargs: PvmMarshallingOutput(
                            gas_used=17, exit_condition=ExitCondition(ExitReason.halt, returned), context=context,
                        ))

    output = invocation.pvm_invoke_accumulate(
        state_context=state, timeslot=1, service_id=42, gas_limit=100,
        accumulation_inputs=[], post_entropy=EntropyState([bytes(32)] * 4),
    )

    assert output.accumulation_output == expected
    assert output.state_context is state
    assert output.gas_used == 17
    commitments = BeefyCommitmentMap()
    if output.accumulation_output is not None:
        commitments.add_accumulation_output(42, output.accumulation_output)
    commitments.to_jam_bytes()
