import logging
from functools import wraps
from inspect import signature

from pyjamaz.pvm.exceptions import PanicError
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput


def hostcall(cost_method):
    """
    Decorator to determine the gas cost to charge for this hostcall
    - A fixed charge: @hostcall(48) charges 48 gas
    - A cost function: @hostcall(fetch_cost) calculates the charge from the call’s arguments
    - A generated cost function: @hostcall(gas_cost_by_size(600, (248, 11))) charges 600 + ceil(248 × r11 / 1024)
  """
    if not callable(cost_method) and cost_method < 0:
        raise ValueError("hostcall cost must be non-negative")

    def hostcall_inner(func):
        parameters = signature(func)

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

            # Note: for dynamic argument handling, we use .bind(...) to map positional and keyword arguments to names,
            # this way cost functions can consistently access values such as args['registers'] and args['memory'].
            gas_cost = cost_method(parameters.bind(*args, **kwargs).arguments) if callable(cost_method) else cost_method
            invocation_output.gas_limit = int(invocation_output.gas_limit) - gas_cost
            if invocation_output.gas_limit < 0:
                logging.debug(f"hostcall {func} gas_limit reached")
                invocation_output.exit_condition = ExitCondition(reason=ExitReason.out_of_gas)
                return None

            return func(*args, **kwargs)

        return hc_wrapped

    return hostcall_inner
