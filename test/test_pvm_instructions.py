import json
import os
import unittest

from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants_new import ExitReason, OpcodeNames
from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm.types_new import PVMCode, PVMProgram, PVMMemory, MemorySection, PVMMemoryMode


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

    @parameterized.expand(load_test_vectors('fixtures/pvm/programs'))
    def test_instruction(self, name, test_vector):

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')

        pvm_code = PVMCode.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm_regs = test_vector["initial-regs"]

        mem_rom = None
        mem_heap = None
        mem_pages = []
        if test_vector["initial-page-map"]:
            for page_map in test_vector["initial-page-map"]:
                page = MemorySection(
                    address=page_map["address"],
                    length=page_map["length"],
                    acl=PVMMemoryMode.writable if page_map["is-writable"] else PVMMemoryMode.readable,
                    contents=[0] * page_map["length"]
                )
                if page_map["address"] < 2*65536:
                    mem_rom = page
                else:
                    mem_heap = page

                """
                 ROM:       2**16 65536  
                 HEAP:      2*65536+len(rom) 196608
                 STACK: 
                 ARGUMENTS: 
                """

                mem_pages.append(page)

        if len(mem_pages) > 3:
            raise Exception("TODO: implement heap & stack for testvectors?")

        pvm_memory = PVMMemory(mem_rom, mem_heap, None, None)

        if test_vector["initial-memory"]:
            for mem_block in test_vector["initial-memory"]:
                page = pvm_memory.find_section(mem_block["address"])
                mem = page.contents

                if len(mem_block["contents"]) > len(mem):
                    raise ValueError(f"TOO BIG TO FIT IN HERE :D")
                offset = mem_block["address"] - page.address
                for idx, byt in enumerate(mem_block["contents"]):
                    mem[offset + idx] = np.uint8(byt)

        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program)
        #pvm = PVMInterpreter(pvm_program, logger_cls=PVMDebugLog)#, log_ctx=log_ctx) # Note: uncomment to enable debug logging
        pvm.invoke(
            test_vector["initial-pc"],
            test_vector["initial-gas"]
        )

        # Mapping specific for test vectors
        ExitReasonMap = {
            ExitReason.resume.value: "none",
            ExitReason.panic.value: "panic",
            ExitReason.halt.value: "halt",
            ExitReason.page_fault.value: "page-fault",
        }

        self.assertEqual(test_vector["expected-status"], ExitReasonMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        # self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            for expected_mem in test_vector["expected-memory"]:
                page = pvm_memory.find_section(expected_mem["address"])
                mem_offset = expected_mem["address"] - page.address
                mem_len = len(expected_mem["contents"])
                pvm_mem = page.contents.tolist()[mem_offset:mem_offset + mem_len]
                self.assertEqual(
                    expected_mem["contents"],
                    pvm_mem,
                    f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {pvm_mem}"
                )

# print some stats collected from logger
# def tearDownModule():
#     global log_ctx
#     # Note: only show debug log when enabled
#     if log_ctx["_pvm"]:
#         log_ctx["_pvm"].log_state()
#         if log_ctx["log_opcode_calls"]:
#             print("Opcodes:")
#             opcodes = log_ctx["log_dict"]
#             if not log_ctx["log_opcode_calls_if_zero"]:
#                 opcodes = {x:y for x,y in opcodes.items() if y > 0}
#             print(opcodes)

if __name__ == '__main__':
    unittest.main()
