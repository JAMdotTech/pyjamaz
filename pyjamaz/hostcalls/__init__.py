from functools import wraps
import inspect
from typing import Callable, TypeVar

from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput

R = TypeVar("R")


def hostcall(cost: int) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator for hostcalls to charge a fixed gas cost and halt on OOG.
    """
    if cost < 0:
        raise ValueError("hostcall cost must be non-negative")

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        signature = inspect.signature(func)
        param_names = list(signature.parameters.keys())
        invocation_output_index = (
            param_names.index("invocation_output")
            if "invocation_output" in signature.parameters
            else None
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            if "invocation_output" in kwargs:
                invocation_output = kwargs["invocation_output"]
            elif invocation_output_index is not None and len(args) > invocation_output_index:
                invocation_output = args[invocation_output_index]
            else:
                invocation_output = next(
                    (value for value in list(args) + list(kwargs.values())
                     if isinstance(value, InvocationMutationOutput)),
                    None
                )

            if invocation_output is None:
                raise RuntimeError("hostcall could not locate invocation_output")

            invocation_output.gas_limit -= cost
            if invocation_output.gas_limit < 0:
                invocation_output.exit_condition = ExitCondition(reason=ExitReason.out_of_gas)
                return None

            return func(*args, **kwargs)

        return wrapper

    return decorator
