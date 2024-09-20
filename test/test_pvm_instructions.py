import json
import os
import unittest

from os import path

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm import PVM
from pyjamaz.pvm.types import PVMProgram


def load_test_vectors(directory):
    directory = path.join(path.dirname(path.abspath(__file__)), directory)
    test_vectors = []
    if directory.endswith('.json'):
        #filename = "inst_jump.json"
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

        mem_size = 0
        if test_vector["expected-memory"]:
            mem_size = len(test_vector["expected-memory"][0]["contents"])

        pvm_data = PVMProgram.from_jam_bytes(JamBytes(bytes(test_vector["program"])))
        #TODO: initialize mag naar instantiatie ==> gelijk ook de invoke
        pvm = PVM(pvm_data, mem_size=mem_size)
        pvm.initialize(
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
        )
        pvm.invoke()

        #self.assertEqual(test_vector["expected-status"], pvm.status, f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            self.assertEqual(test_vector["expected-memory"][0]["contents"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory'][0]['contents']}, but got: {pvm.mem.tolist()}")


if __name__ == '__main__':
    unittest.main()
