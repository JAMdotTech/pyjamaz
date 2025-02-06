import json
import os
import unittest

from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm import PVM
from pyjamaz.pvm.constants import ExitCondition
from pyjamaz.pvm.types import PVMProgram


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

        TODO: PRINT ELKE REGEL DIE WE AFLOPEN ZODAT IK KAN VERGELIJKEN MET FLUFFY!!!!!

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')

        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM()
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
