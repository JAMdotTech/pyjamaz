import json
import os
import unittest

from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitCondition, OpcodeNames
from pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory, MemoryPage


def load_test_vectors(directory):
    directory = path.join(path.dirname(path.abspath(__file__)), directory)
    test_vectors = []
    if directory.endswith('.json'):
        with open(directory) as f:
            test_vector = json.load(f)
            test_vectors = [(directory, test_vector)]
    else:
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                with open(os.path.join(directory, filename)) as f:
                    test_vector = json.load(f)
                    test_vectors.append((filename, test_vector))

    return test_vectors


class TestPolkaVMInstructions(unittest.TestCase):

    #@parameterized.expand(load_test_vectors('fixtures/pvm/programs'))
    @parameterized.expand(load_test_vectors('fixtures/pvm/programs/inst_add_32.json'))
    def test_instruction(self, name, test_vector):

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')

        pvm_code = PVMCode.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm_regs = test_vector["initial-regs"]

        mem_pages = []
        if test_vector["initial-page-map"]:
            for page_map in test_vector["initial-page-map"]:
                page = MemoryPage(
                    address=page_map["address"],
                    length=page_map["length"],
                    writable=page_map["is-writable"],
                    contents=None
                )
                mem_pages.append(page)

        pvm_memory = PVMMemory(mem_pages)

        if test_vector["initial-memory"]:
            for mem_block in test_vector["initial-memory"]:
                page = pvm_memory.find_page(mem_block["address"])
                mem = page.contents
                if len(mem_block["contents"]) > len(mem):
                    raise ValueError(f"TOO BIG TO FIT IN HERE :D")
                offset = mem_block["address"] - page.address
                for idx, byt in enumerate(mem_block["contents"]):
                    mem[offset + idx] = np.uint8(byt)

        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program, log_ctx=log_ctx)
        pvm.invoke(
            test_vector["initial-pc"],
            test_vector["initial-gas"]
        )

        # Mapping specific for test vectors
        ExitConditionMap = {
            ExitCondition.none.value: "none",
            ExitCondition.panic.value: "panic",
            ExitCondition.halt.value: "halt",
            ExitCondition.page_fault.value: "page-fault",
        }

        self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            for expected_mem in test_vector["expected-memory"]:
                page = pvm_memory.find_page(expected_mem["address"])
                mem_offset = expected_mem["address"] - page.address
                mem_len = len(expected_mem["contents"])
                pvm_mem = page.contents.tolist()[mem_offset:mem_offset + mem_len]
                self.assertEqual(
                    expected_mem["contents"],
                    pvm_mem,
                    f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {pvm_mem}"
                )


def log_print_header(self):
    print(
        f"GAS: {self.gas}\n"
        f"PC: {self.pc}\n"
    )

    print(
        f"PC  "
        f"INST                  "
        f"R1  "
        f"R2  "
        f"R3  "
        f"IMM1                    "
        f"IMM2                    "
        f"OFF1                    "
        f"OFF2                    "
        "CTX")


def log_print(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
    ctx = {"reg": [int(x) for x in self.reg]}
    if context: ctx = ctx | context

    reg1 = reg1 or ''
    reg2 = reg2 or ''
    reg3 = reg3 or ''
    imm1 = imm1 or ''
    imm2 = imm2 or ''
    off1 = off1 or ''
    off2 = off2 or ''

    opn = OpcodeNames[self.opcode]
    r1 = " " * (4-len(str(self.pc)))
    r2 = " " * (22-len(opn))
    r3 = " " * (4-len(str(reg1)))
    r33 = " " * (3-len(str(reg1)))
    r4 = " " * (4-len(str(reg2)))
    r44 = " " * (3-len(str(reg2)))
    r5 = " " * (4-len(str(reg3)))
    r55 = " " * (3-len(str(reg3)))
    r6 = " " * (24-len(str(imm1)))
    r7 = " " * (24-len(str(imm2)))
    r8 = " " * (24-len(str(off1)))
    r9 = " " * (24-len(str(off2)))

    if opn not in self._log_dict:
        raise Exception(f"Unknown opcode {opn}")
    else:
        self._log_dict[opn] += 1

    print(
        f"{self.pc}{r1}"
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


log_ctx = {
     "log_init": log_print_header,
     "log_func": log_print,
     "log_dict": {},
}


for opcode_name in OpcodeNames.values():
    log_ctx[opcode_name] = 0


# print some stats collected from logger
def tearDownModule():
    global log_ctx
    print(log_ctx["log_dict"])


if __name__ == '__main__':
    unittest.main()
