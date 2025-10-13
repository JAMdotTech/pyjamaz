import logging

from pyjamaz import settings
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.debug_logger import PVMDebugLog


class PVMFormattedLog(PVMDebugLog):

    def pvm_counters(self):
        pass

    def pvm_header(self):
        pass

    def hc_regs(self, msg, phase):
        # TODO: set phase from pvm invoke, hardcoded accumulate for now
        msg = f"{self._pvm_id}_{phase}: {msg}"
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{reg_msg}"
        )

    def hc_log(self, msg, data):

        msg = f"{self._pvm_id}: {msg}"
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{data}"
        )

    def pvm_regs(self, msg):
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{reg_msg}"
        )

    def sbrk(self, cur_size, new_size, growth, alloc_mem):
        logging.debug(f"SBRK GROWN FROM {cur_size} TO {new_size} (growth {growth}, alloc mem: {alloc_mem})")

    def acl(self, cur_size, new_size, growth):
        logging.debug(f"ACL GROWN FROM {cur_size} TO {new_size} (growth: {growth})")

    def exc(self, exc_str):
        logging.warning(f"PVM EXCEPTION:\n{exc_str}")

    def hc_debug(self, log_lvl, log_lvl_name, core_idx, service_idx, target, message):
        target_str = ""
        if target:
            target_str = f"@{target} "

        if log_lvl_name == 'INFO':
            prefix_str = f"👀 {self._pvm_id}"
        else:
            prefix_str = f"{log_lvl_name}{target_str}"

        spacing = " " * (31 - (len(prefix_str)))
        logging.log(log_lvl, f'{prefix_str}{spacing}{message}')

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        if not settings.PVM_DEBUG_OPCODES:
            return

        regs = self._pvm.get_registers()

        opn = OpcodeNames[self._pvm.opcode]

        inst_str = (
            f"{self._pvm.inst_nr}: "
            f"PC {self._pvm.pc} "
            f"{opn} ({self._pvm.opcode})"
        )
        spacing = " " * (51 - len(str(inst_str)))
        logging.debug(
            f"{inst_str}"
            f"{spacing}"
            f"g={self._pvm.gas} "
            #f"pvmHash={format_hash(self.hash())} "
            f"reg={str(regs)}"
        )
