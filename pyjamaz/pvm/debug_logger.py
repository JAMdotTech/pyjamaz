import logging
from datetime import datetime

import numpy as np

from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.invocation import PVMLogger



def _fmix64(x: np.uint64) -> np.uint64:
    """Finalization mix (from MurmurHash3)"""
    x ^= x >> np.uint64(33)
    x *= np.uint64(0xff51afd7ed558ccd)
    x ^= x >> np.uint64(33)
    x *= np.uint64(0xc4ceb9fe1a85ec53)
    x ^= x >> np.uint64(33)
    return x


def hash_memory_segment(section_array) -> np.uint64:
    """
    Hash a memory segment with FNV-1a 64-bit, then fmix.
    section_array: uint8[::1] NumPy array (1-D, C-contiguous).
    """
    n = len(section_array)
    if n == 0:
        return np.uint64(0)

    h = np.uint64(1469598103934665603)        # FNV-1a offset basis (64-bit)
    prime = np.uint64(1099511628211)          # FNV-1a prime (64-bit)

    # Process all bytes (rely on 64-bit wraparound; no modulo)
    for i in range(n):
        h ^= np.uint64(section_array[i])
        h *= prime

    return _fmix64(h)


class PVMDebugLog(PVMLogger):

    def __init__(self, pvm, log_opcode_calls=True, log_opcode_calls_if_zero=False):
        np.seterr(over='ignore')
        self._pvm = pvm
        self._pvm_id = self._pvm.name
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
        # logging.debug(
        #     f"PC      "
        #     f"INST                  "
        #     f"R1  "
        #     f"R2  "
        #     f"R3  "
        #     f"IMM1                    "
        #     f"IMM2                    "
        #     f"OFF1                    "
        #     f"OFF2                    "
        #     "CTX")
        pass

    def pvm_regs(self, msg):
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        logging.debug(f"{msg} {reg_msg}")

    def sbrk(self, cur_size, new_size, growth, alloc_mem):
        print(f"SBRK GROWN FROM {cur_size} TO {new_size} (growth {growth}, alloc mem: {alloc_mem})")

    def acl(self, cur_size, new_size, growth):
        print(f"ACL GROWN FROM {cur_size} TO {new_size} (growth: {growth})")

    def exc(self, exc_str):
        print(f"PVM EXCEPTION:\n{exc_str}")

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        return

        mem_info = ""
        # if hasattr(self._pvm, "mem_sections"):
        #     mem = self._pvm.mem_sections
        #     if mem is not None and len(mem) >= 2 and mem[1] is not None:
        #         heap_hash = hash_memory_segment(mem[1])
        #         mem_info += f"heap_hash:{heap_hash}"
        #     if mem is not None and len(mem) >= 3 and mem[2] is not None:
        #         stack_hash = hash_memory_segment(mem[2])
        #         mem_info += f" stack_hash:{stack_hash}"
        # elif hasattr(self._pvm, "mem"):
        #     mem = [x for x in [self._pvm.mem._rom, self._pvm.mem._heap, self._pvm.mem._stack, self._pvm.mem._args] if x]
        #     if mem is not None and len(mem) >= 2:
        #         heap_hash = hash_memory_segment(mem[1].contents)
        #         mem_info += f"heap_hash:{heap_hash}"
        #     if mem is not None and len(mem) >= 3:
        #         stack_hash = hash_memory_segment(mem[2].contents)
        #         mem_info += f" stack_hash:{stack_hash}"

        # print("inst=", self._pvm.inst_nr, "op=", OpcodeNames[self._pvm.opcode], "pc=", self._pvm.pc, "gas=", self._pvm.gas,
        #       "r1=", reg1, "r2=", reg2, "r3=", reg3,
        #       "imm1=", imm1, "imm2=", imm2, "off1=", off1, "off2=", off2, context, mem_info)

        name_str = OpcodeNames[self._pvm.opcode]
        name_pad = 22 - len(name_str)
        if name_pad > 0:
            name_str = name_str + (" " * name_pad)

        regs = [int(x) for x in self._pvm.get_registers()]
        regs_str = ""
        for i in range(len(regs)):
            s = str(regs[i])
            pad = 21 - len(s)
            if pad > 0:
                regs_str += (" " * pad) + s
            else:
                regs_str += s
            if i != len(regs) - 1:
                regs_str += " "

        # Fixed width for inst_nr and pc (4 chars each, right-aligned)
        inst_str = str(self._pvm.inst_nr)
        if len(inst_str) < 4:
            inst_str = (" " * (4 - len(inst_str))) + inst_str

        pc_str = str(self._pvm.pc)
        if len(pc_str) < 4:
            pc_str = (" " * (4 - len(pc_str))) + pc_str

        # tnow = time.time()
        # dt_ms = (tnow - self._pvm.op_time)
        # print(inst_str + " " + pc_str + " " + name_str + "" + str(dt_ms))

        #print(inst_str, pc_str, name_str, self._pvm.gas, regs_str, mem_info)
        tt = " ".join([inst_str, pc_str, name_str, self._pvm.gas, regs_str, mem_info])
        logging.debug(tt)


    def hc_log(self, msg, data):
        msg = f"{self._pvm_id}: {msg}"
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{data}"
        )
