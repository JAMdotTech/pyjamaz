"""
An optimized PVM interpreter using Numba JIT compiler for the main loop & functions.
"""
#import ctypes
#import time as _pytime

import numpy as np
import numpy.typing as npt

from numba import njit, types
from numba.typed import Dict, List
from numba import uint8, uint32, int32, uint64, int64, boolean

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR
from pyjamaz.pvm.exceptions import PVMMemoryError, PanicError

from pyjamaz.pvm.interpreters.numba.const import NUMBA_CACHE, STATE_STATUS, STATE_PC, STATE_GAS, STATE_INST_NR, \
    STATE_EXIT_VALUE, \
    STATE_SKIP_LEN, STATE_ERROR, PVM_PAGE_SIZE, PVM_PAGE_SHIFT, EXIT_RESUME, EXIT_PANIC, ERROR_PANIC_TRAP, \
    EXIT_HOST_HALT, ERROR_NONE, ERROR_MEMORY_FAULT, EXIT_PAGE_FAULT, EXIT_HALT, ERROR_PANIC_INVALID_DJUMP, \
    ERROR_PANIC_INVALID_BRANCH, MEM_READABLE, MEM_WRITABLE, ERROR_PANIC_INVALID_PC, ERROR_INVALID_OPCODE, OUT_OF_GAS
from pyjamaz.pvm.interpreters.numba.defs import U8, U16, U32, U64, I8, I16, I32, I64, u8_array_list, u64_array_list, U32_MASK, pvm_X_jit, \
    read_uint_jit, mem_write_jit, mem_read_jit, pvm_Z_jit, U64_MASK, count_leading_zeroes_jit, \
    count_trailing_zeroes_jit, pvm_Z_inv_jit, reverse_bytes_jit, rori64_jit, rori32_jit, pvm_rtz_div_jit, pvm_smod_jit, \
    imul64wide_jit, smul_u64wide_jit, umul64wide_jit, roli64_jit, roli32_jit, ACL_PAGES_PER_BITMAP
from pyjamaz.pvm.constants import (
    ExitReason, OpcodeScheme,

    op_trap, op_fallthrough, op_ecalli, op_load_imm_64, op_store_imm_u8, op_store_imm_u16,
    op_store_imm_u32, op_store_imm_u64, op_jump, op_jump_ind, op_load_imm, op_load_u8,
    op_load_i8, op_load_u16, op_load_i16, op_load_u32, op_load_i32, op_load_u64,
    op_store_u8, op_store_u16, op_store_u32, op_store_u64, op_store_imm_ind_u8,
    op_store_imm_ind_u16, op_store_imm_ind_u32, op_store_imm_ind_u64, op_load_imm_jump,
    op_branch_eq_imm, op_branch_ne_imm, op_branch_lt_u_imm, op_branch_le_u_imm,
    op_branch_ge_u_imm, op_branch_gt_u_imm, op_branch_lt_s_imm, op_branch_le_s_imm,
    op_branch_ge_s_imm, op_branch_gt_s_imm, op_move_reg, op_sbrk, op_count_set_bits_64,
    op_count_set_bits_32, op_leading_zero_bits_64, op_leading_zero_bits_32,
    op_trailing_zero_bits_64, op_trailing_zero_bits_32, op_sign_extend_8, op_sign_extend_16,
    op_zero_extend_16, op_reverse_bytes, op_store_ind_u8, op_store_ind_u16,
    op_store_ind_u32, op_store_ind_u64, op_load_ind_u8, op_load_ind_i8, op_load_ind_u16,
    op_load_ind_i16, op_load_ind_u32, op_load_ind_i32, op_load_ind_u64, op_add_imm_32,
    op_and_imm, op_xor_imm, op_or_imm, op_mul_imm_32, op_set_lt_u_imm, op_set_lt_s_imm,
    op_shlo_l_imm_32, op_shlo_r_imm_32, op_shar_r_imm_32, op_neg_add_imm_32,
    op_set_gt_u_imm, op_set_gt_s_imm, op_shlo_l_imm_alt_32, op_shlo_r_imm_alt_32,
    op_shar_r_imm_alt_32, op_cmov_iz_imm, op_cmov_nz_imm, op_add_imm_64, op_mul_imm_64,
    op_shlo_l_imm_64, op_shlo_r_imm_64, op_shar_r_imm_64, op_neg_add_imm_64,
    op_shlo_l_imm_alt_64, op_shlo_r_imm_alt_64, op_shar_r_imm_alt_64, op_rot_r_64_imm,
    op_rot_r_64_imm_alt, op_rot_r_32_imm, op_rot_r_32_imm_alt, op_branch_eq, op_branch_ne,
    op_branch_lt_u, op_branch_lt_s, op_branch_ge_u, op_branch_ge_s, op_load_imm_jump_ind,
    op_add_32, op_sub_32, op_mul_32, op_div_u_32, op_div_s_32, op_rem_u_32, op_rem_s_32,
    op_shlo_l_32, op_shlo_r_32, op_shar_r_32, op_add_64, op_sub_64, op_mul_64,
    op_div_u_64, op_div_s_64, op_rem_u_64, op_rem_s_64, op_shlo_l_64, op_shlo_r_64,
    op_shar_r_64, op_and, op_xor, op_or, op_mul_upper_s_s, op_mul_upper_u_u,
    op_mul_upper_s_u, op_set_lt_u, op_set_lt_s, op_cmov_iz, op_cmov_nz, op_rot_l_64,
    op_rot_l_32, op_rot_r_64, op_rot_r_32, op_and_inv, op_or_inv, op_xnor, op_max,
    op_max_u, op_min, op_min_u, MEM_R, MEM_W,

    inst_none, inst_imm, inst_reg_ext_imm, inst_imm_imm, inst_offset, inst_reg_imm,
    inst_reg_imm_imm, inst_reg_imm_offset, inst_reg_reg, inst_reg_reg_imm,
    inst_reg_reg_offset, inst_reg_reg_imm_imm, inst_reg_reg_reg, MemOps, ExitCondition, OpcodeNames
)

from pyjamaz.pvm.types import PVMProgram
from pyjamaz.pvm.interpreters.graypaper.memory import PVMMemory


@njit(uint32(
    uint64[::1],  # reg
    uint64[::1],  # registers_out
    int64[::1],   # state_out
    int64,        # status
    int64,        # pc
    int64,        # gas
    int64,        # inst_nr
    int64,        # exit_value
    uint32,       # skip_len
    uint32        # error_code
), cache=NUMBA_CACHE)
def sync_state_and_return(
        reg:List[U64],
        registers_out:List[U64],
        state_out:List[U64],
        status:I64,
        pc:I64,
        gas:I64,
        inst_nr:I64,
        exit_value:I64,
        skip_len:U32,
        error_code:U32) -> U32:

    for i in range(len(reg)):
        registers_out[i] = reg[i]
    state_out[STATE_STATUS] = I64(status)
    state_out[STATE_PC] = I64(pc)
    state_out[STATE_GAS] = I64(gas)
    state_out[STATE_INST_NR] = I64(inst_nr)
    state_out[STATE_EXIT_VALUE] = I64(exit_value)
    state_out[STATE_SKIP_LEN] = I64(skip_len)
    state_out[STATE_ERROR] = I64(error_code)
    return error_code


# Note: uncomment for memory debugging:

# @njit(uint64(uint64), cache=NUMBA_CACHE)
# def _fmix64_jit(x: U64) -> U64:
#     # Finalization mix (from MurmurHash3)
#     x ^= x >> U64(33)
#     x *= U64(0xff51afd7ed558ccd)
#     x ^= x >> U64(33)
#     x *= U64(0xc4ceb9fe1a85ec53)
#     x ^= x >> U64(33)
#     return x

#
# @njit(uint64(uint8[::1]), cache=NUMBA_CACHE)
# def hash_memory_segment(section_array) -> U64:
#     """
#     Hash the memory segment with FNV-1a 64-bit, then fmix.
#     """
#     n = len(section_array)
#     if n == 0:
#         return U64(0)
#
#     h = U64(1469598103934665603)  # FNV-1a offset basis (64-bit)
#     prime = U64(10995628211)  # FNV-1a prime (64-bit)
#
#     # Process all bytes (rely on 64-bit wraparound; no modulo)
#     for i in range(n):
#         h ^= U64(section_array[i])
#         h *= prime
#
#     return _fmix64_jit(h)
#
#
# @njit(uint64(u8_array_list, int32), cache=NUMBA_CACHE)
# def get_memory_hash(section_arrays, seg_idx: I32):
#     segment_hash = U64(0)
#     if seg_idx >= 0 and seg_idx < len(section_arrays):
#         segment_hash = hash_memory_segment(section_arrays[seg_idx])
#     return segment_hash


@njit(types.Tuple((uint64, int64))(
    uint64,
    uint64,
    uint64,
    int64,
    u8_array_list,
    uint64[::1],
    u64_array_list
), cache=NUMBA_CACHE)
def sbrk_jit(
        size: U64,
        current_heap_ptr: U64,
        next_section_start: U64,
        mem_writable: I64,
        section_arrays,
        section_starts,
        acl_bitmaps) -> (U64, I64):

    if size == 0:
        return current_heap_ptr, I64(0)

    new_heap_ptr = current_heap_ptr + size
    if new_heap_ptr >= next_section_start:
        return U64(0), I64(0)  # Allocation failed - would overlap next section

    # Calculate page boundaries (match PVMMemory.page_size semantics: ceil to page size)
    next_page_boundary = ((current_heap_ptr + PVM_PAGE_SIZE - 1) >> PVM_PAGE_SHIFT) << PVM_PAGE_SHIFT

    grew_bytes = I64(0)
    if new_heap_ptr > next_page_boundary:
        new_heap_end = ((new_heap_ptr + PVM_PAGE_SIZE - 1) >> PVM_PAGE_SHIFT) << PVM_PAGE_SHIFT
        growth = new_heap_end - next_page_boundary

        heap_arr = section_arrays[1]
        base_start = section_starts[1]
        desired_len = int(new_heap_end - base_start)
        cur_len = len(heap_arr)

        if desired_len > cur_len:
            reserve_len = desired_len
            new_arr = np.empty(reserve_len, dtype=U8)
            if cur_len > 0:
                new_arr[:cur_len] = heap_arr[:cur_len]
            new_arr[cur_len:reserve_len] = 0
            section_arrays[1] = new_arr
            #heap_arr = new_arr
            grew_bytes = I64(growth)

            # Ensure ACL bitmaps cover the extended heap size
            acl_array = acl_bitmaps[1]
            bitmap_count = len(acl_array)
            prev_page_count = cur_len // PVM_PAGE_SIZE
            new_page_count = reserve_len // PVM_PAGE_SIZE
            bitmaps_required = -(-new_page_count // ACL_PAGES_PER_BITMAP)

            if bitmaps_required > bitmap_count:
                extended = np.zeros(bitmaps_required, dtype=np.uint64)
                if bitmap_count > 0:
                    extended[:bitmap_count] = acl_array
                acl_array = extended
                acl_bitmaps[1] = acl_array
            else:
                acl_array = acl_bitmaps[1]

            if new_page_count > prev_page_count and len(acl_array) > 0:
                pages_to_enable = new_page_count - prev_page_count
                perm = int(mem_writable)
                if perm == MEM_WRITABLE:
                    required_bits = 0b11
                elif perm == MEM_READABLE:
                    required_bits = 0b01
                else:
                    required_bits = 0

                if required_bits != 0:
                    for page in range(prev_page_count, prev_page_count + pages_to_enable):
                        bitmap_idx = page // ACL_PAGES_PER_BITMAP
                        shift = (ACL_PAGES_PER_BITMAP - 1 - (page % ACL_PAGES_PER_BITMAP)) * 2
                        mask = np.uint64(0b11 << shift)
                        bits = np.uint64(required_bits << shift)
                        acl_array[bitmap_idx] = np.uint64((acl_array[bitmap_idx] & ~mask) | bits)
        else:
            grew_bytes = I64(growth)
            current_len = int(current_heap_ptr - base_start)
            if desired_len > current_len:
                heap_arr[current_len:desired_len] = 0

    return new_heap_ptr, grew_bytes


@njit(int32(uint32, int64, boolean, int32[::1]), cache=NUMBA_CACHE)
def branch_jit(pc: U32, offset: I64, condition: bool, pc_to_inst_index) -> I32:
    if condition:
        target_pc = pc + offset
        tpi = int(target_pc)
        if not (tpi >= 0 and tpi < len(pc_to_inst_index) and pc_to_inst_index[tpi] >= 0):
            return I32(-1)  # Invalid branch - panic

        return I32(offset)  # Valid branch
    else:
        return I32(0)  # No branch - continue


@njit(int32(uint32, int32[::1], uint32, int32[::1]), cache=NUMBA_CACHE)
def djump_jit(a: U32, jump_table, pc: U32, pc_to_inst_index) -> I32:
    halt_value = U32((U32(0xFFFFFFFF) - U32(0xFFFF)) & U32_MASK)
    if a == halt_value:
        return I32(-1)  # Special return code for halt

    if (a == 0 or
        a > len(jump_table) * PVM_DYNAMIC_ALIGNMENT_FACTOR or
        a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0
    ):
        return I32(-2)

    jump_idx = a // PVM_DYNAMIC_ALIGNMENT_FACTOR - 1
    if jump_idx < 0 or jump_idx >= len(jump_table):
        return I32(-2)

    target_pc = U32(jump_table[jump_idx])

    tpi = int(target_pc)
    if not (tpi >= 0 and tpi < len(pc_to_inst_index) and pc_to_inst_index[tpi] >= 0):
        return I32(-2)

    return I32(target_pc - pc)  # Valid skip_len


@njit(
    types.void(
        types.ListType(types.unicode_type),  # opcode_names list
        int64[::1],               # local_state
        uint64[::1],              # regs
        types.optional(u8_array_list),    # mem
        types.optional(uint64[::1]),      # mem_starts
        types.optional(uint64[::1])       # mem_ends
    ),
    cache=NUMBA_CACHE
)
def log(opcode_names, local_state, regs, mem, mem_starts, mem_ends):
    inst_nr = int(local_state[0])
    opcode = int(local_state[1])
    pc = int(local_state[2])
    gas = int(local_state[3])
    start_time = float(local_state[4])

    if len(opcode_names) == 0:
        return

    # Use array indexing for opcode name lookup
    if opcode >= 0 and opcode < len(opcode_names):
        name = opcode_names[opcode]
    else:
        name = "UNKNOWN"
    #
    mem_info = ""
    # # if mem is not None and len(mem) >= 2:
    # #     if mem_starts is not None and mem_ends is not None:
    # #         # Compute effective lengths based on section bounds so hash reflects sbrk changes
    # #         heap_len = int(mem_ends[1] - mem_starts[1])
    # #         if heap_len < 0:
    # #             heap_len = 0
    # #         if heap_len > len(mem[1]):
    # #             heap_len = len(mem[1])
    # #         heap_hash = hash_memory_segment(mem[1][:heap_len])
    # #     else:
    # #         heap_hash = hash_memory_segment(mem[1])
    # #     mem_info += f"heap_hash:{heap_hash}"
    # # if mem is not None and len(mem) >= 3:
    # #     if mem_starts is not None and mem_ends is not None:
    # #         stack_len = int(mem_ends[2] - mem_starts[2])
    # #         if stack_len < 0:
    # #             stack_len = 0
    # #         if stack_len > len(mem[2]):
    # #             stack_len = len(mem[2])
    # #         stack_hash = hash_memory_segment(mem[2][:stack_len])
    # #     else:
    # #         stack_hash = hash_memory_segment(mem[2])
    # #     mem_info += f" stack_hash:{stack_hash}"
    #
    # # print("inst=",inst_nr, "op=",name, "pc=",pc, "gas=",gas,
    # #       "r1=",reg1, "r2=",reg2, "r3=",reg3,
    # #       "imm1=",imm1, "imm2=",imm2, "off1=",off1, "off2=",off2, context, mem_info)
    #
    # # Format opcode name with fixed width (22 chars)
    name_str = name
    name_pad = 22 - len(name_str)
    if name_pad > 0:
        name_str = name_str + (" " * name_pad)
    #
    # # Format registers with fixed width (21 chars) for even spacing.
    regs_str = ""
    for i in range(len(regs)):
        s = str(regs[i])
        pad = 21 - len(s)
        if pad > 0:
            regs_str += (" " * pad) + s
        else:
            regs_str += s
        if i != len(regs) - 1:
            regs_str += " "

    # # Fixed width for inst_nr and pc (4 chars each, right-aligned)
    inst_str = str(inst_nr)
    if len(inst_str) < 4:
        inst_str = (" " * (4 - len(inst_str))) + inst_str
    #
    pc_str = str(pc)
    if len(pc_str) < 4:
        pc_str = (" " * (4 - len(pc_str))) + pc_str

    # Note: uncomment when logging timing info
    # Compute elapsed time if start_time provided (debug; uses objmode)
    # if start_time > 0.0:
    #     with objmode(tnow='float64'):
    #         tnow = _pytime.perf_counter()
    #     dt_ms = (tnow - start_time) * 1000.0
    #     #print(inst_str, pc_str, name_str, regs_str, mem_info, dt_ms)
    #     print(inst_str, pc_str, name_str, dt_ms)
    # else:
    #     print(inst_str, pc_str, name_str, regs_str, mem_info)

    #print(inst_str, pc_str, name_str, dt_ms)
    print(inst_str, pc_str, name_str, gas, regs_str, mem_info)


@njit(int32(
    uint32,          # pc
    int64,           # gas
    uint32,          # inst_nr
    uint32,          # skip_len

    uint8[::1],      # code
    uint32,          # code_size
    int32[::1],      # inst_arg_len_array
    int32[::1],      # pc_to_inst_index
    int32[::1],      # opcode_scheme_array (len 256)
    int32[::1],      # jump_table_array

    uint64[::1],     # mem_section_starts
    uint64[::1],     # mem_section_ends
    u8_array_list,   # section_arrays : List[uint8[:]]
    u64_array_list,  # acl_bitmaps
    int32[::1],      # section_access
    uint64[::1],     # heap_info (len 3)

    uint64[::1],     # reg (len 13)

    boolean,         # logging_enabled
    types.ListType(types.unicode_type),  # opcode_names list

    uint64[::1],     # registers_out
    int64[::1],      # state_out
    int64[::1],      # heap_grew_out
), cache=NUMBA_CACHE)
def invoke_native(
        pc_start,
        gas_start,
        inst_start,
        initial_skip_len,

        code,
        code_size,
        inst_arg_len,
        pc_to_inst_index,
        opcode_scheme,
        jump_table,

        mem_section_starts,
        mem_section_ends,
        section_arrays,
        acl_bitmaps,
        section_access,
        heap_info,  # [current_heap_end, next_section_start, mem_writable_value]

        registers_in,

        logging,
        opcode_names,

        registers_out,
        state_out,
        heap_grew_out
):
    """
    Numba compiled core interpreter loop

    Returns:
        Error code (0 = success, >0 = specific error)
    """
    pc = U32(pc_start)
    gas = I64(gas_start)
    status = EXIT_RESUME
    exit_value = I64(0)
    skip_len = I64(initial_skip_len)
    inst_nr = U32(inst_start)

    # Copy registers
    reg = registers_in.copy()

    timing_enabled = False
    start_time = 0.0    # Note: only used when timing_enabled == True to measure time per opcode

    # Local state array for logging: [inst_nr, opcode, pc, gas, start_time]
    if logging:
        local_state = np.empty(5, dtype=np.int64)

    while status == EXIT_RESUME:

        # Note: enable when we want to run perf checks
        # if logging and timing_enabled:
        #     with objmode(t0='float64'):
        #         t0 = _pytime.perf_counter()
        #     start_time = t0

        if gas <= 0:
            return sync_state_and_return(reg, registers_out, state_out, OUT_OF_GAS, pc, gas, inst_nr, 0, skip_len, ERROR_NONE)

        gas -= 1
        next_pc = U32(pc + skip_len)
        pc = next_pc
        inst_nr += 1

        if next_pc >= code_size:
            return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, 0, skip_len, ERROR_PANIC_TRAP)

        inst_index = -1
        npi = int(next_pc)
        if npi >= 0 and npi < len(pc_to_inst_index):
            inst_index = pc_to_inst_index[npi]

        if inst_index < 0:
            return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)


        # Fetch opcode and decode
        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = inst_arg_len[inst_index] + 1
        if logging:
            local_state[0] = inst_nr
            local_state[1] = opcode
            local_state[2] = pc
            local_state[3] = gas
            local_state[4] = start_time  # Will be converted to float in log function

        # GP-0.6.7-section:A.5.1
        if inst_type == inst_none:  # InstructionType.none
            if opcode == op_trap:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
            elif opcode == op_fallthrough:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                pass
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.2
        elif inst_type == inst_imm:  # InstructionType.imm
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_X_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_ecalli:
                exit_value = I64(v_x)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_HOST_HALT, pc, gas, inst_nr, exit_value, skip_len, ERROR_NONE)
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.3
        elif inst_type == inst_reg_ext_imm:  # InstructionType.reg_ext_imm
            r_a = min(12, code[pc + 1] % 16)
            v_x = read_uint_jit(code, pc + 2, 8)

            if opcode == op_load_imm_64:
                reg[r_a] = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.4
        elif inst_type == inst_imm_imm:
            l_x = min(4, code[pc + 1] % 8)
            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), np.uint8(l_y))

            if opcode == op_store_imm_u8:
                mem_status, fault_addr = mem_write_jit(v_x, U64(v_y) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            elif opcode == op_store_imm_u16:
                mem_status, fault_addr = mem_write_jit(v_x, U64(v_y) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            elif opcode == op_store_imm_u32:
                mem_status, fault_addr = mem_write_jit(v_x, U64(v_y) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            elif opcode == op_store_imm_u64:
                mem_status, fault_addr = mem_write_jit(v_x, v_y, U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.5
        elif inst_type == inst_offset:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_jump:
                skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.6
        elif inst_type == inst_reg_imm:
            r_a = min(12, code[pc + 1] % 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))

            if opcode == op_jump_ind:
                jump_target = U32(((U64(reg[r_a]) + U64(v_x)) & U32_MASK))
                djump_result = djump_jit(jump_target, jump_table, pc, pc_to_inst_index)
                if djump_result == I32(-1):
                    skip_len = I64(0)
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_HALT, pc, gas, inst_nr, exit_value, skip_len, ERROR_NONE)
                elif djump_result == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_DJUMP)
                else:
                    skip_len = djump_result
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_imm:
                reg[r_a] = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_u8:
                status_read, loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_i8:
                status_read, loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(1))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_u16:
                status_read, loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_load_i16:
                status_read, loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(2))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_u32:
                status_read, loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_i32:
                status_read, loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_u64:
                status_read, loaded_value = mem_read_jit(v_x, U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_u8:
                mem_status, fault_addr = mem_write_jit(v_x, U64(reg[r_a]) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_u16:
                mem_status, fault_addr = mem_write_jit(v_x, U64(reg[r_a]) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    _rs2, _rv2 = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_u32:
                mem_status, fault_addr = mem_write_jit(v_x, U64(reg[r_a]) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_u64:
                mem_status, fault_addr = mem_write_jit(v_x, reg[r_a], U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(v_x), skip_len, ERROR_MEMORY_FAULT)
                if logging:
                    log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.7
        elif inst_type == inst_reg_imm_imm:
            r_a = min(12, code[pc + 1] % 16)
            w_a = reg[r_a]

            l_x = min(4, (code[pc + 1] // 16) % 8)
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), U8(l_x))

            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), U8(l_y))

            if opcode == op_store_imm_ind_u8:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(v_y) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_imm_ind_u16:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(v_y) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_imm_ind_u32:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(v_y) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_imm_ind_u64:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, v_y, U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.8
        elif inst_type == inst_reg_imm_offset:

            r_a = min(12, code[pc + 1] % 16)
            w_a = reg[r_a]

            l_x = min(4, (code[pc + 1] // 16) % 8)
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), U8(l_x))

            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_y = pvm_Z_jit(read_uint_jit(code, pc + 2 + l_x, l_y), U8(l_y))

            if opcode == op_load_imm_jump:
                reg[r_a] = v_x
                skip_len = v_y  # Jump with offset
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_eq_imm:
                branch_result = branch_jit(pc, v_y, w_a == v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a == v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ne_imm:
                branch_result = branch_jit(pc, v_y, w_a != v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a != v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_lt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a < v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a < v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_le_u_imm:
                branch_result = branch_jit(pc, v_y, w_a <= v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a <= v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ge_u_imm:
                branch_result = branch_jit(pc, v_y, w_a >= v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a >= v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_gt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a > v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a > v_x:
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_lt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) < pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) < pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_le_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) <= pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) <= pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ge_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) >= pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) >= pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_gt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) > pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) > pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.9
        elif inst_type == inst_reg_reg:

            r_d = min(12, code[pc + 1] % 16)
            r_a = min(12, code[pc + 1] // 16)

            if opcode == op_move_reg:
                reg[r_d] = reg[r_a]
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_sbrk:
                size = reg[r_a]
                current_heap_ptr = heap_info[0]
                next_section_start = heap_info[1]
                mem_writable_value = I64(heap_info[2])

                new_heap_ptr, grew_bytes = sbrk_jit(size, current_heap_ptr, next_section_start, mem_writable_value, section_arrays, mem_section_starts, acl_bitmaps)
                reg[r_d] = new_heap_ptr

                if new_heap_ptr != U64(0):
                    heap_info[0] = new_heap_ptr
                    mem_section_ends[1] = new_heap_ptr
                    if grew_bytes > I64(0):
                        heap_grew_out[0] += grew_bytes

                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_count_set_bits_64:
                val = reg[r_a]
                count = U64(0)
                for _ in range(64):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_count_set_bits_32:
                val = U32(U64(reg[r_a]) & U32_MASK)
                count = U64(0)
                for _ in range(32):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_leading_zero_bits_64:
                reg[r_d] = count_leading_zeroes_jit(reg[r_a], U8(64))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_leading_zero_bits_32:
                reg[r_d] = count_leading_zeroes_jit(U64(reg[r_a]) & U32_MASK, U8(32))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_trailing_zero_bits_64:
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a], U8(64))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_trailing_zero_bits_32:
                reg[r_d] = count_trailing_zeroes_jit(U64(reg[r_a]) & U32_MASK, U8(32))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_sign_extend_8:
                reg[r_d] = pvm_Z_inv_jit(pvm_Z_jit(U64(reg[r_a]) & U64(0xFF), 1), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_sign_extend_16:
                reg[r_d] = pvm_Z_inv_jit(pvm_Z_jit(U64(reg[r_a]) & U64(0xFFFF), 2), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_zero_extend_16:
                reg[r_d] = U64(reg[r_a]) & U64(0xFFFF)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_reverse_bytes:
                reg[r_d] = reverse_bytes_jit(reg[r_a])
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.10
        elif inst_type == inst_reg_reg_imm:

            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)

            w_a = reg[r_a]
            w_b = reg[r_b]

            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))

            if opcode == op_store_ind_u8:
                store_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(w_a) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_ind_u16:
                store_addr =(U64(w_b) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(w_a) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_ind_u32:
                store_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, U64(w_a) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_store_ind_u64:
                store_addr =  (U64(w_b) + U64(v_x)) & U64_MASK
                mem_status, fault_addr = mem_write_jit(store_addr, w_a, U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if mem_status == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if mem_status < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(store_addr), skip_len, ERROR_MEMORY_FAULT)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_u8:
                load_addr =  (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(1), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_i8:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(1), mem_section_starts, mem_section_ends,
                                                         section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 1), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_u16:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(2), mem_section_starts, mem_section_ends,
                                                         section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_i16:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(2), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 2), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_u32:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_i32:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(4), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 4), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_load_ind_u64:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(8), mem_section_starts, mem_section_ends, section_arrays, section_access)
                if status_read == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr, I64(load_addr), skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_add_imm_32:
                wb_vx_32 = (U64(w_b) + U64(v_x)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(wb_vx_32), np.uint8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_and_imm:
                reg[r_a] = w_b & v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_xor_imm:
                reg[r_a] = w_b ^ v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_or_imm:
                reg[r_a] = w_b | v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_imm_32:
                prod32 = (U64(w_b) * U64(v_x)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(prod32), np.uint8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_lt_u_imm:
                reg[r_a] = U64(1) if w_b < v_x else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_lt_s_imm:
                reg[r_a] = U64(1) if pvm_Z_jit(w_b, 8) < pvm_Z_jit(v_x, 8) else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_imm_32:
                sh = U64(v_x) & U64(31)
                reg[r_a] = pvm_X_jit(U32((U64(w_b) << sh) & U32_MASK), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_imm_32:
                reg[r_a] = pvm_X_jit(U32(w_b) >> U32(U32(v_x) & U32(31)), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_imm_32:
                reg[r_a] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(w_b), 4)) >> I64(U32(v_x) & U32(31)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_neg_add_imm_32:
                diff32 = (U64(v_x) - U64(w_b)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(diff32), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_gt_u_imm:
                reg[r_a] = U64(1) if w_b > v_x else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_gt_s_imm:
                reg[r_a] = U64(1) if pvm_Z_jit(w_b, 8) > pvm_Z_jit(v_x, 8) else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_imm_alt_32:
                sh = U64(w_b) & U64(31)
                reg[r_a] = pvm_X_jit(U32((U64(v_x) << sh) & U32_MASK), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_imm_alt_32:
                reg[r_a] = pvm_X_jit(U32(v_x) >> U32(U32(w_b) & U32(31)), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_imm_alt_32:
                reg[r_a] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(v_x), 4)) >> I64(U32(w_b) & U32(31)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_cmov_iz_imm:
                if w_b == 0:
                    reg[r_a] = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_cmov_nz_imm:
                if w_b != 0:
                    reg[r_a] = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_add_imm_64:
                reg[r_a] = (U64(w_b) + U64(v_x)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_imm_64:
                reg[r_a] = (U64(w_b) * U64(v_x)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_imm_64:
                sh = U64(v_x) & U64(63)
                reg[r_a] = (U64(w_b) << sh) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_imm_64:
                reg[r_a] = U64(w_b) >> U64(U64(v_x) & U64(63))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_imm_64:
                reg[r_a] = pvm_Z_inv_jit(I64(pvm_Z_jit(w_b, 8)) >> I64(U64(v_x) & U64(63)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_neg_add_imm_64:
                reg[r_a] = (U64(v_x) - U64(w_b)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_imm_alt_64:
                sh = U64(w_b) & U64(63)
                reg[r_a] = (U64(v_x) << sh) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_imm_alt_64:
                reg[r_a] = v_x >> U64(w_b & U64(63))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_imm_alt_64:
                reg[r_a] = pvm_Z_inv_jit(I64(pvm_Z_jit(v_x, 8)) >> I64(U64(w_b) & U64(63)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_64_imm:
                reg[r_a] = rori64_jit(w_b, v_x)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_64_imm_alt:
                reg[r_a] = rori64_jit(v_x, w_b)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_32_imm:
                reg[r_a] = pvm_X_jit(rori32_jit(U32(w_b), U32(v_x)), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_32_imm_alt:
                reg[r_a] = pvm_X_jit(rori32_jit(U32(v_x), U32(w_b)), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.11
        elif inst_type == inst_reg_reg_offset:

            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            w_a = reg[r_a]
            w_b = reg[r_b]

            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 2, l_x), U8(l_x))

            if opcode == op_branch_eq:
                branch_result = branch_jit(pc, v_x, w_a == w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a == w_b:
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ne:
                branch_result = branch_jit(pc, v_x, w_a != w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a != w_b:
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_lt_u:
                branch_result = branch_jit(pc, v_x, w_a < w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a < w_b:
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_lt_s:
                branch_result = branch_jit(pc, v_x, pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8):
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ge_u:
                branch_result = branch_jit(pc, v_x, w_a >= w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a >= w_b:
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_branch_ge_s:
                branch_result = branch_jit(pc, v_x, pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8):
                    skip_len = v_x
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                # Invalid opcode
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.12
        elif inst_type == inst_reg_reg_imm_imm:
            r_a = min(12, code[pc + 1] % 16)
            r_b = code[pc + 1] // 16

            w_b = reg[r_b]

            l_x = min(4, code[pc + 2] % 8)
            v_x = pvm_X_jit(read_uint_jit(code, pc + 3, l_x), U8(l_x))

            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 2))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 3 + l_x, l_y), U8(l_y))

            if opcode == op_load_imm_jump_ind:
                reg[r_a] = v_x
                jump_target = (U64(w_b) + U64(v_y)) & U32_MASK
                djump_result = djump_jit(U32(jump_target), jump_table, pc, pc_to_inst_index)
                if djump_result == I32(-1):
                    skip_len = I64(0)
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_HALT, pc, gas, inst_nr, exit_value, skip_len, ERROR_NONE)
                elif djump_result == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_INVALID_DJUMP)
                else:
                    skip_len = djump_result
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
            else:
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.13
        elif inst_type == inst_reg_reg_reg:

            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            r_d = min(12, code[pc + 2])

            w_a = reg[r_a]
            w_b = reg[r_b]

            if opcode == op_add_32:
                wa_wb_32 = (U64(w_a) + U64(w_b)) & U32_MASK
                reg[r_d] = pvm_X_jit(U32(wa_wb_32), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_sub_32:
                wa_minus_wb_32 = (U64(w_a) - U64(w_b)) & U32_MASK
                reg[r_d] = pvm_X_jit(U32(wa_minus_wb_32), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_32:
                prod32 = (U64(w_a) * U64(w_b)) & U32_MASK
                reg[r_d] = pvm_X_jit(U32(prod32), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_div_u_32:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = pvm_X_jit(U32(w_a) // U32(w_b), U8(4))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_div_s_32:
                a_signed = I32(pvm_Z_jit((U64(w_a) & U32_MASK), 4))
                b_signed = I32(pvm_Z_jit((U64(w_b) & U32_MASK), 4))

                if b_signed == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                elif a_signed == I32(-2 ** 31) and b_signed == I32(-1):
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_rtz_div_jit(I64(a_signed), I64(b_signed)), U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rem_u_32:
                wb32 = U64(w_b) & U32_MASK
                if wb32 == 0:
                    reg[r_d] = pvm_X_jit(U32(U64(w_a) & U32_MASK), U8(4))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    wa32 = U64(w_a) & U32_MASK
                    reg[r_d] = pvm_X_jit(U32(wa32 % wb32), U8(4))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rem_s_32:
                a_signed = pvm_Z_jit((U64(w_a) & U32_MASK), 4)
                b_signed = pvm_Z_jit((U64(w_b) & U32_MASK), 4)

                if b_signed == 0:
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                elif a_signed == I64(-2 ** 31) and b_signed == I64(-1):
                    reg[r_d] = U64(0)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_smod_jit(a_signed, b_signed), U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_32:
                sh = U64(w_b) & U64(31)
                reg[r_d] = pvm_X_jit(U32((U64(w_a) << sh) & U32_MASK), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_32:
                reg[r_d] = pvm_X_jit(U32(w_a) >> U32(U32(w_b) & U32(31)), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_32:
                reg[r_d] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(w_a), 4)) >> I64(U32(w_b) & U32(31)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_add_64:
                reg[r_d] =(U64(w_a) + U64(w_b)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_sub_64:
                reg[r_d] = (U64(w_a) - U64(w_b)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_64:
                reg[r_d] = (U64(w_a) * U64(w_b)) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_div_u_64:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = w_a // w_b
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_div_s_64:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                elif pvm_Z_jit(w_a, 8) == I64(-9223372036854775808) and pvm_Z_jit(w_b, 8) == I64(-1):
                    reg[r_d] = w_a  # Overflow case
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_rtz_div_jit(pvm_Z_jit(w_a, 8), pvm_Z_jit(w_b, 8)), U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rem_u_64:
                if w_b == 0:
                    reg[r_d] = w_a
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = w_a % w_b
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rem_s_64:
                a_signed = pvm_Z_jit(w_a, 8)
                b_signed = pvm_Z_jit(w_b, 8)
                if b_signed == 0:
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                elif a_signed == I64(-9223372036854775808) and b_signed == I64(-1):
                    reg[r_d] = U64(0)
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_smod_jit(a_signed, b_signed), U8(8))
                    if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_l_64:
                sh = U64(w_b) & U64(63)
                reg[r_d] = (U64(w_a) << sh) & U64_MASK
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shlo_r_64:
                reg[r_d] = U64(w_a) >> U64(U64(w_b) & U64(63))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_shar_r_64:
                reg[r_d] = pvm_Z_inv_jit(I64(pvm_Z_jit(w_a, 8)) >> I64(U64(w_b) & U64(63)), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_and:
                reg[r_d] = w_a & w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_xor:
                reg[r_d] = w_a ^ w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_or:
                reg[r_d] = w_a | w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_upper_s_s:
                hi, lo = imul64wide_jit(I64(w_a), I64(w_b))
                reg[r_d] = pvm_Z_inv_jit(I64(hi), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_upper_u_u:
                hi, lo = umul64wide_jit(w_a, w_b)
                reg[r_d] = hi
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_mul_upper_s_u:
                hi, lo = smul_u64wide_jit(I64(w_a), w_b)
                reg[r_d] = pvm_Z_inv_jit(I64(hi), U8(8))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_lt_u:
                reg[r_d] = U64(1) if w_a < w_b else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_set_lt_s:
                reg[r_d] = U64(1) if pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8) else U64(0)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_cmov_iz:
                if w_b == 0:
                    reg[r_d] = w_a
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_cmov_nz:
                if w_b != 0:
                    reg[r_d] = w_a
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_l_64:
                reg[r_d] = roli64_jit(w_a, U64(w_b) & U64(63))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_l_32:
                reg[r_d] = pvm_X_jit(roli32_jit(U32(w_a), U32(U32(w_b) & U32(31))), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_64:
                reg[r_d] = rori64_jit(w_a, U64(w_b) & U64(63))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_rot_r_32:
                reg[r_d] = pvm_X_jit(rori32_jit(U32(w_a), U32(U32(w_b) & U32(31))), U8(4))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_and_inv:
                reg[r_d] = w_a & U64(~w_b)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_or_inv:
                reg[r_d] = w_a | U64(~w_b)
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_xnor:
                reg[r_d] = U64(~(w_a ^ w_b))
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_max:
                reg[r_d] = w_a if pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8) else w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_max_u:
                reg[r_d] = w_a if w_a >= w_b else w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_min:
                reg[r_d] = w_a if pvm_Z_jit(w_a, 8) <= pvm_Z_jit(w_b, 8) else w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            elif opcode == op_min_u:
                reg[r_d] = w_a if w_a <= w_b else w_b
                if logging: log(opcode_names, local_state, reg, section_arrays, mem_section_starts, mem_section_ends)

            else:
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr, exit_value, skip_len, ERROR_PANIC_TRAP)

    # Finally, copy local state to state output
    return sync_state_and_return(reg, registers_out, state_out, status, pc, gas, inst_nr, exit_value, skip_len, ERROR_NONE)


class PVMInterpreter:

    @staticmethod
    def alloc_memory(
        rom_start: int,
        rom_size: int,
        rom_contents: bytes,
        heap_start: int,
        heap_size: int,
        heap_contents: bytes,
        stack_start: int,
        stack_size: int,
        argument_start: int,
        argument_size: int,
        argument_contents: bytes,
    ) -> PVMMemory:
        mem = PVMMemory()
        mem.add_segment(rom_start, rom_size, MEM_R, rom_contents)
        mem.add_segment(heap_start, heap_size, MEM_W, heap_contents)
        mem.add_segment(stack_start, stack_size, MEM_W, bytes(stack_size))
        mem.add_segment(argument_start, argument_size, MEM_R, argument_contents)
        mem.heap_base = heap_start
        mem.heap_ptr = heap_start + heap_size
        mem.stack_base = stack_start
        return mem

    def __init__(self, program: PVMProgram, logger=None):

        self.name = program.name
        self.reg:npt.NDArray[U64] = np.zeros(13, dtype=U64)
        self.inst_nr:U32 = U32(0)
        self.pc:U32 = U32(0)
        self.opcode:int = 0
        self.skip_len: int = 0
        self.gas:I64 = I64(0)
        self.code:npt.NDArray[U8] = np.array(1, dtype=U8)
        self.code_size: U64 = U64(0)
        self.jump_table = []

        self.inst_bitmask: List[bool] = []
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []

        self.mem:PVMMemory = None
        self.status:int = ExitReason.resume.value
        self.exit_value:int = None

        # Initialize memory operation lookups
        self._init_mem_ops_lookup()

        # Initialize memory sections storage
        self.mem_sections = []
        self.mem_section_acl = []
        self.mem_section_access = []
        self.mem_section_starts = np.array([], dtype=U32)
        self.mem_section_ends = np.array([], dtype=U32)
        self.mem_section_size = np.array([], dtype=U32)

        self._mem_addr: int = -1

        self.pc = U32(0)
        self.gas = I64(0)
        self.name = program.name
        self.code:npt.NDArray[U8] = np.array(program.code.code, dtype=U8)
        self.code_size: U64 = U64(len(self.code))
        self.mem = program.memory
        self.jump_table = [x.value for x in program.code.jump_table]

        # Initialize memory sections from the PVMMemory object (just reference where possible)
        self._link_memory(program.memory)

        for idx, val in enumerate(program.registers):
            self.reg[idx] = U64(val)

        self.status = ExitReason.resume.value

        self.inst_bitmask: List[bool] = program.code.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []
        self.create_instruction_lookup()

        # Create typed List of opcode names (max opcode value is 230)
        # Initialize with "UNKNOWN" for all opcodes
        self.opcode_names = List()
        for i in range(231):
            self.opcode_names.append("UNKNOWN")

        self.log = None
        if logger:
            self.program = program
            from pyjamaz.pvm.debug_logger import PVMDebugLog
            logger_cls = PVMDebugLog
            self.log = logger_cls(pvm=self)
            self.log._pvm = self
            self.log._pvm_id = self.name
            for opcode_val, opcode_name in OpcodeNames.items():
                if opcode_name not in self.log.log_opcodes:
                    self.log.log_opcodes[opcode_name] = 0
                if opcode_val < len(self.opcode_names):
                    self.opcode_names[opcode_val] = str(opcode_name)



        # Note: native (jit) caches, which we sync this back to the python side
        self._prepare_jit_data()
        self._jit_mem_cache_dirty = True
        self._jit_section_starts_cache = None
        self._jit_section_ends_cache = None
        self._jit_section_arrays_cache = None
        self._jit_section_access_cache = None
        self._jit_acl_bitmaps_cache = None
        self._jit_acl_bitmaps_cache = None

        self.jump_table_array = np.array(self.jump_table, dtype=np.int32)

        # Prepare heap info (for sbrk)
        current_heap_end = self.mem_section_ends[1] if len(self.mem_section_ends) > 1 else 0
        self.heap_info = np.array([
            current_heap_end,  # current heap end
            self.mem_section_starts[2] if len(self.mem_section_starts) > 2 else 0xFFFFFFFF,  # next section start
            MEM_WRITABLE  # writable permission value
        ], dtype=np.uint64)


    def _link_memory(self, memory):
        # Store memory sections as numpy arrays with their boundaries
        mem_section_starts = []
        mem_section_ends = []  # This will use paged_tail, not size
        mem_section_size = []

        # Reset caches so we rebuild typed views on next invoke
        self.mem_sections = []
        self.mem_section_acl = []
        self.mem_section_access = []

        # Track which sections we've seen (by address) to avoid duplicates
        seen_addresses = set()

        # Access the actual memory sections (rom, heap, stack, args)
        for section in [memory._rom, memory._heap, memory._stack, memory._args]:
            if section:
                seen_addresses.add(section.address)
                contents = section.contents #_ensure_uint8_array(section.contents)
                self.mem_sections.append(contents)
                acl_bitmap = section.acl_bitmap #_ensure_uint64_array(section.acl_bitmap)
                self.mem_section_acl.append(acl_bitmap)
                self.mem_section_access.append(section.acl if hasattr(section, "acl") else None)
                mem_section_starts.append(section.address)
                mem_section_ends.append(section.paged_tail)
                mem_section_size.append(section.size)
            else:
                self.mem_sections.append(None)
                self.mem_section_acl.append(None)
                self.mem_section_access.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)

        # Note: Also include sections from memory.sections (fx for test fixtures that use map_section)
        if hasattr(memory, 'sections') and memory.sections:
            for section in memory.sections:
                if section and section.address not in seen_addresses:
                    seen_addresses.add(section.address)
                    contents = section.contents
                    self.mem_sections.append(contents)
                    acl_bitmap = section.acl_bitmap if hasattr(section, 'acl_bitmap') else None
                    self.mem_section_acl.append(acl_bitmap)
                    self.mem_section_access.append(section.acl if hasattr(section, "acl") else None)
                    mem_section_starts.append(section.address)
                    mem_section_ends.append(section.paged_tail)
                    mem_section_size.append(section.size)

        self.mem_section_starts = np.array(mem_section_starts, dtype=U32)
        self.mem_section_ends = np.array(mem_section_ends, dtype=U32)
        self.mem_section_size = np.array(mem_section_size, dtype=U32)
        self._jit_mem_cache_dirty = True
        self._jit_section_starts_cache = None
        self._jit_section_ends_cache = None
        self._jit_section_arrays_cache = None
        self._jit_section_access_cache = None


    def create_instruction_lookup(self):
        """
        Create lookups for byte_pos -> instruction_nr and instruction_nr->instruction_length
        """
        self.inst_pos = {0: 0}
        self.inst_arg_len = []

        inst_nr = 0
        inst_bitmask = self.inst_bitmask
        inst_bitmask_idx = 1

        # Note: In the exceptional case we only have 1 instruction (trap or fallthrough), we add it manually and be done
        if len(inst_bitmask) == 1:
            self.inst_arg_len.append(0)
            return

        # Parse instruction bitmask and create a opcode offset and instruction length lookup
        while inst_bitmask_idx < len(inst_bitmask):
            inst_args = 0

            is_opcode = False

            while not is_opcode:

                is_opcode = inst_bitmask[inst_bitmask_idx]
                if not is_opcode:
                    inst_args += 1

                inst_bitmask_idx += 1

                if inst_bitmask_idx > len(inst_bitmask) - 1:
                    is_opcode = True

            # GP-0.6.2-eq:A.19 (l)
            self.inst_arg_len.append(inst_args)
            inst_nr += 1
            # Note: only add to inst_pos if this position has an opcode in the bitmask
            if inst_bitmask_idx - 1 < len(inst_bitmask) and inst_bitmask[inst_bitmask_idx - 1]:
                self.inst_pos[inst_bitmask_idx - 1] = inst_nr


    def _prepare_jit_data(self):
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
        Build (or reuse) JIT-ready section references.
        Returns: section_starts, section_ends, section_arrays, section_access, acl_bitmaps
        """
        if (not self._jit_mem_cache_dirty and
                self._jit_section_arrays_cache is not None and
                self._jit_section_starts_cache is not None and
                self._jit_section_ends_cache is not None and
                self._jit_section_access_cache is not None and
                self._jit_acl_bitmaps_cache is not None):
            return (self._jit_section_starts_cache,
                    self._jit_section_ends_cache,
                    self._jit_section_arrays_cache,
                    self._jit_section_access_cache,
                    self._jit_acl_bitmaps_cache)

        starts = []
        ends = []
        arrays = List.empty_list(types.uint8[::1])
        access_values = []
        acl_bitmaps = List.empty_list(types.uint64[::1])

        for i, section in enumerate(self.mem_sections):
            if section is None:
                continue

            start_addr = np.uint64(self.mem_section_starts[i])
            end_addr = np.uint64(self.mem_section_ends[i])
            buf = section #_ensure_uint8_array(section)
            self.mem_sections[i] = buf

            acl_buf = self.mem_section_acl[i]
            if acl_buf is None:
                acl_arr = np.zeros(0, dtype=np.uint64)
            else:
                acl_arr = acl_buf #_ensure_uint64_array(acl_buf)
            self.mem_section_acl[i] = acl_arr

            starts.append(start_addr)
            ends.append(end_addr)
            arrays.append(buf)
            acl_bitmaps.append(acl_arr)
            access = self.mem_section_access[i]
            access_values.append(-1 if access is None else int(access))

        self._jit_section_starts_cache = np.asarray(starts, dtype=np.uint64)
        self._jit_section_ends_cache = np.asarray(ends, dtype=np.uint64)
        self._jit_section_arrays_cache = arrays
        self._jit_acl_bitmaps_cache = acl_bitmaps
        self._jit_section_access_cache = np.asarray(access_values, dtype=np.int32)
        self._jit_mem_cache_dirty = False

        return (self._jit_section_starts_cache,
                self._jit_section_ends_cache,
                self._jit_section_arrays_cache,
                self._jit_section_access_cache,
                self._jit_acl_bitmaps_cache)


    def _init_mem_ops_lookup(self):
        """Initialize memory operation lookups as numpy arrays for fast access"""
        # Create lookup arrays for memory operations
        self.mem_ops_bytes = np.zeros(256, dtype=U8)
        self.mem_ops_read = np.zeros(256, dtype=np.bool_)
        self.mem_ops_write = np.zeros(256, dtype=np.bool_)

        # Populate the lookup arrays from MemOps
        for opcode, ops in MemOps.items():
            self.mem_ops_bytes[opcode] = ops["bytes"]
            self.mem_ops_read[opcode] = ops["read"]
            self.mem_ops_write[opcode] = ops["write"]


    def _sync_memory(self):
        # Sync memory state back to original PVMMemory and MemorySection objects after execution
        if self.mem_sections and self.mem_section_starts[1]:
            self.mem._heap.contents = self.mem_sections[1]
            self.mem._heap.size = len(self.mem_sections[1])
            self.mem._heap.paged_tail = self.mem_section_ends[1]
            if self.mem_section_acl and len(self.mem_section_acl) > 1:
                self.mem._heap.acl_bitmap = self.mem_section_acl[1]
            self.mem._mem_addr = self._mem_addr



    def get_exit_condition(self) -> ExitCondition:
        exit_value = None
        exit_reason = self.status

        if self.status in (ExitReason.host_halt.value, ExitReason.page_fault.value):
            exit_value = self.exit_value
        elif self.status == ExitReason.halt.value:
            mem = bytes()
            try:
                mem = self.mem.read_bytes(self.reg[7], self.reg[8])
            except (PVMMemoryError, PanicError):
                pass
            exit_value = mem
        elif self.status == ExitReason.panic.value:
            exit_value = None
        else:
            exit_value = b''

        return ExitCondition(reason=ExitReason(exit_reason), value=exit_value)


    def next_instruction(self):
        inst_index = self.inst_pos[self.pc]
        return self.inst_arg_len[inst_index] + 1


    def get_registers(self):
        return [int(x) for x in self.reg]


    def invoke(self, pc: int, gas: int):
        """
        Pure JIT invoke that uses only Numba compilation.
        No fallback to Python interpreter.
        """
        self.pc = pc
        self.gas = gas

        # Note: re-link memory to pick up any sections added via map_section() after init
        self._link_memory(self.mem)

        # Prepare memory arrays for JIT
        mem_section_starts, mem_section_ends, section_arrays, section_access, acl_bitmaps = self._prepare_memory_for_jit()

        registers_out = np.zeros(13, dtype=np.uint64)
        # state_out holds: [status, pc, gas, inst_nr, exit_value, skip_len, error_code]
        state_out = np.array([0, 0, 0, 0, 0, 0, 0], dtype=np.int64)
        heap_grew_out = np.array([0], dtype=np.int64)

        # Call the Numba compiled invoke function
        prev_skip = int(self.skip_len) & U32_MASK

        error_code = invoke_native(
            np.uint32(self.pc),
            np.int64(self.gas),
            np.uint32(self.inst_nr),
            np.uint32(prev_skip),

            self.code,
            np.uint32(self.code_size),
            self.inst_arg_len_array,
            self.pc_to_inst_index,
            self.opcode_scheme_array,
            self.jump_table_array,

            mem_section_starts,
            mem_section_ends,
            section_arrays,
            acl_bitmaps,
            section_access,
            self.heap_info,

            self.reg,

            False,
            self.opcode_names,

            # Outputs
            registers_out,
            state_out,
            heap_grew_out
        )

        # Update state from outputs
        self.reg[:] = registers_out
        self.status = int(state_out[STATE_STATUS])
        pc_out_val = np.uint32(state_out[STATE_PC])
        self.exit_value = int(state_out[STATE_EXIT_VALUE])
        skip_len = int(state_out[STATE_SKIP_LEN])
        self.gas = int(state_out[STATE_GAS])
        self.inst_nr = np.uint32(state_out[STATE_INST_NR])
        # Advance PC only when there were no errors
        if error_code == ERROR_NONE:
            # Note: do not advance PC in case of a host-halt
            if self.status == ExitReason.host_halt.value:
                self.pc = pc_out_val
            else:
                pc_int = int(pc_out_val)
                new_pc = (pc_int + skip_len) & U32_MASK
                self.pc = np.uint32(new_pc)
        else:
            self.pc = pc_out_val
        self.skip_len = skip_len

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
            fault_addr = self.exit_value
            if fault_addr is not None and fault_addr >= 0:
                fault_addr = fault_addr - (fault_addr % PVM_PAGE_SIZE)
            self.exit_value = fault_addr
        elif error_code != ERROR_NONE:
            # Other errors cause panic
            self.status = ExitReason.panic.value

        # Update heap end pointer if it was modified by sbrk
        if len(self.mem_section_ends) > 1:
            self.mem_section_ends[1] = self.heap_info[0]

        # Always sync the heap buffer reference from the JIT to avoid losing writes.
        # growth_bytes = int(heap_grew_out[0])
        if section_arrays is not None and len(section_arrays) > 1:
            self.mem_sections[1] = section_arrays[1]
            self._jit_mem_cache_dirty = True
        if acl_bitmaps is not None and len(acl_bitmaps) > 1:
            self.mem_section_acl[1] = acl_bitmaps[1]
            self._jit_mem_cache_dirty = True

        self._sync_memory()
