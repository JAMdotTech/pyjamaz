import logging
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.utils import format_hash


class PVMDunaLog(PVMDebugLog):

    def state(self):
        pass

    def header(self):
        pass

    @staticmethod
    def host_call(msg, data):
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{data}"
        )

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        regs = [int(x) for x in self._pvm.reg]

        opn = OpcodeNames[self._pvm.opcode]

        inst_str = (
            f"{self._pvm.inst_nr}: "
            f"PC {self._pvm.pc} "
            f"{opn}"
        )
        spacing = " " * (51 - len(str(inst_str)))
        logging.debug(
            f"{inst_str}"
            f"{spacing}"
            f"g={self._pvm.gas} "
            f"pvmHash={format_hash(self.hash())} "
            f"reg={str(regs)}"
        )
