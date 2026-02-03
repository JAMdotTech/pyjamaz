import logging
from functools import wraps

from pyjamaz.pvm.exceptions import PanicError
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput


def hostcall(cost: int):
    if cost < 0:
        raise ValueError("hostcall cost must be non-negative")

    def hostcall_inner(func):

        @wraps(func)
        def hc_wrapped(*args, **kwargs):

            invocation_output = kwargs.get("invocation_output")
            if invocation_output is None:
                for value in args:
                    if isinstance(value, InvocationMutationOutput):
                        invocation_output = value
                        break
            if invocation_output is None:
                for value in kwargs.values():
                    if isinstance(value, InvocationMutationOutput):
                        invocation_output = value
                        break

            if invocation_output is None:
                raise PanicError("hostcall could not locate invocation_output")

            invocation_output.gas_limit -= cost
            if invocation_output.gas_limit < 0:
                logging.debug(f"hostcall {func} gas_limit reached")
                invocation_output.exit_condition = ExitCondition(reason=ExitReason.out_of_gas)
                return None

            return func(*args, **kwargs)

        return hc_wrapped

    return hostcall_inner
