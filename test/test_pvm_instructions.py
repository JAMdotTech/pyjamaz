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
from pyjamaz.pvm.constants import ExitReason, MEM_W, MEM_R, OpcodeScheme, Opcode
from pyjamaz.pvm.gas_model import GasModel
from pyjamaz.pvm.gas_model_logger import TimelineTracker

# Note: set to true to print timeline for mismatched blocks
DEBUG_GAS_MISMATCHES = True

# Set to a file path to log ALL block timelines (not just mismatches)
# Example: GAS_LOG_FILE = "gas_timelines.log"
GAS_LOG_FILE = None  # "blabla.md"


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
    #@parameterized.expand(load_test_vectors('fixtures/pvm/gas-cost/'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/integration-tests/'))
    #@parameterized.expand(load_test_vectors('fixtures/pvm/integration-tests/doom.json'))
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

        status_map = {
            ExitReason.resume.value: "none",
            ExitReason.panic.value: "panic",
            ExitReason.halt.value: "halt",
            ExitReason.page_fault.value: "page-fault",
            ExitReason.host_halt.value: "ecalli",
            ExitReason.out_of_gas.value: "out-of-gas",
        }

        # self.assertEqual(test_vector["expected-status"], ExitReasonMap[pvm.status], f"{name}:\n Expected status: {test_vector['expected-status']}, but got: {pvm.status}")
        # self.assertEqual(test_vector["expected-regs"], list(pvm.reg), f"{name}:\n Expected registers: {test_vector['expected-regs']}, but got: {pvm.reg}")
        # self.assertEqual(test_vector["expected-pc"], pvm.pc, f"{name}:\n Expected PC: {test_vector['expected-pc']}, but got: {pvm.pc}")
        # # self.assertEqual(test_vector["expected-gas"], pvm.gas, f"{name}:\n Expected gas: {test_vector['expected-gas']}, but got: {pvm.gas}")
        # if test_vector["expected-memory"]:
        #     for expected_mem in test_vector["expected-memory"]:
        #         mem_len = len(expected_mem["contents"])
        #         pvm_mem = list(pvm_memory.read_bytes(expected_mem["address"], mem_len))
        #         self.assertEqual(
        #             expected_mem["contents"],
        #             pvm_mem,
        #             f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {pvm_mem}"
        #         )

        # Integration tests (doom.json, etc.) only have program + block-gas-costs, no steps
        current_pc = test_vector.get("initial-pc", 0)
        current_gas = test_vector.get("initial-gas", 0)

        for step in test_vector.get("steps", []):
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
                    # for expected_mem in expected["memory"]:
                    #     section = pvm_memory.find_section(expected_mem["address"])
                    #     mem_offset = expected_mem["address"] - section.address
                    #     mem_len = len(expected_mem["contents"])
                    #     pvm_mem = list(section.contents[mem_offset:mem_offset + mem_len])
                    #     self.assertEqual(
                    #         expected_mem["contents"],
                    #         pvm_mem,
                    #         f"{name}:\n Expected mem: {expected_mem['contents']}, but got: {pvm_mem}"
                    #     )
                    for expected_mem in test_vector["expected-memory"]:
                        mem_len = len(expected_mem["contents"])
                        pvm_mem = list(pvm_memory.read_bytes(expected_mem["address"], mem_len))
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
            expected_costs = test_vector["block-gas-costs"]

            # Create gas model for timeline rendering (when DEBUG or LOG_FILE enabled)
            gas_model = None
            log_file_handle = None
            if DEBUG_GAS_MISMATCHES or GAS_LOG_FILE:
                gas_model = GasModel(
                    code=pvm.code,
                    inst_pos=pvm.inst_pos,
                    inst_arg_len=pvm.inst_arg_len,
                    opcode_scheme=OpcodeScheme,
                    opcode_enum=Opcode,
                )
                if GAS_LOG_FILE:
                    log_file_handle = open(GAS_LOG_FILE, 'a')
                    log_file_handle.write(f"\n{'='*80}\n")
                    log_file_handle.write(f"Test: {name}\n")
                    log_file_handle.write(f"{'='*80}\n\n")

            def log_block_timeline(blk_pc, expected_cost, actual_cost, is_mismatch=False):
                """Helper to log timeline to console and/or file."""
                tracker = TimelineTracker()
                gas_model.compute_block_gas_cost(blk_pc, timeline_tracker=tracker)
                timeline = tracker.get_timeline(blk_pc)

                status = "MISMATCH" if is_mismatch else "OK"
                header = f"Block PC {blk_pc}: expected {expected_cost}, got {actual_cost} [{status}]"
                body = (
                    f"Total cycles: {timeline.total_cycles}, Gas cost: {timeline.gas_cost}\n"
                    f"Timeline ({len(timeline.instructions)} instructions):\n"
                    f"{tracker.render_timeline(timeline, gas_model)}\n"
                )

                # Print to console only on mismatch
                if is_mismatch and DEBUG_GAS_MISMATCHES:
                    print(f"\n{'='*80}")
                    print(f"GAS {header}")
                    print(f"{'='*80}")
                    print(body)

                # Log to file always (if enabled)
                if log_file_handle:
                    log_file_handle.write(f"{header}\n{'-'*40}\n{body}\n")

            try:
                # Handle both formats: dict {"pc": cost} or array [{"pc": ..., "cost": ...}]
                if isinstance(expected_costs, dict):
                    # Integration test format: {"0": 26, "27": 15, ...}
                    for pc_str, expected_cost in expected_costs.items():
                        blk_pc = int(pc_str)
                        self.assertIn(blk_pc, block_gas, f"{name}:\n Missing block {blk_pc} in basic block gas costs")
                        actual_cost = block_gas[blk_pc]
                        is_mismatch = expected_cost != actual_cost
                        if gas_model and (is_mismatch or GAS_LOG_FILE):
                            log_block_timeline(blk_pc, expected_cost, actual_cost, is_mismatch)
                        self.assertEqual(expected_cost, actual_cost, f"{name}:\n Block {blk_pc}: expected {expected_cost}, got {actual_cost}")
                else:
                    # Standard test format: [{"pc": 0, "cost": 26}, ...]
                    for block in expected_costs:
                        blk_pc = block["pc"]
                        expected_cost = block["cost"]
                        self.assertIn(blk_pc, block_gas, f"{name}:\n Missing block {blk_pc} in basic block gas costs")
                        actual_cost = block_gas[blk_pc]
                        is_mismatch = expected_cost != actual_cost
                        if gas_model and (is_mismatch or GAS_LOG_FILE):
                            log_block_timeline(blk_pc, expected_cost, actual_cost, is_mismatch)
                        self.assertEqual(expected_cost, actual_cost, f"{name}:\n Block {blk_pc}: expected {expected_cost}, got {actual_cost}")
            finally:
                if log_file_handle:
                    log_file_handle.close()

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
