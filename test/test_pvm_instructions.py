import json
import os
import unittest

from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz import settings
from pyjamaz.pvm.types import PVMCode, PVMProgram
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.pvm import MemorySection, PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, MEM_W, MEM_R


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

    @parameterized.expand(load_test_vectors('fixtures/pvm/gas-cost/gas_xor_and_shift.json'))
    def test_instruction(self, name, test_vector):

        import logging

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        pvm_code = PVMCode.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        # Zeroed registers by default; the test steps may mutate them before running.
        pvm_regs = [0] * 13

        pvm_memory = PVMMemory(None, None, None, None)
        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program, settings.PVM_DEBUGGER)

        status_map = {
            ExitReason.resume.value: "none",
            ExitReason.panic.value: "panic",
            ExitReason.halt.value: "halt",
            ExitReason.page_fault.value: "page-fault",
            ExitReason.host_halt.value: "ecalli",
            ExitReason.out_of_gas.value: "out-of-gas",
        }

        current_pc = test_vector["initial-pc"]
        current_gas = test_vector["initial-gas"]

        for step in test_vector["steps"]:
            if "set-reg" in step:
                reg = step["set-reg"]["reg"]
                value = step["set-reg"]["value"]
                pvm.reg[reg] = value
            elif "map" in step:
                mapping = step["map"]
                section = MemorySection(
                    address=mapping["address"],
                    size=mapping["length"],
                    contents=[0] * mapping["length"],
                    acl=MEM_W if mapping["is-writable"] else MEM_R
                )
                pvm_memory.map_section(section)
            elif "write" in step:
                write = step["write"]
                section = pvm_memory.find_section(write["address"])
                if not section:
                    raise ValueError(f"Memory section not found for address {write['address']}")
                offset = write["address"] - section.address
                if offset + len(write["contents"]) > len(section.contents):
                    raise ValueError(f"Write too large for mapped section at {write['address']}")
                for idx, byt in enumerate(write["contents"]):
                    section.contents[offset + idx] = np.uint8(byt)
            elif "run" in step:
                pvm.invoke(current_pc, current_gas)
                current_pc = pvm.pc
                current_gas = pvm.gas
            elif "assert" in step:
                expected = step["assert"]
                self.assertIn(pvm.status, status_map, f"{name}:\n Unknown status {pvm.status}")
                self.assertEqual(expected["status"], status_map[pvm.status], f"{name}:\n Expected status: {expected['status']}, but got: {pvm.status}")
                self.assertEqual(expected["gas"], pvm.gas, f"{name}:\n Expected gas: {expected['gas']}, but got: {pvm.gas}")
                self.assertEqual(expected["pc"], pvm.pc, f"{name}:\n Expected PC: {expected['pc']}, but got: {pvm.pc}")
                self.assertEqual(expected["regs"], list(pvm.reg), f"{name}:\n Expected registers: {expected['regs']}, but got: {pvm.reg}")

                if "memory" in expected and expected["memory"]:
                    for expected_mem in expected["memory"]:
                        section = pvm_memory.find_section(expected_mem["address"])
                        mem_offset = expected_mem["address"] - section.address
                        mem_len = len(expected_mem["contents"])
                        pvm_mem = list(section.contents[mem_offset:mem_offset + mem_len])
                        self.assertEqual(
                            expected_mem["contents"],
                            pvm_mem,
                            f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {pvm_mem}"
                        )

                if "page-fault-address" in expected:
                    self.assertEqual(expected["page-fault-address"], pvm.exit_value, f"{name}:\n Expected page fault address: {expected['page-fault-address']}, but got: {pvm.exit_value}")

                if "hostcall" in expected:
                    self.assertEqual(expected["hostcall"], pvm.exit_value, f"{name}:\n Expected hostcall value: {expected['hostcall']}, but got: {pvm.exit_value}")

        # Validate block gas costs when provided by the test vector.
        if "block-gas-costs" in test_vector:
            block_gas = {int(k): v for k, v in pvm.basic_block_gas.items()}
            for block in test_vector["block-gas-costs"]:
                blk_pc = block["pc"]
                expected_cost = block["cost"]
                self.assertIn(blk_pc, block_gas, f"{name}:\n Missing block {blk_pc} in basic block gas costs")
                self.assertEqual(expected_cost, block_gas[blk_pc], f"{name}:\n Expected block gas costs: {test_vector['block-gas-costs']}, but got: {block_gas}")

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
