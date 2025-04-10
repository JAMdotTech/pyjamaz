import logging
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.utils import format_hash


class PVMDunaLog(PVMDebugLog):
    logness = False

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

    def hc_debug(self, log_lvl, log_lvl_name, core_idx, service_idx, target, message):
        target_str = ""
        if target:
            target_str = f"target={target} "
        core_str = "corevm "
        if core_idx:
            core_str = f"core={core_idx} "#{service_idx}"
        prefix_str = f"{log_lvl_name}#{core_str}"
        msg_str = f'{target_str}msg="{message}"'
        spacing = " " * (51-(len(prefix_str)))
        logging.log(log_lvl, f'{prefix_str}{spacing}{msg_str}')

        if message.startswith("LOG_START:"):
            self._pvm.mem._heap.logness = True
            PVMDunaLog.logness = True
            print(
                f"PC      "
                f"INST                  "
                f"R1  "
                f"R2  "
                f"R3  "
                f"IMM1                    "
                f"IMM2                    "
                f"OFF1                    "
                f"OFF2                    "
                "CTX")
        elif message.startswith("LOG_END:"):
            self._pvm.mem._heap.logness = False
            PVMDunaLog.logness = False

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        if PVMDunaLog.logness == True:
            # regs = self._pvm.get_registers()
            #
            # opn = OpcodeNames[self._pvm.opcode]
            #
            # inst_str = (
            #     f"{self._pvm.inst_nr}: "
            #     f"PC {self._pvm.pc} "
            #     f"{opn}"
            # )
            #spacing = " " * (51 - len(str(inst_str)))
            # print(
            #     f"{inst_str}"
            #     f"{spacing}"
            #     f"g={self._pvm.gas} "
            #     f"pvmHash={format_hash(self.pvm_hash())} "
            #     f"reg={str(regs)}"
            # )
            ctx = {"reg": self._pvm.get_registers()}
            if context: ctx = ctx | {x:int(y) for (x,y) in context.items()}

            reg1 = reg1 and int(reg1) or ''
            reg2 = reg2 and int(reg2) or ''
            reg3 = reg3 and int(reg3) or ''
            imm1 = imm1 and int(imm1) or ''
            imm2 = imm2 and int(imm2) or ''
            off1 = off1 and int(off1) or ''
            off2 = off2 and int(off2) or ''

            opn = OpcodeNames[self._pvm.opcode]
            r1 = " " * (8 - len(str(self._pvm.inst_nr)))
            r2 = " " * (22 - len(opn))
            r3 = " " * (4 - len(str(reg1)))
            r33 = " " * (3 - len(str(reg1)))
            r4 = " " * (4 - len(str(reg2)))
            r44 = " " * (3 - len(str(reg2)))
            r5 = " " * (4 - len(str(reg3)))
            r55 = " " * (3 - len(str(reg3)))
            r6 = " " * (24 - len(str(imm1)))
            r7 = " " * (24 - len(str(imm2)))
            r8 = " " * (24 - len(str(off1)))
            r9 = " " * (24 - len(str(off2)))

            if opn not in self.log_opcodes:
                raise Exception(f"Unknown opcode {opn}")
            else:
                self.log_opcodes[opn] += 1

            print(
                f"{self._pvm.pc}{r1}"
                f"{opn}{r2}"
                f"{reg1 and ('ω' + str(reg1) + r33) or r3}"
                f"{reg2 and ('ω' + str(reg2) + r44) or r4}"
                f"{reg3 and ('ω' + str(reg3) + r55) or r5}"
                f"{imm1 and (str(imm1) + r6) or r6}"
                f"{imm2 and (str(imm2) + r7) or r7}"
                f"{off1 and (str(off1) + r8) or r8}"
                f"{off2 and (str(off2) + r9) or r9}"
                f"{str(ctx)}"
            )
        pass
