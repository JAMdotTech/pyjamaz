import logging
from datetime import datetime

import numpy as np

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.types import PVMMemory, PVMLogger


class PVMDebugLog(PVMLogger):

    def __init__(self, pvm, log_opcode_calls=True, log_opcode_calls_if_zero=False):
        np.seterr(over='ignore')
        self._pvm = pvm
        self._pvm_id = self._pvm.metadata.decode("utf-8")
        self._initial_gas = pvm.gas  # TODO: sla op in logger!
        self._initial_pc = pvm.pc
        self.log_opcodes = {}
        self.log_opcode_calls = log_opcode_calls
        self.log_opcode_calls_if_zero = log_opcode_calls_if_zero

    def dump_code(self):
        with open(f"code-spi-{datetime.now().strftime('%H:%M:%S')}.bin", "wb") as binary_file:
            data=self._pvm.program.to_serialized_bytes()
            binary_file.write(data) #program_bytes)

    def dump_test_vector(self):
        import json

        initial_page_map = []
        initial_memory = []

        mem_segments = [
            self._pvm.program.memory._rom,
            self._pvm.program.memory._heap,
            self._pvm.program.memory._stack,
            self._pvm.program.memory._args
        ]

        for mem in mem_segments:
            if mem and mem.size > 0:
                initial_page_map.append({
                    "address": int(mem.address),
                    "length": int(mem.size),
                    "is-writable": mem.writable,
                })

                #end_idx = 0
                for idx, value in enumerate(mem.contents):
                    #if value > 0:
                    initial_memory.append({
                        "address": mem.address+idx,
                        "contents": [int(value)]
                    })
                #     if value != 0:
                #         end_idx = idx
                # if end_idx != 0:
                #     initial_memory.append({
                #         "address": int(mem.address),
                #         "contents": [int(x) for x in mem.contents[:end_idx]]
                #     })

        with open(f"code-testvector-{datetime.now().strftime('%H-%M-%S')}.json", 'w') as fp:
            tt = {
                "name": "gas_basic_consume_all",
                "initial-regs": self._pvm.program.registers,
                "initial-pc": int(self._pvm._initial_pc),
                "initial-page-map": initial_page_map,
                "initial-memory": initial_memory,
                "initial-gas": int(self._pvm._initial_gas),
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
                "expected-pc": 1,#TODO
                "expected-memory": [],#TODO
                "expected-gas": 0#TODO
            }
            json.dump(tt, fp)


    def hc_regs(self, msg: str, phase: str) -> None:
        #TODO: set phase from pvm invoke, hardcoded accumulate for now
        msg = f"{self._pvm_id}_{phase}: {msg}"
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        logging.debug(
            f"{msg}\n{reg_msg}"
        )

    def hc_debug(self, log_lvl: int, log_lvl_name: str, core_idx: int, service_id: int, target_msg: str, message: str) -> None:
        logging.log(log_lvl, f"{log_lvl_name}@{core_idx}#{service_id} {target_msg} {message}")

    def pvm_hash(self):
        bytez = bytes()
        for x in range(len(self._pvm.reg)):
            bytez += int(self._pvm.reg[x]).to_bytes(length=8, byteorder="little")

        bytez += int(self._pvm.gas).to_bytes(length=8, byteorder="little")

        rom = self._pvm.mem._rom
        heap = self._pvm.mem._heap
        stack = self._pvm.mem._stack
        arguments = self._pvm.mem._args
        mem_segments = [m for m in (rom, heap, stack, arguments) if m]
        for seg in mem_segments:
            if seg.tail > 0:
                page_begin_addr = seg.address
                page_end_addr = seg.paged_tail
                nr_pages = (page_end_addr-page_begin_addr) // 4096 + 1
                for xx in range(nr_pages):
                    bytez += int(seg.address // 4096).to_bytes(length=4, byteorder="little")
                    offset = xx*4096
                    bytez += bytes(seg.contents[offset:offset+4096])

        return blake2b_256_hash(bytez)

    def pvm_counters(self):
        logging.debug(f"GAS: {self._pvm.gas} PC: {self._pvm.pc}")

    def pvm_header(self):
        logging.debug(
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

    def pvm_regs(self, msg):
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        logging.debug(f"{msg} {reg_msg}")

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        ctx = {"reg": self._pvm.get_registers()}
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

        logging.debug(
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


    def hc_log(self, msg, data):
        pass
