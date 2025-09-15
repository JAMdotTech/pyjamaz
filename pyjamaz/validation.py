import logging
import time

from pyjamaz.models.stf_output import SafroleOutput, DisputesOutput

from pyjamaz.exceptions import BlockValidationError, BlockValidationErrorCode
from pyjamaz.graypaper_constants import COMMON_ERA, SLOT_PERIOD, EPOCH_TIMESLOTS, TICKET_ENTRIES, \
    TICKET_SUBMISSION_END_SLOT
from pyjamaz.models.block import Header, Extrinsic
from pyjamaz.models.context import BlockContext
from pyjamaz.models.state import EntropyState, ValidatorPoolState, SafroleState, TimeslotState
from pyjamaz import settings
from pyjamaz.utils import format_hash


class BlockValidation:

    def __init__(self, block_context: BlockContext):
        self.block_context = block_context

    @staticmethod
    def is_epoch_change(pre_slotnumber: int, post_slotnumber: int) -> bool:
        """
        GP-0.3.8-general: `e!=e' ? T, F` | Helper function that determines if the epoch has changed.

        Returns
        -------
        bool
            `True` when epoch has changed, `False` otherwise.
        """
        if pre_slotnumber == 0 and post_slotnumber % EPOCH_TIMESLOTS != 0:
            # TODO double-check what initial behavior should be when
            return False
        return pre_slotnumber // EPOCH_TIMESLOTS != post_slotnumber // EPOCH_TIMESLOTS

    @staticmethod
    def current_timeslot() -> int:
        return int(time.time() - COMMON_ERA) // SLOT_PERIOD

    def validate_header(self,
                        header: Header,
                        post_entropy: EntropyState,
                        post_validator_pool: ValidatorPoolState,
                        safrole_output: SafroleOutput,
                        disputes_output: DisputesOutput,
                        extrinsic: Extrinsic,
                        ):

        #  GP-0.5.4-eq:5.4 | Check extrinsic hash
        if header.extrinsic_hash != extrinsic.generate_extrinsic_hash():
            raise BlockValidationError(BlockValidationErrorCode.extrinsic_hash_mismatch)

        # Check marker data
        if header.tickets_marker != safrole_output.tickets_mark and header.slot_phase_index == TICKET_SUBMISSION_END_SLOT:
            raise BlockValidationError(BlockValidationErrorCode.bad_ticket_marker_data)

        if header.epoch_marker != safrole_output.epoch_mark:
            raise BlockValidationError(BlockValidationErrorCode.bad_epoch_marker_data)

        if header.offenders_marker != disputes_output.offenders_mark:
            raise BlockValidationError(BlockValidationErrorCode.bad_offender_marker_data)

        parent_header = self.block_context.get_parent(header)

        if parent_header is None:
            raise BlockValidationError(
                f"Parent hash {header.parent.hex()} does not has valid ancestor"
            )

        # GP-0.7.0-eq:5.7
        if header.timeslot <= parent_header.timeslot:
            raise BlockValidationError(BlockValidationErrorCode.bad_slot)

        # GP-0.7.0-eq:5.7
        if not settings.SKIP_TIMESLOT_WALL_CLOCK_CHECK and header.timeslot > self.current_timeslot():
            raise BlockValidationError(BlockValidationErrorCode.bad_slot)

        if header.parent_state_root != self.block_context.state_root:
            raise BlockValidationError(
                f"Parent state root {header.parent_state_root.hex()} does not match with  0x{self.block_context.state_root.hex()}"
            )

        # Validate seal
        entropy = post_entropy.entropy[3]
        author_key = post_validator_pool.validators[header.author_index].bandersnatch

        if safrole_output.post_state.slot_sealer_series.tickets is not None:
            ticket = safrole_output.post_state.slot_sealer_series.tickets[header.timeslot % EPOCH_TIMESLOTS]
            logging.debug(
                f'Validate ticket | Timeslot: {header.timeslot} | Ticket ID: {ticket.id.hex()} | Author: {author_key.hex()} | Entropy: {entropy.hex()} '
            )
            try:
                self.block_context.seal_vrf_output = header.verify_ticket_seal(author_key, ticket, entropy)
            except ValueError:
                raise BlockValidationError("Invalid seal key")

        elif safrole_output.post_state.slot_sealer_series.keys is not None:
            # Fallback method
            sealer_key = safrole_output.post_state.slot_sealer_series.keys[header.timeslot % EPOCH_TIMESLOTS]

            logging.debug(
                f'Validate key | Timeslot: {header.timeslot} |  Author: {format_hash(sealer_key)} | Entropy: {format_hash(entropy)}'
            )

            if author_key != sealer_key:
                # logging.error('Invalid author key')
                raise BlockValidationError("Invalid author key")
            try:

                logging.debug(f"Validate Seal with entropy {format_hash(entropy)}")

                self.block_context.seal_vrf_output = header.verify_fallback_seal(author_key, entropy)

            except ValueError:
                raise BlockValidationError("Invalid seal key")

    def validate_author(self, header: Header, post_safrole: SafroleState, post_validator_pool: ValidatorPoolState):
        pass

