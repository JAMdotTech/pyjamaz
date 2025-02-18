import json
import os
import unittest

from os import path
from pickletools import read_int4

import numpy as np

from jamcodec.base import JamBytes
from jamcodec.types import BitArray
from parameterized import parameterized

from pyjamaz.pvm import PVM
from pyjamaz.pvm.constants import ExitCondition, OpcodeNames
from pyjamaz.pvm.types import PVMProgram
from pyjamaz.pvm.utils import read_uint


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

log_ctx = {}
#
# def setUpModule():
#     for opcode_name in OpcodeNames.values():
#         log_ctx[opcode_name] = 0
#
# def tearDownModule():
#     print(">>> tearDownModule() called once after all tests in this module <<<")


class TestPolkaVMInstructions(unittest.TestCase):

    @parameterized.expand(load_test_vectors('fixtures/pvm/programs'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/riscv'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/programs/inst_load_imm_and_jump_indirect_different_regs_with_offset_ok.json'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/programs/inst_load_imm_and_jump_indirect_different_regs_without_offset_ok.json'))
    def test_instruction(self, name, test_vector):

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')

        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        global log_ctx

        read_uint([9, 3, 0], 0, 3)

        bitmask_bytes = BitArray(23).encode([True, False, False, True, False, False, True, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False])
        bitmask_values = BitArray(23).decode(bitmask_bytes)

        #pvm_data.opcode_bitmask[8] = False
        pvm = PVM(log_ctx)
        #if pvm._log: print(f"RUN {test_vector['name']}")
        pvm.invoke(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"]
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
                page = pvm.find_page(expected_mem["address"])
                mem_offset = expected_mem["address"] - page.offset
                mem_len = len(expected_mem["contents"])
                pvm_mem = page.memory.tolist()[mem_offset:mem_offset + mem_len]
                self.assertEqual(
                    expected_mem["contents"],
                    pvm_mem,
                    f"{name}:\n Expected mem: {expected_mem["contents"]}, but got: {pvm_mem}"
                )


if __name__ == '__main__':
    unittest.main()
