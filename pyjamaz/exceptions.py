class StateComponentNotFound(ValueError):
    pass


class StateKeyNoResult(ValueError):
    pass


class PyjamazAppError(Exception):
    def __init__(self, custom_error_code):
        self.custom_error_code = custom_error_code


class StateTransitionError(PyjamazAppError):
    pass


class BlockValidationError(PyjamazAppError):
    pass
