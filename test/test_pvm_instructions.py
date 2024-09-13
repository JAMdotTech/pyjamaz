import json
import os
import unittest

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pvm import PVM
from pyjamaz.pvm.types import PVMProgram


def load_test_vectors(directory):
    test_vectors = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            with open(os.path.join(directory, filename)) as f:
                test_vector = json.load(f)
                test_vectors.append((filename, test_vector))

    filename = "inst_trap.json"
    #filename = "inst_store_u8_trap_read_only.json"
    #filename = "inst_load_u8.json"
    #filename = "inst_load_imm.json"
    #filename = "inst_add_imm.json"
    #filename = "inst_branch_eq_imm_ok.json"
    #filename = "inst_sub_imm.json"
    #filename = "inst_branch_less_unsigned_imm_nok.json"
    # with open(os.path.join(directory, filename)) as f:
    #     test_vector = json.load(f)
    #     test_vectors = [(filename, test_vector)]

    return test_vectors


class TestPolkaVMInstructions(unittest.TestCase):
    @parameterized.expand(load_test_vectors('./fixtures/pvm/programs2'))
    def test_instruction(self, name, test_vector):

        mem_size = 0
        if test_vector["expected-memory"]:
            mem_size = len(test_vector["expected-memory"][0]["contents"])

        pvm_data = PVMProgram.from_jam_bytes(JamBytes(bytes(test_vector["program"])))
        pvm = PVM(pvm_data, mem_size=mem_size)

        pvm.initialize(
            test_vector["initial-regs"],
            test_vector["initial-pc"],
            test_vector["initial-gas"],
            test_vector["initial-page-map"],
            test_vector["initial-memory"],
        )
        pvm.invoke()

        # Note: fix to get identical memory as test vectors (ignore empy bytes)
        #pvm.mem = pvm.mem[pvm.mem != 0].tolist()

        #self.assertEqual(test_vector["expected-status"], pvm.status, f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        self.assertEqual(test_vector["expected-regs"], pvm.reg.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg.tolist()}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            self.assertEqual(test_vector["expected-memory"][0]["contents"], pvm.mem.tolist(), f"{name}:\n Expected mem: {test_vector['expected-memory'][0]['contents']}, but got: {pvm.mem.tolist()}")


if __name__ == '__main__':
    unittest.main()
