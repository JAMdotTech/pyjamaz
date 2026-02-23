import json
import os
import unittest

from os import path

from jamcodec.base import JamBytes
from parameterized import parameterized

from pyjamaz import settings
from pyjamaz.pvm.types import PVMCode, PVMProgram, PVMMemory
from pyjamaz.pvm import PVMInterpreter
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


def _build_segments(initial_page_map, initial_memory):
    segments = []
    for page_map in initial_page_map or []:
        segments.append({
            "address": page_map["address"],
            "length": page_map["length"],
            "acl": MEM_W if page_map["is-writable"] else MEM_R,
            "contents": bytearray(page_map["length"]),
        })

    for mem_block in initial_memory or []:
        addr = mem_block["address"]
        data = bytes(mem_block["contents"])
        if not data:
            continue

        remaining = len(data)
        cursor = 0
        while remaining > 0:
            segment = next(
                (seg for seg in segments if seg["address"] <= addr < seg["address"] + seg["length"]),
                None
            )
            if segment is None:
                raise ValueError(f"Initial memory block not covered by page map at address {addr}")
            seg_off = addr - segment["address"]
            chunk = min(segment["length"] - seg_off, remaining)
            if chunk <= 0:
                raise ValueError(f"Invalid page map for memory block at address {addr}")
            segment["contents"][seg_off:seg_off + chunk] = data[cursor:cursor + chunk]
            addr += chunk
            cursor += chunk
            remaining -= chunk

    return segments


class TestPolkaVMInstructions(unittest.TestCase):

    @parameterized.expand(load_test_vectors('fixtures/pvm/programs/'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/programs-custom'))
    def test_instruction(self, name, test_vector):

        pvm_code = PVMCode.from_jam_bytes(
            JamBytes(bytes(test_vector["program"]))
        )
        pvm_regs = test_vector["initial-regs"]

        segments = _build_segments(
            test_vector.get("initial-page-map", []),
            test_vector.get("initial-memory", []),
        )
        pvm_memory = PVMMemory()
        for segment in segments:
            pvm_memory.add_segment(
                segment["address"],
                segment["length"],
                segment["acl"],
                bytes(segment["contents"]),
            )

        heap_segments = [seg for seg in segments if seg["address"] >= 2 * 65536]
        if heap_segments:
            heap_seg = min(heap_segments, key=lambda seg: seg["address"])
            pvm_memory.heap_base = heap_seg["address"]
            pvm_memory.heap_ptr = heap_seg["address"] + heap_seg["length"]

        pvm_program = PVMProgram(pvm_code, pvm_regs, pvm_memory)
        pvm = PVMInterpreter(pvm_program, logger=settings.PVM_DEBUGGER)

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
        self.assertEqual(test_vector["expected-regs"], list(pvm.reg), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg}")
        self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        # self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        if test_vector["expected-memory"]:
            for expected_mem in test_vector["expected-memory"]:
                mem_len = len(expected_mem["contents"])
                pvm_mem = list(pvm_memory.read_bytes(expected_mem["address"], mem_len))
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
