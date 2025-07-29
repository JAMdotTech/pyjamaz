import json
import os
import unittest

from os import path

import numpy as np

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz.pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory, MemorySection, PVMMemoryMode, PVMLogger
from pyjamaz.pyjamaz.pvm_interface.hostcalls.general import hc_read, hc_write



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


class TestHCGeneral(unittest.TestCase):

    @parameterized.expand(load_test_vectors('fixtures/hostcalls/general'))
    def test_instruction(self, name, test_vector):

        # Set NumPy to ignore overflow warnings
        # np.seterr(over='ignore')
        # pvm_code = PVMCode.from_jam_bytes(
        #     JamBytes(bytes(test_vector["program"]))
        # )
        pvm_regs = test_vector["registers"]

        mem_rom = None
        mem_heap = None
        mem_pages = []
        for page_map in test_vector["page-map"]:
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

            mem_pages.append(page)

        pvm_memory = PVMMemory(mem_rom, mem_heap, None, None)

        for mem_block in test_vector["initial-memory"]:
            page = pvm_memory.find_section(mem_block["address"])
            mem = page.contents

            if len(mem_block["contents"]) > len(mem):
                raise ValueError(f"TOO BIG TO FIT IN HERE :D")
            offset = mem_block["address"] - page.address
            for idx, byt in enumerate(mem_block["contents"]):
                mem[offset + idx] = np.uint8(byt)


        invocation_output = TODO
        service_id = TODO
        service = TODO
        services = TODO

        hostcall = test_vector["hostcall"]
        logger = PVMLogger()

        if hostcall == "hc_read":
            hc_read(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)
        elif hostcall == "hc_write":
            hc_write(
                pvm_regs,
                pvm_memory,
                service,
                service_id,
                services,
                invocation_output,
                logger)

        self.assertEqual(test_vector["expected-regs"], invocation_output.registers.tolist(), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {invocation_output.registers.tolist()}")
        for expected_mem in test_vector["expected-memory"]:
            page = invocation_output.memory.find_section(expected_mem["address"])
            mem_offset = expected_mem["address"] - page.address
            mem_len = len(expected_mem["contents"])
            hc_mem = page.contents.tolist()[mem_offset:mem_offset + mem_len]
            self.assertEqual(
                expected_mem["contents"],
                hc_mem,
                f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {hc_mem}"
            )


if __name__ == '__main__':
    unittest.main()
