"""
Ahead of Time compiled version of the JIT interpreter
"""

import numpy as np

from numba import types
from numba.typed import Dict, List

from .interpreter_numba_aot_ffi import invoke_native
from .types import PVMProgram
from ..rpython.interpreter_rpython import PVMInterpreter as PVMInterpreterBase

from ..constants import (
    ExitReason, OpcodeScheme, OpcodeNames,
)


# Error codes for the JIT function
ERROR_NONE = 0
ERROR_PANIC_TRAP = 1
ERROR_PANIC_INVALID_PC = 2
ERROR_PANIC_INVALID_BRANCH = 3
ERROR_PANIC_INVALID_DJUMP = 4
ERROR_INVALID_OPCODE = 5
ERROR_MEMORY_FAULT = 6

# Memory permissions (match PVMMemoryMode enum values)
MEM_INACCESSIBLE = 0
MEM_READABLE = 1
MEM_WRITABLE = 2

# Page size constant
PVM_PAGE_SIZE = 4096
PVM_PAGE_SHIFT = 12  # 4096 = 2^12

# Exit reasons (matching ExitReason enum)
EXIT_RESUME = 0  # GP:     ▸: continue PVM
EXIT_HALT = 1  # GP-A.2: ∎: regular halt: halt
EXIT_PANIC = 2  # GP-A.2: ☇: unexpected program termination: panic
OUT_OF_GAS = 3  # GP-A.2: ∞: out-of-gas
EXIT_PAGE_FAULT = 4  # GP-A.2: F: page-fault
EXIT_HOST_HALT = 5  # GP-A.2: h: host-call

U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64

# state_out constants for invoke_jit (int64 array)
STATE_STATUS = 0
STATE_PC = 1
STATE_GAS = 2
STATE_INST_NR = 3
STATE_EXIT_VALUE = 4
STATE_SKIP_LEN = 5
STATE_ERROR = 6



class PVMInterpreter(PVMInterpreterBase):
    """
    Pure JIT-optimized PVM interpreter using Numba compilation only.
    No fallback to Python interpreter.
    """

    def __init__(self, program: PVMProgram, logger=None):
        """Initialize the interpreter with a program."""
        super().__init__(program, logger)
        self._prepare_jit_data()

    def _prepare_jit_data(self):
        """Prepare data structures for JIT compilation."""
        # Convert dictionaries to arrays for JIT access
        if self.inst_pos:
            self.inst_pos_keys = np.array(list(self.inst_pos.keys()), dtype=np.int32)
            self.inst_pos_vals = np.array(list(self.inst_pos.values()), dtype=np.int32)
        else:
            # Empty arrays if no instructions
            self.inst_pos_keys = np.array([], dtype=np.int32)
            self.inst_pos_vals = np.array([], dtype=np.int32)
        self.inst_arg_len_array = np.array(self.inst_arg_len if self.inst_arg_len else [], dtype=np.int32)

        # Build opcode scheme array - use 255 as invalid
        self.opcode_scheme_array = np.full(256, 255, dtype=np.int32)
        for opcode, scheme in OpcodeScheme.items():
            self.opcode_scheme_array[opcode] = scheme.value

        # Dense PC -> inst_index lookup for O(1) fetch in JIT
        if self.inst_pos_keys.size > 0:
            max_pc = int(max(self.inst_pos_keys))
            size = max_pc + 1
        else:
            size = int(self.code_size) if hasattr(self, 'code_size') else 0
        self.pc_to_inst_index = np.full(size, -1, dtype=np.int32)
        for k, v in zip(self.inst_pos_keys, self.inst_pos_vals):
            idx = int(k)
            if 0 <= idx < size:
                self.pc_to_inst_index[idx] = int(v)

    def _prepare_memory_for_jit(self):
        """
        Build JIT-ready section references
        Returns: section_starts, section_ends, section_arrays, acl_dict
        """
        if not self.mem_sections:
            empty_acl = Dict.empty(key_type=types.int64, value_type=types.int64)
            return (np.array([], dtype=np.uint64),
                    np.array([], dtype=np.uint64),
                    List.empty_list(types.uint8[::1]),
                    empty_acl)

        starts = []
        ends = []
        arrays = List.empty_list(types.uint8[::1])

        acl_dict = Dict.empty(key_type=types.uint32, value_type=types.int32)
        if self.mem_acl is not None:
            for page_nr, permission in self.mem_acl.items():
                acl_dict[np.uint32(page_nr)] = np.int32(permission)

        for i, section in enumerate(self.mem_sections):
            if section is not None:
                start_addr = self.mem_section_starts[i]
                end_addr = self.mem_section_ends[i]
                buf = section

                # Ensure C-contiguous
                if not buf.flags.c_contiguous:
                    buf = np.ascontiguousarray(buf)

                # Ensure uint8 1-D view for zero-copy
                # if buf.dtype == np.uint8:
                #     b8 = buf  # zero-copy
                # else:
                #     # Zero-copy view when possible
                #     b8 = buf.view(np.uint8).reshape(-1)
                #     if not b8.flags.c_contiguous:
                #         b8 = np.ascontiguousarray(b8)  # fallback copy

                starts.append(np.uint64(start_addr))
                ends.append(np.uint64(end_addr))
                arrays.append(buf)

        section_starts = np.asarray(starts, dtype=np.uint64)
        section_ends = np.asarray(ends, dtype=np.uint64)
        return section_starts, section_ends, arrays, acl_dict

    def invoke(self, pc: int, gas: int):
        """
        Pure JIT invoke that uses only Numba compilation.
        No fallback to Python interpreter.
        """
        self.pc = pc
        self.gas = gas

        jump_table_array = np.array(self.jump_table, dtype=np.int32)

        # Prepare memory arrays for JIT
        mem_section_starts, mem_section_ends, section_arrays, acl_dict = self._prepare_memory_for_jit()

        # Prepare heap info (for sbrk)
        heap_info = np.array([
            self.mem_section_ends[1] if len(self.mem_section_ends) > 1 else 0,  # current heap end
            self.mem_section_starts[2] if len(self.mem_section_starts) > 2 else 0xFFFFFFFF,  # next section start
            MEM_WRITABLE  # writable permission value
        ], dtype=np.uint64)

        registers_out = np.zeros(13, dtype=np.uint64)
        # state_out holds: [status, pc, gas, inst_nr, exit_value, skip_len, error_code]
        state_out = np.array([0, 0, 0, 0, 0, 0, 0], dtype=np.int64)
        heap_grew_out = np.array([0], dtype=np.int32)

        opcode_names = Dict.empty(
            key_type=types.int64,
            value_type=types.unicode_type,
        )
        if self.log:
            for _k, _v in OpcodeNames.items():
                opcode_names[int(_k)] = _v

        # Convert mem_ops arrays to int64 for JIT compatibility
        mem_ops_read_int64 = np.asarray(self.mem_ops_read, dtype=np.int64, order='C')
        mem_ops_write_int64 = np.asarray(self.mem_ops_write, dtype=np.int64, order='C')
        mem_ops_bytes_int64 = np.asarray(self.mem_ops_bytes, dtype=np.int64, order='C')

        # Call JIT-compiled function
        error_code = invoke_native(
            np.uint32(self.pc), np.int64(self.gas), np.uint32(self.inst_nr), np.uint32(int(self.skip_len)),
            self.code, np.uint32(self.code_size),
            self.inst_pos_keys, self.inst_pos_vals, self.inst_arg_len_array, self.pc_to_inst_index,
            self.opcode_scheme_array, jump_table_array,
            mem_ops_read_int64, mem_ops_write_int64, mem_ops_bytes_int64,
            mem_section_starts, mem_section_ends, section_arrays, acl_dict,
            heap_info,
            self.reg,
            opcode_names,
            # Outputs
            registers_out, state_out, heap_grew_out
        )

        # Update state from outputs
        old_pc = self.pc
        self.reg[:] = registers_out
        self.status = int(state_out[STATE_STATUS])
        pc_out_val = np.uint32(state_out[STATE_PC])
        self.exit_value = int(state_out[STATE_EXIT_VALUE])
        skip_len_out_val = int(state_out[STATE_SKIP_LEN])
        self.gas = int(state_out[STATE_GAS])
        self.inst_nr = np.uint32(state_out[STATE_INST_NR])
        # Advance PC only when there were no errors
        if error_code == ERROR_NONE:
            # Note: do not advance PC in case of a host-halt
            if self.status == ExitReason.host_halt.value:
                self.pc = pc_out_val
            else:
                self.pc = np.uint32(pc_out_val + skip_len_out_val)
        else:
            self.pc = pc_out_val
        self.skip_len = skip_len_out_val

        # Handle errors
        if error_code == ERROR_PANIC_TRAP:
            self.status = ExitReason.panic.value
        elif error_code == ERROR_PANIC_INVALID_PC:
            self.status = ExitReason.panic.value
        elif error_code == ERROR_PANIC_INVALID_DJUMP:
            self.status = ExitReason.panic.value
        elif error_code == ERROR_PANIC_INVALID_BRANCH:
            self.status = ExitReason.panic.value
        elif error_code == ERROR_INVALID_OPCODE:
            # No fallback - treat as panic
            self.status = ExitReason.panic.value
        elif error_code == ERROR_MEMORY_FAULT:
            self.status = ExitReason.page_fault.value
        elif error_code != ERROR_NONE:
            # Other errors cause panic
            self.status = ExitReason.panic.value

        # if self.status not in (ExitReason.resume.value, ExitReason.halt.value, ExitReason.host_halt.value):
        #     print(111111111)
        # Memory sections are automatically updated via zero-copy views

        # Update heap end pointer if it was modified by sbrk
        if len(self.mem_section_ends) > 1:
            self.mem_section_ends[1] = heap_info[0]

        # Sync grown heap back from JIT's typed list (preferred) or extend locally
        try:
            if heap_grew_out[0] == 1 and section_arrays is not None:
                # Reuse the same underlying buffer grown by the JIT (zero-copy)
                self.mem_sections[1] = np.asarray(section_arrays[1], dtype=np.uint8)
            elif self.mem_sections and self.mem_sections[1] is not None:
                current_len = len(self.mem_sections[1])
                desired_len = int(self.mem_section_ends[1] - self.mem_section_starts[1])
                if desired_len > current_len:
                    growth = desired_len - current_len
                    self.mem_sections[1] = np.concatenate((self.mem_sections[1], np.zeros(growth, dtype=np.uint8)))
        except Exception:
            # Non-fatal; logging parity may differ if extension fails
            pass

        # Sync ACL changes back to original dict
        if hasattr(self, 'mem_acl') and self.mem_acl is not None:
            # Update original ACL with any new entries from sbrk
            for page_nr in acl_dict:
                # Ensure page_nr is uint32 to avoid type warning
                page_nr_u32 = np.uint32(page_nr) if not isinstance(page_nr, np.uint32) else page_nr
                self.mem_acl[int(page_nr)] = int(acl_dict[page_nr_u32])

        self._sync_memory()
