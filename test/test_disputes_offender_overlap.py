from copy import deepcopy

import pytest

from pyjamaz.exceptions import StateTransitionError
from pyjamaz.models.block import Culprit, ExtrinsicDisputes, Fault
from pyjamaz.models.context import AppContext, BlockContext
from pyjamaz.models.state import DisputesState
from pyjamaz.models.stf_output import DisputesErrorCode
from pyjamaz.signing import Ed25519Keypair
from pyjamaz.state.components import Disputes


BAD_REPORT = b'b' * 32
GOOD_REPORT = b'g' * 32


def prior_state(offenders=()):
    return DisputesState(
        good_set=[GOOD_REPORT], bad_set=[BAD_REPORT], wonky_set=[], offenders=list(offenders),
    )


def culprit(key):
    return Culprit(
        target=BAD_REPORT, key=key.public_key,
        signature=key.sign(b'jam_guarantee' + BAD_REPORT),
    )


def fault(key, *, target=BAD_REPORT, vote=True):
    return Fault(
        target=target, vote=vote, key=key.public_key,
        signature=key.sign((b'jam_valid' if vote else b'jam_invalid') + target),
    )


@pytest.fixture
def keys():
    return sorted(
        [Ed25519Keypair.from_seed(bytes([seed]) * 32) for seed in range(1, 4)],
        key=lambda key: key.public_key,
    )


@pytest.mark.parametrize('same_report', [False, True])
def test_culprit_and_fault_share_key_without_duplicate_posterior_offender(keys, same_report):
    key = keys[1]
    prior = prior_state([keys[0].public_key])
    original = deepcopy(prior)
    evidence = ExtrinsicDisputes(
        verdicts=[], culprits=[culprit(key)],
        faults=[fault(key) if same_report else fault(key, target=GOOD_REPORT, vote=False)],
    )

    output = Disputes(BlockContext(), AppContext()).state_transition(evidence, prior)

    assert output.offenders_mark == [key.public_key, key.public_key]
    assert output.post_state.offenders == [keys[0].public_key, key.public_key]
    assert output.post_state.bad_set == prior.bad_set
    assert output.post_state.good_set == prior.good_set
    assert prior == original


def test_offender_marker_concatenates_lists_while_posterior_unions_keys(keys):
    first, second, third = keys
    evidence = ExtrinsicDisputes(
        verdicts=[], culprits=[culprit(first), culprit(third)],
        faults=[fault(first), fault(second)],
    )

    output = Disputes(BlockContext(), AppContext()).state_transition(evidence, prior_state())

    assert output.offenders_mark == [
        first.public_key, third.public_key, first.public_key, second.public_key,
    ]
    assert output.post_state.offenders == [key.public_key for key in keys]


@pytest.mark.parametrize('kind', ['culprit', 'fault', 'both'])
def test_previously_reported_offender_is_still_rejected(keys, kind):
    key = keys[0]
    prior = prior_state([key.public_key])
    original = deepcopy(prior)
    evidence = ExtrinsicDisputes(
        verdicts=[], culprits=[culprit(key)] if kind != 'fault' else [],
        faults=[fault(key)] if kind != 'culprit' else [],
    )

    with pytest.raises(StateTransitionError) as error:
        Disputes(BlockContext(), AppContext()).state_transition(evidence, prior)

    assert error.value.custom_error_code == DisputesErrorCode.offender_already_reported
    assert prior == original


@pytest.mark.parametrize('kind,error_code', [
    ('culprit', DisputesErrorCode.culprits_not_sorted_unique),
    ('fault', DisputesErrorCode.faults_not_sorted_unique),
])
def test_duplicate_key_within_one_evidence_list_is_still_rejected(keys, kind, error_code):
    key = keys[0]
    evidence = ExtrinsicDisputes(
        verdicts=[], culprits=[culprit(key)] * 2 if kind == 'culprit' else [],
        faults=[fault(key)] * 2 if kind == 'fault' else [],
    )

    with pytest.raises(StateTransitionError) as error:
        Disputes(BlockContext(), AppContext()).state_transition(evidence, prior_state())

    assert error.value.custom_error_code == error_code


def test_shared_key_does_not_skip_fault_signature_validation(keys):
    key = keys[0]
    invalid_fault = fault(key)
    invalid_fault.signature = bytes(64)
    evidence = ExtrinsicDisputes(verdicts=[], culprits=[culprit(key)], faults=[invalid_fault])

    with pytest.raises(StateTransitionError) as error:
        Disputes(BlockContext(), AppContext()).state_transition(evidence, prior_state())

    assert error.value.custom_error_code == DisputesErrorCode.bad_signature


def test_shared_key_does_not_skip_fault_verdict_validation(keys):
    key = keys[0]
    evidence = ExtrinsicDisputes(verdicts=[], culprits=[culprit(key)], faults=[fault(key, vote=False)])

    with pytest.raises(StateTransitionError) as error:
        Disputes(BlockContext(), AppContext()).state_transition(evidence, prior_state())

    assert error.value.custom_error_code == DisputesErrorCode.fault_verdict_wrong


def test_reused_component_refreshes_prior_offender_snapshot(keys):
    key = keys[0]
    component = Disputes(BlockContext(), AppContext())
    evidence = ExtrinsicDisputes(verdicts=[], culprits=[culprit(key)], faults=[fault(key)])
    first = component.state_transition(evidence, prior_state())

    with pytest.raises(StateTransitionError) as error:
        component.state_transition(evidence, first.post_state)

    assert error.value.custom_error_code == DisputesErrorCode.offender_already_reported
    assert first.offenders_mark == [key.public_key, key.public_key]
    assert first.post_state.offenders == [key.public_key]
