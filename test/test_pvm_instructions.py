import json
import os
import unittest

from parameterized import parameterized

from pvm import PVM


def load_test_vectors(directory):
    test_vectors = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            with open(os.path.join(directory, filename)) as f:
                test_vector = json.load(f)
                test_vectors.append((filename, test_vector))
    return test_vectors


class TestPolkaVMInstructions(unittest.TestCase):
    @parameterized.expand(load_test_vectors('./fixtures/pvm/programs'))
    def test_instruction(self, name, test_vector):

        pvm = PVM()
        pvm.initialize(
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
        )
        pvm.run(test_vector["program"])

        self.assertEqual(pvm.status, test_vector["expected-status"], f"Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(pvm.regs, test_vector["expected-regs"], f"Expected registers: {test_vector['expected-regs']}, but got: {pvm.regs}")
        self.assertEqual(pvm.pc, test_vector["expected-pc"], f"Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(pvm.gas, test_vector["expected-gas"], f"Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")


if __name__ == '__main__':
    unittest.main()
