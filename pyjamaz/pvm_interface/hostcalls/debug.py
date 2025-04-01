import logging

from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMLogger
from pyjamaz.pvm_interface.types import InvocationInput

LEVELS = {
    0: (logging.ERROR, "ERROR", "⛔"),
    1: (logging.WARNING, "WARNING", "⚠"),
    2: (logging.CRITICAL, "CRITICAL", "ℹ️"),
    3: (logging.INFO, "INFO", "💁"),
    4: (logging.DEBUG, "DEBUG", "🪡"),
}

def hc_log(ctx_in: InvocationInput, ctx_out: InvocationMutationOutput, logger: PVMLogger):
    """
    """
    level = ctx_in.registers[7]
    log_level = LEVELS.get(level, None)

    if ctx_in.registers[8] == 0 or ctx_in.registers[9] == 0:
        target = ""
    else:
        target = ctx_in.memory.read_bytes(ctx_in.registers[8], ctx_in.registers[9]).decode("utf-8")

    message = ctx_in.memory.read_bytes(ctx_in.registers[10], ctx_in.registers[11]).decode("utf-8")

    logger.hc_debug(log_level[0], log_level[1], None, ctx_in.service_id, target, message)
