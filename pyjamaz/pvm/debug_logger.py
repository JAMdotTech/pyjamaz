from datetime import datetime

import numpy as np

from pyjamaz.pvm.constants import OpcodeNames


class PVMDebugLog:

    def __init__(self, pvm, log_opcode_calls=True, log_opcode_calls_if_zero=False):
        np.seterr(over='ignore')
        self._pvm = pvm
        self.log_opcodes = {}
        self.log_opcode_calls = log_opcode_calls
        self.log_opcode_calls_if_zero = log_opcode_calls_if_zero

    def dump_code(self):
        with open(f"code-{datetime.now().strftime("%H:%M:%S")}.bin", "wb") as binary_file:
            data=self._pvm.program.to_serialized_bytes()
            binary_file.write(data) #program_bytes)

    def dump_test_vector(self):
        import json
        with open(f"vector-{datetime.now().strftime("%H:%M:%S")}.json", 'w') as fp:
            tt = {
                "name": "gas_basic_consume_all",
                "initial-regs": self._pvm.program.registers, #TODO: initial regs
                "initial-pc": 5, #TODO
                "initial-page-map": [],#TODO
                "initial-memory": [],#TODO
                "initial-gas": 10000,#TODO
                "program": [x for x in self._pvm.program.to_serialized_bytes()],
                "expected-status": "panic",
                "expected-regs": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0
                ],
                "expected-pc": 2,#TODO
                "expected-memory": [],#TODO
                "expected-gas": 0#TODO
            }
            json.dump(tt, fp)


    def state(self):
        print(
            f"\nGAS: {self._pvm.gas}\n"
            f"PC: {self._pvm.pc}\n"
        )

    def header(self):
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

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        ctx = {"reg": [int(x) for x in self._pvm.reg]}
        if context: ctx = ctx | context

        reg1 = reg1 or ''
        reg2 = reg2 or ''
        reg3 = reg3 or ''
        imm1 = imm1 or ''
        imm2 = imm2 or ''
        off1 = off1 or ''
        off2 = off2 or ''

        opn = OpcodeNames[self._pvm.opcode]
        r1 = " " * (8 - len(str(self._pvm.pc)))
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

    # Note: Basic debug logging
    # log_ctx = {
    #     "_pvm": None,
    #     "log_state": log_state,
    #     "log_header": log_header,
    #     # "log_footer": log_footer,
    #     "log_func": log_opcode,
    #     "log_dict": {},
    #     "log_opcode_calls": True,
    #     "log_opcode_calls_if_zero": False,
    # }