import logging
from typing import List

from pyjamaz.hostcalls.constants import HostCallResult
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput, PVMLogger
from pyjamaz.pvm import PVMMemory
from pyjamaz.hostcalls import hostcall


LEVELS = {
    0: (logging.ERROR, "ERROR", "⛔"),
    1: (logging.WARNING, "WARNING", "⚠️"),
    2: (logging.INFO, "INFO", "ℹ️"),
    3: (logging.DEBUG, "DEBUG", "💁"),
    4: (logging.DEBUG, "DEBUG", "🪡"),
}

@hostcall(10)
def hc_log(
        registers: List[int],
        memory: PVMMemory,
        service_id: int,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    """
    logger and logger.pvm_regs("LOG")

    level = registers[7]
    log_level = LEVELS.get(level, None)

    if registers[8] == 0 or registers[9] == 0:
        target = ""
    else:
        try:
            target = memory.read_bytes(registers[8], registers[9]).decode("utf-8")
        except (UnicodeDecodeError, PVMMemoryError):
            target = '<decode-error>'

    try:
        message = memory.read_bytes(registers[10], registers[11]).decode("utf-8")
    except (UnicodeDecodeError, PVMMemoryError):
        message = '<decode-error>'

    logger and logger.hc_debug(log_level[0], log_level[1], None, service_id, target, message)
    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
    invocation_output.registers[7] = HostCallResult.WHAT.value
