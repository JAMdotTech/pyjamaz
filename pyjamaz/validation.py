import logging
import time

from pyjamaz.exceptions import BlockValidationError, BlockValidationErrorCode
from pyjamaz.graypaper_constants import COMMON_ERA, SLOT_PERIOD, EPOCH_TIMESLOTS
from pyjamaz.models.block import Header, BlockContext, Extrinsic
from pyjamaz.models.state import EntropyState, ValidatorPoolState, SafroleState, TimeslotState


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
                        pre_state_timeslot: TimeslotState,
                        post_entropy: EntropyState,
                        post_validator_pool: ValidatorPoolState,
                        post_safrole: SafroleState,
                        extrinsic: Extrinsic,
                        ):

        #  GP-0.5.4-eq:5.4 | Check extrinsic hash
        if header.extrinsic_hash != extrinsic.generate_extrinsic_hash():
            raise BlockValidationError(BlockValidationErrorCode.extrinsic_hash_mismatch)

        parent_header = self.block_context.get_parent(header)

        if not parent_header:
            raise BlockValidationError(
                f"Parent hash {header.parent.hex()} does not has valid ancestor"
            )

        # GP-0.5.4-eq:5.7
        if header.timeslot <= parent_header.timeslot or header.timeslot > self.current_timeslot():
            raise BlockValidationError(BlockValidationErrorCode.bad_slot)

        # TODO Check calculation, currently doesn't match Duna
        # if header.parent_state_root != self.block_context.state_root:
        #     raise BlockValidationError(
        #         f"Parent state root {header.parent_state_root.hex()} does not match with  0x{self.block_context.state_root.hex()}"
        #     )

        # Validate seal
        author_key = post_validator_pool.validators[header.author_index].bandersnatch

        self.block_context.author_bandersnatch_key = author_key

        # if self.is_epoch_change(parent_header.timeslot, header.timeslot):
        #     entropy = post_entropy.entropy[2]
        # else:
        entropy = post_entropy.entropy[3]

        if post_safrole.slot_sealer_series.tickets is not None:
            ticket = post_safrole.slot_sealer_series.tickets[header.timeslot % EPOCH_TIMESLOTS]
            logging.debug(
                f'Validate ticket | Timeslot: {header.timeslot} | Ticket ID: {ticket.id.hex()} | Author: {author_key.hex()} | Entropy: {entropy.hex()} '
            )
            self.block_context.seal_vrf_output = header.verify_ticket_seal(author_key, ticket, entropy)

        elif post_safrole.slot_sealer_series.keys is not None:
            # Fallback method
            sealer_key = post_safrole.slot_sealer_series.keys[header.timeslot % EPOCH_TIMESLOTS]

            logging.debug(
                f'Validate key | Timeslot: {header.timeslot} |  Author: {sealer_key.hex()} | Entropy: {entropy.hex()}'
            )

            if author_key != sealer_key:
                logging.error('Invalid author key')
                #raise BlockValidationError("Invalid author key")
            try:

                logging.debug(f"Validate Seal with entropy {entropy.hex()}")

                self.block_context.seal_vrf_output = header.verify_fallback_seal(author_key, entropy)

            except ValueError:
                raise BlockValidationError("Invalid seal key")

    def validate_author(self, header: Header, post_safrole: SafroleState, post_validator_pool: ValidatorPoolState):
        pass

