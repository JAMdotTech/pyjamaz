import logging
from typing import List

from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMLogger, PVMMemory


LEVELS = {
    0: (logging.ERROR, "ERROR", "⛔"),
    1: (logging.WARNING, "WARNING", "⚠"),
    2: (logging.CRITICAL, "CRITICAL", "ℹ️"),
    3: (logging.INFO, "INFO", "💁"),
    4: (logging.DEBUG, "DEBUG", "🪡"),
}

def hc_log(
        registers: List[int],
        memory: PVMMemory,
        service_id: int,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    """
    logger.pvm_regs("LOG")

    level = registers[7]
    log_level = LEVELS.get(level, None)

    if registers[8] == 0 or registers[9] == 0:
        target = ""
    else:
        target = memory.read_bytes(registers[8], registers[9]).decode("utf-8")

    message = memory.read_bytes(registers[10], registers[11]).decode("utf-8")

    logger.hc_debug(log_level[0], log_level[1], None, service_id, target, message)
    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
