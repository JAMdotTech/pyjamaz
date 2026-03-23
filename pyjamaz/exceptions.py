import enum

from jamcodec.mixins import Serializable


class StateComponentNotFound(ValueError):
    pass


class StateKeyNoResult(ValueError):
    pass


class PyjamazAppError(Exception):
    def __init__(self, custom_error_code):
        self.custom_error_code = custom_error_code


class StateTransitionError(PyjamazAppError):
    pass


class BlockValidationErrorCode(Serializable, enum.Enum):
    extrinsic_hash_mismatch = 0
    invalid_author_key = 1
    invalid_seal_key = 2
    bad_slot = 3
    bad_ticket_marker_data = 4
    bad_epoch_marker_data = 5
    bad_offender_marker_data = 6
    no_valid_ancestor = 7
    state_root_mismatch = 8
    historical_state_not_found = 9


class BlockValidationError(PyjamazAppError):
    pass


class ProcessWorkpackageError(ValueError):
    pass
