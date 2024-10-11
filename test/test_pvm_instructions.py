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
    @parameterized.expand(load_test_vectors('fixtures/pvm/programs2/inst_load_u8.json'))
    def test_instruction(self, name, test_vector):

        # Set NumPy to ignore overflow warnings
        np.seterr(over='ignore')

        # TODO!!!!!!!!!!!!!!!!!!!!!!
        # voor fibonaci & store_u16 moet strict uit staan, de branch test gaat wel goed...: jamcodec.exceptions.ScaleDecodeException: Remaining bits not all 0
        # fixtures/pvm/programs-extra/u16_store.json:
        # strict moet false staan, expected gass klopt volgens mij ook niet????

        # TODO: we gaan nu altijd maar uit van 1 mem page
        mem_size = 0
        mem_offset = 0
        if test_vector["expected-memory"]:
            mem_size = len(test_vector["expected-memory"][0]["contents"])
            mem_offset = test_vector["expected-memory"][0]["address"]

        pvm_data = PVMProgram.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm = PVM(
            pvm_data,
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
            mem_size=mem_size,
            mem_offset=mem_offset
        )

        # Mapping specific for test vectors
        ExitConditionMap = {
            ExitCondition.none.value: "none",
            ExitCondition.panic.value: "trap",
            ExitCondition.halt.value: "halt"
        }

        self.assertEqual(test_vector["expected-status"], ExitConditionMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            self.assertEqual(test_vector["expected-memory"][0]["contents"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory'][0]['contents']}, but got: {pvm.mem.tolist()}")


if __name__ == '__main__':
    unittest.main()
