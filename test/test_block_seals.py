"""GP-0.8.0-eq:6.16: a valid ticket seal must also identify the winning ticket."""

from types import SimpleNamespace

import bandersnatch_vrfs
import pytest

from pyjamaz.exceptions import BlockValidationError, BlockValidationErrorCode
from pyjamaz.graypaper_constants import CORE_COUNT, EPOCH_TIMESLOTS
from pyjamaz.models.block import EpochMark, EpochMarkValidatorKeys, Extrinsic, Header
from pyjamaz.models.common import TicketBody
from pyjamaz.models.context import BlockContext
from pyjamaz.models.state import EntropyState, SlotSealerSeries
from pyjamaz.utils import vrf_input_ticket_seal
from pyjamaz.validation import BlockValidation


@pytest.fixture
def seal_validation():
    secret = bandersnatch_vrfs.secret_from_seed(bytes(32))
    public = bandersnatch_vrfs.public_from_secret(secret)
    entropy = b'e' * 32
    header = Header.default()
    header.author_index = 0
    header.timeslot = EPOCH_TIMESLOTS + 3
    context = BlockContext()

    def validate(series):
        BlockValidation(context).validate_header_after_safrole(
            header=header,
            post_entropy=EntropyState([bytes(32)] * 3 + [entropy]),
            post_validator_pool=SimpleNamespace(validators=[SimpleNamespace(bandersnatch=public)]),
            safrole_output=SimpleNamespace(
                post_state=SimpleNamespace(slot_sealer_series=series),
                tickets_mark=header.tickets_marker, epoch_mark=header.epoch_marker,
            ),
            disputes_output=SimpleNamespace(offenders_mark=header.offenders_marker),
            extrinsic=Extrinsic.default(),
        )
        return context.seal_vrf_output

    ticket = TicketBody(bandersnatch_vrfs.vrf_output(secret, vrf_input_ticket_seal(entropy, 1)), 1)
    header.seal = header.generate_ticket_seal(secret, entropy, ticket.attempt)
    return header, secret, public, entropy, ticket, validate


def test_matching_ticket_seal_is_accepted(seal_validation):
    header, secret, public, entropy, ticket, validate = seal_validation
    assert validate(SlotSealerSeries(tickets=[ticket] * EPOCH_TIMESLOTS)) == ticket.id


def test_valid_seal_for_another_ticket_is_rejected(seal_validation):
    header, secret, public, entropy, ticket, validate = seal_validation
    # The signature remains valid: only the selected winning ticket differs.
    other = TicketBody(bytes(32), ticket.attempt)
    assert header.verify_ticket_seal(public, other, entropy) == ticket.id
    tickets = [ticket] * EPOCH_TIMESLOTS
    tickets[header.timeslot % EPOCH_TIMESLOTS] = other

    with pytest.raises(BlockValidationError, match='winning ticket'):
        validate(SlotSealerSeries(tickets=tickets))


def test_invalid_ticket_signature_is_still_rejected(seal_validation):
    header, secret, public, entropy, ticket, validate = seal_validation
    header.seal = bytes(96)
    with pytest.raises(BlockValidationError, match='Invalid seal key'):
        validate(SlotSealerSeries(tickets=[ticket] * EPOCH_TIMESLOTS))


def test_fallback_seal_is_still_accepted(seal_validation):
    header, secret, public, entropy, ticket, validate = seal_validation
    header.seal = header.generate_fallback_seal(secret, entropy)
    expected = header.verify_fallback_seal(public, entropy)
    assert validate(SlotSealerSeries(keys=[public] * EPOCH_TIMESLOTS)) == expected


@pytest.mark.parametrize('count', [0, 3, 5] + ([7] if 3 * CORE_COUNT >= 7 else []))
def test_invalid_epoch_marker_count_is_a_block_error(seal_validation, count):
    header, secret, public, entropy, ticket, validate = seal_validation
    header.epoch_marker = EpochMark(
        bytes(32), bytes(32), [EpochMarkValidatorKeys(public, bytes(32)) for _ in range(count)],
    )
    header.seal = header.generate_ticket_seal(secret, entropy, ticket.attempt)

    with pytest.raises(BlockValidationError) as error:
        validate(SlotSealerSeries(tickets=[ticket] * EPOCH_TIMESLOTS))
    assert error.value.custom_error_code == BlockValidationErrorCode.bad_epoch_marker_data


@pytest.mark.parametrize('count', sorted({6, 3 * CORE_COUNT}))
def test_valid_epoch_marker_count_is_accepted(seal_validation, count):
    header, secret, public, entropy, ticket, validate = seal_validation
    header.epoch_marker = EpochMark(
        bytes(32), bytes(32), [EpochMarkValidatorKeys(public, bytes(32)) for _ in range(count)],
    )
    header.seal = header.generate_ticket_seal(secret, entropy, ticket.attempt)

    assert validate(SlotSealerSeries(tickets=[ticket] * EPOCH_TIMESLOTS)) == ticket.id
