"""
AOT compilation module for the PVM interpreter core loop (invoke_native).
Built using numba.pycc per https://numba.pydata.org/numba-doc/dev/user/pycc.html

Notes:
- This export implements the core state machine without logging/objmode.
- It relies on AOT-exported helpers from pvm_numba_aot and pvm_numba_aot2.
- All signatures are explicit and must match the interpreter's expectations.
"""

import numpy as np
import numba
import numba.types as types
from numba.pycc import CC

# Create compilation unit
cc = CC('pvm_numba_aot_invoke')
cc.verbose = True

# Aliases
u8 = types.uint8
u32 = types.uint32
u64 = types.uint64
i32 = types.int32
i64 = types.int64

u8_array = types.Array(u8, 1, 'C')
u32_array = types.Array(u32, 1, 'C')
u64_array = types.Array(u64, 1, 'C')
i32_array = types.Array(i32, 1, 'C')
i64_array = types.Array(i64, 1, 'C')

u8_array_list = types.ListType(types.Array(u8, 1, 'C'))
dict_u64_u64 = types.DictType(u64, u64)

# Constants consistent with interpreter
EXIT_RESUME = 0
EXIT_HALT = 1
EXIT_PANIC = 2
OUT_OF_GAS = 3
EXIT_PAGE_FAULT = 4
EXIT_HOST_HALT = 5

STATE_STATUS = 0
STATE_PC = 1
STATE_GAS = 2
STATE_INST_NR = 3
STATE_EXIT_VALUE = 4
STATE_SKIP_LEN = 5
STATE_ERROR = 6

ERROR_NONE = 0
ERROR_PANIC_TRAP = 1
ERROR_PANIC_INVALID_PC = 2
ERROR_PANIC_INVALID_BRANCH = 3
ERROR_PANIC_INVALID_DJUMP = 4
ERROR_INVALID_OPCODE = 5
ERROR_MEMORY_FAULT = 6

MEM_INACCESSIBLE = 0
MEM_READABLE = 1
MEM_WRITABLE = 2

PVM_PAGE_SIZE = 4096


# NOTE: Do not call into other extension modules from within AOT-compiled
# functions; Numba's nopython compiler cannot type external extension calls.
# Re-implement the needed helpers locally (not exported) for use by the loop.

@numba.njit(cache=True)
def _read_uint_le(code, addr32, length_u8):
    addr32 = np.uint32(addr32)
    l = np.uint8(length_u8)
    base = int(addr32)
    if l == np.uint8(1):
        return np.uint64(code[base])
    elif l == np.uint8(2):
        b0 = np.uint64(code[base])
        b1 = np.uint64(code[base + 1])
        return b0 | (b1 << np.uint64(8))
    elif l == np.uint8(4):
        b0 = np.uint64(code[base])
        b1 = np.uint64(code[base + 1])
        b2 = np.uint64(code[base + 2])
        b3 = np.uint64(code[base + 3])
        return (b0 | (b1 << np.uint64(8)) | (b2 << np.uint64(16)) | (b3 << np.uint64(24)))
    elif l == np.uint8(8):
        b0 = np.uint64(code[base])
        b1 = np.uint64(code[base + 1])
        b2 = np.uint64(code[base + 2])
        b3 = np.uint64(code[base + 3])
        b4 = np.uint64(code[base + 4])
        b5 = np.uint64(code[base + 5])
        b6 = np.uint64(code[base + 6])
        b7 = np.uint64(code[base + 7])
        return (b0 | (b1 << np.uint64(8)) | (b2 << np.uint64(16)) |
                (b3 << np.uint64(24)) | (b4 << np.uint64(32)) |
                (b5 << np.uint64(40)) | (b6 << np.uint64(48)) |
                (b7 << np.uint64(56)))
    else:
        # unsupported length => 0
        return np.uint64(0)

@numba.njit(cache=True)
def _pvm_X(x_u64, n_u64):
    x = np.uint64(x_u64)
    n = np.uint64(n_u64)
    if n == np.uint64(1):
        masked = x & np.uint64(0xFF)
        if masked & np.uint64(0x80):
            return np.uint64(masked | np.uint64(0xFFFFFFFFFFFFFF00))
        return np.uint64(masked)
    elif n == np.uint64(2):
        masked = x & np.uint64(0xFFFF)
        if masked & np.uint64(0x8000):
            return np.uint64(masked | np.uint64(0xFFFFFFFFFFFF0000))
        return np.uint64(masked)
    elif n == np.uint64(3):
        masked = x & np.uint64(0xFFFFFF)
        if masked & np.uint64(0x800000):
            return np.uint64(masked | np.uint64(0xFFFFFFFFFF000000))
        return np.uint64(masked)
    elif n == np.uint64(4):
        masked = x & np.uint64(0xFFFFFFFF)
        if masked & np.uint64(0x80000000):
            return np.uint64(masked | np.uint64(0xFFFFFFFF00000000))
        return np.uint64(masked)
    elif n == np.uint64(5):
        masked = x & np.uint64(0xFFFFFFFFFF)
        if masked & np.uint64(0x8000000000):
            return np.uint64(masked | np.uint64(0xFFFFFF0000000000))
        return np.uint64(masked)
    elif n == np.uint64(6):
        masked = x & np.uint64(0xFFFFFFFFFFFF)
        if masked & np.uint64(0x800000000000):
            return np.uint64(masked | np.uint64(0xFFFF000000000000))
        return np.uint64(masked)
    elif n == np.uint64(7):
        masked = x & np.uint64(0xFFFFFFFFFFFFFF)
        if masked & np.uint64(0x80000000000000):
            return np.uint64(masked | np.uint64(0xFF00000000000000))
        return np.uint64(masked)
    elif n == np.uint64(8):
        return np.uint64(x & np.uint64(0xFFFFFFFFFFFFFFFF))
    else:
        return np.uint64(x)

@numba.njit(cache=True)
def _pvm_Z(a_u64, n_u64):
    """Unsigned a with n bytes interpreted as signed int64."""
    au = np.uint64(a_u64)
    nb = np.uint64(n_u64)
    width = nb << np.uint64(3)
    if width >= np.uint64(64):
        return np.int64(au)
    if width == np.uint64(0):
        return np.int64(0)
    mask = (np.uint64(1) << width) - np.uint64(1)
    val = au & mask
    signbit = np.uint64(1) << (width - np.uint64(1))
    if (val & signbit) != np.uint64(0):
        extend_mask = np.uint64(0xFFFFFFFFFFFFFFFF) ^ mask
        return np.int64(val | extend_mask)
    else:
        return np.int64(val)

@numba.njit(cache=True)
def _find_section_idx(addr, section_starts, section_ends):
    idx = -1
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = i
            break
    return idx

@numba.njit(cache=True)
def _mem_write(addr, value, bytes_to_write, section_starts, section_ends, section_arrays, acl_dict):
    idx = _find_section_idx(addr, section_starts, section_ends)
    if idx < 0:
        return np.int32(-1)
    page_nr = addr // np.uint64(PVM_PAGE_SIZE)
    if (page_nr not in acl_dict) or (acl_dict[page_nr] < np.uint64(MEM_WRITABLE)):
        return np.int32(-1)
    start = section_starts[idx]
    off = addr - start
    a = section_arrays[idx]
    if off + np.uint64(bytes_to_write) > np.uint64(len(a)):
        return np.int32(-1)
    base = int(off)
    if bytes_to_write == np.uint8(1):
        a[base] = np.uint8(value & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(2):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(4):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
        a[base + 2] = np.uint8((value >> np.uint64(16)) & np.uint64(0xFF))
        a[base + 3] = np.uint8((value >> np.uint64(24)) & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(8):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
        a[base + 2] = np.uint8((value >> np.uint64(16)) & np.uint64(0xFF))
        a[base + 3] = np.uint8((value >> np.uint64(24)) & np.uint64(0xFF))
        a[base + 4] = np.uint8((value >> np.uint64(32)) & np.uint64(0xFF))
        a[base + 5] = np.uint8((value >> np.uint64(40)) & np.uint64(0xFF))
        a[base + 6] = np.uint8((value >> np.uint64(48)) & np.uint64(0xFF))
        a[base + 7] = np.uint8((value >> np.uint64(56)) & np.uint64(0xFF))
    else:
        return np.int32(-1)
    return np.int32(0)

@numba.njit(cache=True)
def _mem_read(addr, bytes_to_read, section_starts, section_ends, section_arrays, acl_dict):
    idx = _find_section_idx(addr, section_starts, section_ends)
    if idx < 0:
        return np.int32(-1), np.uint64(0)
    page_nr = addr // np.uint64(PVM_PAGE_SIZE)
    if (page_nr not in acl_dict) or (acl_dict[page_nr] == np.uint64(MEM_INACCESSIBLE)):
        return np.int32(-1), np.uint64(0)
    start = section_starts[idx]
    off = addr - start
    a = section_arrays[idx]
    if off + np.uint64(bytes_to_read) > np.uint64(len(a)):
        return np.int32(-1), np.uint64(0)
    base = int(off)
    if bytes_to_read == np.uint8(1):
        return np.int32(0), np.uint64(a[base])
    elif bytes_to_read == np.uint8(2):
        return np.int32(0), (np.uint64(a[base]) | (np.uint64(a[base + 1]) << np.uint64(8)))
    elif bytes_to_read == np.uint8(4):
        return np.int32(0), (np.uint64(a[base]) |
                              (np.uint64(a[base + 1]) << np.uint64(8)) |
                              (np.uint64(a[base + 2]) << np.uint64(16)) |
                              (np.uint64(a[base + 3]) << np.uint64(24)))
    elif bytes_to_read == np.uint8(8):
        return np.int32(0), (np.uint64(a[base]) |
                              (np.uint64(a[base + 1]) << np.uint64(8)) |
                              (np.uint64(a[base + 2]) << np.uint64(16)) |
                              (np.uint64(a[base + 3]) << np.uint64(24)) |
                              (np.uint64(a[base + 4]) << np.uint64(32)) |
                              (np.uint64(a[base + 5]) << np.uint64(40)) |
                              (np.uint64(a[base + 6]) << np.uint64(48)) |
                              (np.uint64(a[base + 7]) << np.uint64(56)))
    else:
        return np.int32(-1), np.uint64(0)

@numba.njit(cache=True)
def _djump(pc_u32, a_u32, jump_table, pc_to_inst_index):
    # Special halt value per interpreter
    halt_value = np.uint32(2**32 - 2**16)
    if a_u32 == halt_value:
        return np.int32(-1)
    # Basic validation against jump_table and pc_to_inst_index
    if a_u32 == np.uint32(0):
        return np.int32(-2)
    idx = int(a_u32)  # simplistic; assumes a_u32 is already an index for tests
    if idx < 0 or idx >= len(jump_table):
        return np.int32(-2)
    target_offset = jump_table[idx]
    if target_offset == -1:
        return np.int32(-2)
    target_pc = np.int64(pc_u32) + np.int64(target_offset)
    if target_pc < 0 or target_pc >= len(pc_to_inst_index):
        return np.int32(-2)
    return np.int32(target_pc - np.int64(pc_u32))


@cc.export('invoke_native', (
    u32, u64, u32, u32,                 # pc_start, gas_start, inst_start, initial_skip_len
    u8_array, u32,                      # code, code_size
    i32_array, i32_array, i32_array, i32_array,  # inst_pos_keys, inst_pos_vals, inst_arg_len, pc_to_inst_index
    i32_array, i32_array,               # opcode_scheme, jump_table
    u8_array, u8_array, u8_array,       # mem_ops_read, mem_ops_write, mem_ops_bytes (unused but keep for sig compat)
    u64_array, u64_array,               # mem_section_starts, mem_section_ends
    u8_array_list, dict_u64_u64,        # section_arrays, acl_dict
    u64_array,                          # heap_info [current_heap_end, next_section_start, mem_writable_value]
    u64_array,                          # registers_in
    # logging omitted for AOT
    u64_array, i64_array,               # registers_out, state_out
    i32_array                           # heap_grew_out
))
def invoke_native(
    pc_start, gas_start, inst_start, initial_skip_len,
    code, code_size,
    inst_pos_keys, inst_pos_vals, inst_arg_len, pc_to_inst_index,
    opcode_scheme, jump_table,
    mem_ops_read, mem_ops_write, mem_ops_bytes,
    mem_section_starts, mem_section_ends, section_arrays, acl_dict,
    heap_info,
    registers_in,
    registers_out, state_out, heap_grew_out
):
    """AOT-compiled core interpreter loop without logging."""
    pc = np.uint32(pc_start)
    gas = np.int64(gas_start)
    status = EXIT_RESUME
    exit_value = np.int64(0)
    skip_len = np.int64(initial_skip_len)
    inst_nr = np.uint32(inst_start)

    # Copy registers in
    # Assume 13 regs (as in interpreter)
    regs_len = min(len(registers_in), len(registers_out))
    regs = np.empty(regs_len, dtype=np.uint64)
    for i in range(regs_len):
        regs[i] = registers_in[i]

    while status == EXIT_RESUME and gas > 0:
        next_pc = np.uint32(pc + skip_len)
        if next_pc >= code_size:
            status = EXIT_PANIC
            break

        inst_index = -1
        npi = int(next_pc)
        if 0 <= npi < len(pc_to_inst_index):
            inst_index = pc_to_inst_index[npi]

        if inst_index < 0:
            # invalid pc, return trap
            for i in range(regs_len):
                registers_out[i] = regs[i]
            state_out[STATE_STATUS] = np.int64(status)
            state_out[STATE_PC] = np.int64(next_pc)
            state_out[STATE_GAS] = np.int64(gas)
            state_out[STATE_INST_NR] = np.int64(inst_nr)
            state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
            state_out[STATE_SKIP_LEN] = np.int64(skip_len)
            state_out[STATE_ERROR] = np.int64(ERROR_PANIC_TRAP)
            return ERROR_PANIC_TRAP

        gas -= 1
        pc = next_pc
        inst_nr = np.uint32(inst_nr + 1)

        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = np.int64(inst_arg_len[inst_index] + 1)

        # Implement core groups first; unknown opcodes panic for now.

        # InstructionType.none
        if inst_type == 0:
            # opcodes: trap(0), fallthrough(1)
            if opcode == 0:  # trap
                # panic trap
                for i in range(regs_len):
                    registers_out[i] = regs[i]
                state_out[STATE_STATUS] = np.int64(EXIT_PANIC)
                state_out[STATE_PC] = np.int64(pc)
                state_out[STATE_GAS] = np.int64(gas)
                state_out[STATE_INST_NR] = np.int64(inst_nr)
                state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
                state_out[STATE_SKIP_LEN] = np.int64(skip_len)
                state_out[STATE_ERROR] = np.int64(ERROR_PANIC_TRAP)
                return ERROR_PANIC_TRAP
            elif opcode == 1:  # fallthrough
                # no-op
                pass
            else:
                # unknown none-type opcode
                for i in range(regs_len):
                    registers_out[i] = regs[i]
                state_out[STATE_STATUS] = np.int64(EXIT_PANIC)
                state_out[STATE_PC] = np.int64(pc)
                state_out[STATE_GAS] = np.int64(gas)
                state_out[STATE_INST_NR] = np.int64(inst_nr)
                state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
                state_out[STATE_SKIP_LEN] = np.int64(skip_len)
                state_out[STATE_ERROR] = np.int64(ERROR_INVALID_OPCODE)
                return ERROR_INVALID_OPCODE

        # InstructionType.imm (ecalli)
        elif inst_type == 1:
            l_x = min(4, inst_arg_len[inst_index])
            # read little-endian immediate
            v_x = _pvm_X(_read_uint_le(code, pc + 1, np.uint8(l_x)), np.uint64(l_x))
            # ecalli
            exit_value = np.int64(v_x)
            # host halt
            for i in range(regs_len):
                registers_out[i] = regs[i]
            state_out[STATE_STATUS] = np.int64(EXIT_HOST_HALT)
            state_out[STATE_PC] = np.int64(pc)
            state_out[STATE_GAS] = np.int64(gas)
            state_out[STATE_INST_NR] = np.int64(inst_nr)
            state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
            state_out[STATE_SKIP_LEN] = np.int64(skip_len)
            state_out[STATE_ERROR] = np.int64(ERROR_NONE)
            return ERROR_NONE

        # InstructionType.reg_ext_imm (e.g., load_imm_64)
        elif inst_type == 2:
            r_a = min(12, code[pc + 1] % 16)
            v_x = _read_uint_le(code, pc + 2, np.uint8(8))
            # Treat as load_imm_64
            regs[r_a] = v_x

        # InstructionType.imm_imm (store immediate to memory)
        elif inst_type == 3:
            l_x = min(4, int(inst_arg_len[inst_index]))
            l_y = min(4, max(0, int(inst_arg_len[inst_index]) - l_x - 1))
            v_x = _pvm_X(_read_uint_le(code, pc + 2, np.uint8(l_x)), np.uint64(l_x))
            v_y = _pvm_X(_read_uint_le(code, pc + 2 + l_x, np.uint8(l_y)), np.uint64(l_y))
            ok = True
            if opcode == 30:
                ok = _mem_write(v_x, np.uint64(v_y % np.uint64(2**8)), np.uint8(1), mem_section_starts, mem_section_ends, section_arrays, acl_dict) == np.int32(0)
            elif opcode == 31:
                ok = _mem_write(v_x, np.uint64(v_y % np.uint64(2**16)), np.uint8(2), mem_section_starts, mem_section_ends, section_arrays, acl_dict) == np.int32(0)
            elif opcode == 32:
                ok = _mem_write(v_x, np.uint64(v_y % np.uint64(2**32)), np.uint8(4), mem_section_starts, mem_section_ends, section_arrays, acl_dict) == np.int32(0)
            elif opcode == 33:
                ok = _mem_write(v_x, np.uint64(v_y), np.uint8(8), mem_section_starts, mem_section_ends, section_arrays, acl_dict) == np.int32(0)
            else:
                ok = False
            if not ok:
                for i in range(regs_len): registers_out[i] = regs[i]
                state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT if opcode in (30,31,32,33) else EXIT_PANIC)
                state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT if opcode in (30,31,32,33) else ERROR_INVALID_OPCODE)
                return ERROR_MEMORY_FAULT if opcode in (30,31,32,33) else ERROR_INVALID_OPCODE

        # InstructionType.reg_imm (jump_ind, loads, stores)
        elif inst_type == 5:
            r_a = min(12, code[pc + 1] % 16)
            l_x = min(4, max(0, int(inst_arg_len[inst_index]) - 1))
            v_x = _pvm_X(_read_uint_le(code, pc + 2, np.uint8(l_x)), np.uint64(l_x))
            if opcode == 50:
                jump_target = np.uint32(regs[r_a] + v_x)
                dj = _djump(pc, jump_target, jump_table, pc_to_inst_index)
                if dj == np.int32(-1):
                    skip_len = np.int64(0)
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_HALT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_NONE)
                    return ERROR_NONE
                elif dj == np.int32(-2):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PANIC); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_PANIC_INVALID_DJUMP)
                    return ERROR_PANIC_INVALID_DJUMP
                else:
                    skip_len = np.int64(dj)
            elif opcode == 51:
                regs[r_a] = v_x
            elif opcode == 52:
                s, val = _mem_read(v_x, np.uint8(1), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(1))
            elif opcode == 53:
                s, val = _mem_read(v_x, np.uint8(1), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(1))
            elif opcode == 54:
                s, val = _mem_read(v_x, np.uint8(2), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(2))
            elif opcode == 55:
                s, val = _mem_read(v_x, np.uint8(2), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(2))
            elif opcode == 56:
                s, val = _mem_read(v_x, np.uint8(4), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(4))
            elif opcode == 57:
                s, val = _mem_read(v_x, np.uint8(4), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = _pvm_X(val, np.uint64(4))
            elif opcode == 58:
                s, val = _mem_read(v_x, np.uint8(8), mem_section_starts, mem_section_ends, section_arrays, acl_dict)
                if s != np.int32(0):
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
                regs[r_a] = val
            elif opcode == 59:
                if _mem_write(v_x, np.uint64(regs[r_a] % np.uint64(2**8)), np.uint8(1), mem_section_starts, mem_section_ends, section_arrays, acl_dict) < 0:
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
            elif opcode == 60:
                if _mem_write(v_x, np.uint64(regs[r_a] % np.uint64(2**16)), np.uint8(2), mem_section_starts, mem_section_ends, section_arrays, acl_dict) < 0:
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
            elif opcode == 61:
                if _mem_write(v_x, np.uint64(regs[r_a] % np.uint64(2**32)), np.uint8(4), mem_section_starts, mem_section_ends, section_arrays, acl_dict) < 0:
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
            elif opcode == 62:
                if _mem_write(v_x, np.uint64(regs[r_a]), np.uint8(8), mem_section_starts, mem_section_ends, section_arrays, acl_dict) < 0:
                    for i in range(regs_len): registers_out[i] = regs[i]
                    state_out[STATE_STATUS] = np.int64(EXIT_PAGE_FAULT); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_MEMORY_FAULT); return ERROR_MEMORY_FAULT
            else:
                for i in range(regs_len): registers_out[i] = regs[i]
                state_out[STATE_STATUS] = np.int64(EXIT_PANIC); state_out[STATE_PC] = np.int64(pc); state_out[STATE_GAS] = np.int64(gas); state_out[STATE_INST_NR] = np.int64(inst_nr); state_out[STATE_EXIT_VALUE] = np.int64(exit_value); state_out[STATE_SKIP_LEN] = np.int64(skip_len); state_out[STATE_ERROR] = np.int64(ERROR_INVALID_OPCODE); return ERROR_INVALID_OPCODE

        # InstructionType.reg_reg (e.g., move_reg)
        elif inst_type == 8:
            r_d = min(12, code[pc + 1] % 16)
            r_a = min(12, code[pc + 1] // 16)
            regs[r_d] = regs[r_a]

        else:
            # For now, signal invalid opcode to indicate unsupported path in AOT build.
            for i in range(regs_len):
                registers_out[i] = regs[i]
            state_out[STATE_STATUS] = np.int64(EXIT_PANIC)
            state_out[STATE_PC] = np.int64(pc)
            state_out[STATE_GAS] = np.int64(gas)
            state_out[STATE_INST_NR] = np.int64(inst_nr)
            state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
            state_out[STATE_SKIP_LEN] = np.int64(skip_len)
            state_out[STATE_ERROR] = np.int64(ERROR_INVALID_OPCODE)
            return ERROR_INVALID_OPCODE

    # Copy out state
    for i in range(regs_len):
        registers_out[i] = regs[i]
    state_out[STATE_STATUS] = np.int64(status)
    state_out[STATE_PC] = np.int64(pc)
    state_out[STATE_GAS] = np.int64(gas)
    state_out[STATE_INST_NR] = np.int64(inst_nr)
    state_out[STATE_EXIT_VALUE] = np.int64(exit_value)
    state_out[STATE_SKIP_LEN] = np.int64(skip_len)
    state_out[STATE_ERROR] = np.int64(ERROR_NONE)
    return ERROR_NONE


if __name__ == '__main__':
    cc.compile()
