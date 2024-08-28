import json
import os
import unittest

from parameterized import parameterized

from pyjamaz.pvm import PVM
from pyjamaz.pvm.types import PVMProgram
from pyjamaz.serialization import JamBytes


def load_test_vectors(directory):
    test_vectors = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            with open(os.path.join(directory, filename)) as f:
                test_vector = json.load(f)
                test_vectors.append((filename, test_vector))
    return test_vectors


class TestPolkaVMInstructions(unittest.TestCase):
    @parameterized.expand(load_test_vectors('./fixtures/pvm/programs2'))
    def test_instruction(self, name, test_vector):

        pvm_data = PVMProgram.from_scale_bytes(JamBytes(bytes(test_vector["program"])))
        pvm = PVM(pvm_data)
        pvm.initialize(
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
        )
        pvm.invoke()

        self.assertEqual(pvm.status, test_vector["expected-status"], f"Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(pvm.reg.tolist(), test_vector["expected-regs"], f"Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(pvm.pc, test_vector["expected-pc"], f"Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(pvm.gas, test_vector["expected-gas"], f"Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")


if __name__ == '__main__':
    unittest.main()
