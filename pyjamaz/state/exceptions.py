class StateTransitionError(Exception):
    def __init__(self, custom_error_code):
        self.custom_error_code = custom_error_code
