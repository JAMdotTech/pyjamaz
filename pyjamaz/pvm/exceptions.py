class UIntValueError(ValueError):
    pass

class InvalidOpcode(ValueError):
    pass

class PVMMemoryError(ValueError):
    pass

class PanicError(ValueError):
    pass

class PVMError(ValueError):
    pass


class PVMGasError(PVMError):
    """A PVM invocation supplied gas outside the unsigned 64-bit domain."""
