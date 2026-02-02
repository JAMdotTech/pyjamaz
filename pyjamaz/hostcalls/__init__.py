import inspect
import logging

from pyjamaz.pvm.exceptions import PanicError
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput


def hostcall(cost: int):

    def hostcall_inner(func):

        def hc_wrapped(*args, **kwargs):

            #invocation_output = kwargs.get("invocation_output")
            signature = inspect.signature(func)
            param_names = list(signature.parameters.keys())
            invocation_output_index = (
                param_names.index("invocation_output")
                if "invocation_output" in signature.parameters
                else None
            )
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
                raise PanicError("hostcall could not locate invocation_output")

            invocation_output.gas_limit -= cost
            if invocation_output.gas_limit < 0:
                logging.debug(f"hostcall {func} gas_limit reached")
                invocation_output.exit_condition = ExitCondition(reason=ExitReason.out_of_gas)
                return None

            return func(*args, **kwargs)

        return hc_wrapped

    return hostcall_inner
