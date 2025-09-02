
"""
JIT-optimized PVM interpreter with Numba-compiled invoke_native function.
"""

import numpy as np
import numpy.typing as npt

from numba import njit

from .interpreter_new3 import PVMInterpreter as PVMInterpreterBase
from .types_new import PVMProgram
from .constants_new import (
    ExitReason, OpcodeScheme, Opcode as op,

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
    # Additional JIT opcodes
    op_sub_imm, op_mul_imm, op_shlo_l_imm,
    op_rot_r_64_imm_alt, op_rot_r_32_imm, op_rot_r_32_imm_alt, op_branch_eq, op_branch_ne,
    op_branch_lt_u, op_branch_lt_s, op_branch_ge_u, op_branch_ge_s, op_load_imm_jump_ind,
    op_add_32, op_sub_32, op_mul_32, op_div_u_32, op_div_s_32, op_rem_u_32, op_rem_s_32,
    op_shlo_l_32, op_shlo_r_32, op_shar_r_32, op_add_64, op_sub_64, op_mul_64,
    op_div_u_64, op_div_s_64, op_rem_u_64, op_rem_s_64, op_shlo_l_64, op_shlo_r_64,
    op_shar_r_64, op_and, op_xor, op_or, op_mul_upper_s_s, op_mul_upper_u_u,
    op_mul_upper_s_u, op_set_lt_u, op_set_lt_s, op_cmov_iz, op_cmov_nz, op_rot_l_64,
    op_rot_l_32, op_rot_r_64, op_rot_r_32, op_and_inv, op_or_inv, op_xnor, op_max,
    op_max_u, op_min, op_min_u,

    inst_none, inst_imm, inst_reg_ext_imm, inst_imm_imm, inst_offset, inst_reg_imm,
    inst_reg_imm_imm, inst_reg_imm_offset, inst_reg_reg, inst_reg_reg_imm,
    inst_reg_reg_offset, inst_reg_reg_imm_imm, inst_reg_reg_reg, inst_undefined
)


# Error codes for the JIT function
ERROR_NONE = 0
ERROR_PANIC_TRAP = 1
ERROR_PANIC_INVALID_PC = 2
ERROR_PANIC_INVALID_BRANCH = 3
ERROR_PANIC_INVALID_DJUMP = 4
ERROR_INVALID_OPCODE = 5
ERROR_MEMORY_FAULT = 6

# Exit reasons (matching ExitReason enum)
EXIT_RESUME = 0
EXIT_HALT = 1
EXIT_PANIC = 2
EXIT_HOST_HALT = 3
EXIT_PAGE_FAULT = 4


U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64


@njit
def umul64wide(a: U64, b: U64):
    """Unsigned 64x64 -> (hi, lo) as uint64s."""
    mask32 = U64(0xFFFFFFFF)
    a_lo = a & mask32
    a_hi = a >> U64(32)
    b_lo = b & mask32
    b_hi = b >> U64(32)

    ll = a_lo * b_lo              # 64-bit
    lh = a_lo * b_hi
    hl = a_hi * b_lo
    hh = a_hi * b_hi

    carry   = (ll >> U64(32)) + (lh & mask32) + (hl & mask32)
    lo      = (ll & mask32) | ((carry & mask32) << U64(32))
    hi      = hh + (lh >> U64(32)) + (hl >> U64(32)) + (carry >> U64(32))
    return U64(hi), U64(lo)


@njit
def imul64wide(a: I64, b: I64):
    """Signed 64x64 -> (hi, lo) representing 128-bit two's-complement product."""
    ua = U64(a)   # reinterpret
    ub = U64(b)
    hi, lo = umul64wide(ua, ub)
    # Adjust high word for two's-complement signs (see Hacker's Delight)
    if a < 0:
        hi = U64(hi - ub)
    if b < 0:
        hi = U64(hi - ua)
    return U64(hi), U64(lo)


@njit
def smul_u64wide(a: I64, b: U64):
    """Signed * Unsigned -> (hi, lo), two's-complement."""
    ua = U64(a)
    hi, lo = umul64wide(ua, b)
    if a < 0:
        hi = U64(hi - b)
    return U64(hi), U64(lo)


@njit
def rori64_jit(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate right for 64-bit integers."""
    return U64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit
def roli64_jit(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate left for 64-bit integers."""
    return U64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit
def rori32_jit(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate right for 32-bit integers."""
    return U32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


@njit
def roli32_jit(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate left for 32-bit integers."""
    return U32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


@njit
def pvm_smod_jit(a: I64, b: I64) -> I64:
    """
    JIT-compiled signed modulo operation.

    Returns a % b with sign of a preserved.
    Special case: if b == 0, returns a.
    """
    if b == 0:
        return a

    if a >= 0:
        if b >= 0:
            return a % b
        else:
            return a % (-b)
    else:
        if b >= 0:
            return -((-a) % b)
        else:
            return -((-a) % (-b))


@njit
def pvm_rtz_div_jit(a: I64, b: I64) -> I64:
    """
    JIT-compiled truncated division (rounds toward zero).
    """
    if a >= 0:
        if b > 0:
            return a // b
        else:
            return -(a // (-b))
    else:
        if b > 0:
            return -((-a) // b)
        else:
            return (-a) // (-b)


@njit
def pvm_X_jit(x: U64, n: U64) -> U64:
    """JIT-compiled sign extension."""
    #TODO: cast nodig?
    x = U64(x)
    n = U64(n)

    if n == 1:
        masked = x & 0xFF
        if masked & 0x80:
            return U64(masked | 0xFFFFFFFFFFFFFF00)
        return U64(masked)
    elif n == 2:
        masked = x & 0xFFFF
        if masked & 0x8000:
            return U64(masked | 0xFFFFFFFFFFFF0000)
        return U64(masked)
    elif n == 3:
        masked = x & 0xFFFFFF
        if masked & 0x800000:
            return U64(masked | 0xFFFFFFFFFF000000)
        return U64(masked)
    elif n == 4:
        masked = x & 0xFFFFFFFF
        if masked & 0x80000000:
            return U64(masked | 0xFFFFFFFF00000000)
        return U64(masked)
    elif n == 5:
        masked = x & 0xFFFFFFFFFF
        if masked & 0x8000000000:
            return U64(masked | 0xFFFFFF0000000000)
        return U64(masked)
    elif n == 6:
        masked = x & 0xFFFFFFFFFFFF
        if masked & 0x800000000000:
            return U64(masked | 0xFFFF000000000000)
        return U64(masked)
    elif n == 7:
        masked = x & 0xFFFFFFFFFFFFFF
        if masked & 0x80000000000000:
            return U64(masked | 0xFF00000000000000)
        return U64(masked)
    elif n == 8:
        return U64(x & 0xFFFFFFFFFFFFFFFF)
    else:
        return U64(x)


@njit
def pvm_Z_jit(a: U64, n: U64) -> I64:
    """JIT-friendly unsigned->signed conversion for n bytes (1..8).
    Returns I64 with proper two's-complement sign extension without Python big-ints.
    """
    au = U64(a)
    nb = U64(n)
    width = nb << U64(3)  # bits = n * 8

    # Clamp n to [1,8]; if n>=8, interpret full 64-bit as signed
    if width >= U64(64):
        return I64(au)
    if width == U64(0):
        return I64(0)

    mask = (U64(1) << width) - U64(1)
    val = au & mask
    signbit = U64(1) << (width - U64(1))

    if (val & signbit) != U64(0):
        # Negative: extend the sign bit up to 64 bits
        extend_mask = U64(0xFFFFFFFFFFFFFFFF) ^ mask
        return I64(val | extend_mask)
    else:
        # Positive
        return I64(val)


#TODO: max_bits u8 maken?
@njit
def count_leading_zeroes_jit(value: U64, max_bits=64):
    """JIT-compiled count leading zeroes."""
    value = value & ((1 << max_bits) - 1)
    if value == 0:
        return max_bits

    count = 0
    test_bit = 1 << (max_bits - 1)

    while (value & test_bit) == 0 and count < max_bits:
        count += 1
        test_bit >>= 1

    return count


#TODO: max_bits u8 maken?
@njit
def count_trailing_zeroes_jit(value: U64, max_bits=64):
    """JIT-compiled count trailing zeroes."""
    if value == 0:
        return max_bits

    count = 0
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


@njit
def reverse_bytes_jit(x: U64) -> U64:
    """JIT-compiled reverse bytes."""
    result = U64(0)
    for i in range(8):
        byte = U64((x >> U64(i * 8)) & U64(0xFF))
        result |= U64(byte << U64((7 - i) * 8))
    return result


@njit
def read_uint_jit(code: npt.NDArray[U8], addr:U32, length:U8) -> U64:
    addr32 = U32(addr)      # wrap to 32-bit address space
    len8   = U8(length)

    if len8 == U8(0):
        return U64(0)

    if len8 == U8(1):
        return U64(code[U32(addr32)])

    if len8 == U8(2):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        return b0 | (b1 << U64(8))

    if len8 == U8(3):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16))

    if len8 == U8(4):
        b0 = U64(code[U32(addr32)])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        b3 = U64(code[U32(addr32 + U32(3))])
        return b0 | (b1 << U64(8)) | (b2 << U64(16)) | (b3 << U64(24))

    if len8 == U8(8):
        b0 = U64(code[U32(addr32 + U32(0))])
        b1 = U64(code[U32(addr32 + U32(1))])
        b2 = U64(code[U32(addr32 + U32(2))])
        b3 = U64(code[U32(addr32 + U32(3))])
        b4 = U64(code[U32(addr32 + U32(4))])
        b5 = U64(code[U32(addr32 + U32(5))])
        b6 = U64(code[U32(addr32 + U32(6))])
        b7 = U64(code[U32(addr32 + U32(7))])
        return (b0 | (b1 << U64(8))  | (b2 << U64(16)) |
                (b3 << U64(24)) | (b4 << U64(32)) |
                (b5 << U64(40)) | (b6 << U64(48)) |
                (b7 << U64(56)))

    raise Exception("read_uint: unsupported length")


@njit
def riscv_div_jit(a: I64, b: I64) -> I64:
    """JIT-compiled RISC-V division.""" 
    if b == 0:
        return -1
    return a // b


@njit
def pvm_Z_inv_jit(a: I64, n: U8) -> U64:
    """
    JIT-compiled transform signed to unsigned.
    """
    if n == 1:
        if a >= 0:
            return U64(a & 0xFF)
        return U64((a + (1 << 8)) & 0xFF)
    elif n == 2:
        if a >= 0:
            return U64(a & 0xFFFF)
        return U64((a + (1 << 16)) & 0xFFFF)
    elif n == 4:
        if a >= 0:
            return U64(a & 0xFFFFFFFF)
        return U64((a + I64(1 << 32)) & 0xFFFFFFFF)
    elif n == 8:
        return U64(a)
    else:
        shift = n << 3
        mask = (1 << shift) - 1
        if a >= 0:
            return U64(a & mask)
        return U64((a + (1 << shift)) & mask)


@njit
def find_memory_section_jit(addr: U64, section_starts, section_ends) -> I32:
    """JIT-compiled find memory section."""
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            return I32(i)
    return I32(-1)


@njit
def mem_write_jit(addr: U64, value: U64, bytes_to_write: U8, 
                  section_starts, section_ends, mem_sections_flat, mem_sections_offsets) -> I32:
    """JIT-compiled memory write."""
    # Find section
    section_idx = find_memory_section_jit(addr, section_starts, section_ends)
    if section_idx < 0:
        return I32(-1)  # Memory error
    
    section_start = U64(section_starts[section_idx])
    section_offset = addr - section_start
    section_data_start = U64(mem_sections_offsets[section_idx])
    
    # Convert bytes_to_write to U64 for calculations
    bytes_u64 = U64(bytes_to_write)
    
    # Apply modulus for values less than 8 bytes
    if bytes_u64 < U64(8):
        shift_amount = bytes_u64 * U64(8)
        mask = (U64(1) << shift_amount) - U64(1)
        value = value & mask

    # Convert to integers for array indexing
    base_idx = int(section_data_start + section_offset)

    # Write bytes in little-endian order
    if bytes_to_write == U8(1):
        mem_sections_flat[base_idx] = U8(value & U64(0xFF))
    elif bytes_to_write == U8(2):
        mem_sections_flat[base_idx] = U8(value & U64(0xFF))
        mem_sections_flat[base_idx + 1] = U8((value >> U64(8)) & U64(0xFF))
    elif bytes_to_write == U8(4):
        mem_sections_flat[base_idx] = U8(value & U64(0xFF))
        mem_sections_flat[base_idx + 1] = U8((value >> U64(8)) & U64(0xFF))
        mem_sections_flat[base_idx + 2] = U8((value >> U64(16)) & U64(0xFF))
        mem_sections_flat[base_idx + 3] = U8((value >> U64(24)) & U64(0xFF))
    elif bytes_to_write == U8(8):
        mem_sections_flat[base_idx] = U8(value & U64(0xFF))
        mem_sections_flat[base_idx + 1] = U8((value >> U64(8)) & U64(0xFF))
        mem_sections_flat[base_idx + 2] = U8((value >> U64(16)) & U64(0xFF))
        mem_sections_flat[base_idx + 3] = U8((value >> U64(24)) & U64(0xFF))
        mem_sections_flat[base_idx + 4] = U8((value >> U64(32)) & U64(0xFF))
        mem_sections_flat[base_idx + 5] = U8((value >> U64(40)) & U64(0xFF))
        mem_sections_flat[base_idx + 6] = U8((value >> U64(48)) & U64(0xFF))
        mem_sections_flat[base_idx + 7] = U8((value >> U64(56)) & U64(0xFF))
    else:
        return I32(-1)  # Invalid bytes_to_write
        
    return I32(0)  # Success


@njit
def mem_read_jit(addr: U64, bytes_to_read: U8,
                 section_starts, section_ends, mem_sections_flat, mem_sections_offsets) -> U64:
    """JIT-compiled memory read."""
    # Find section
    section_idx = find_memory_section_jit(addr, section_starts, section_ends)
    if section_idx < 0:
        return U64(0xFFFFFFFFFFFFFFFF)  # Error marker
    
    section_start = U64(section_starts[section_idx])
    section_offset = addr - section_start
    section_data_start = U64(mem_sections_offsets[section_idx])
    
    # Convert to integer for array indexing
    base_idx = int(section_data_start + section_offset)
    
    # Read bytes in little-endian order
    if bytes_to_read == U8(1):
        return U64(mem_sections_flat[base_idx])
    elif bytes_to_read == U8(2):
        return (U64(mem_sections_flat[base_idx]) |
                (U64(mem_sections_flat[base_idx + 1]) << U64(8)))
    elif bytes_to_read == U8(4):
        return (U64(mem_sections_flat[base_idx]) |
                (U64(mem_sections_flat[base_idx + 1]) << U64(8)) |
                (U64(mem_sections_flat[base_idx + 2]) << U64(16)) |
                (U64(mem_sections_flat[base_idx + 3]) << U64(24)))
    elif bytes_to_read == U8(8):
        return (U64(mem_sections_flat[base_idx]) |
                (U64(mem_sections_flat[base_idx + 1]) << U64(8)) |
                (U64(mem_sections_flat[base_idx + 2]) << U64(16)) |
                (U64(mem_sections_flat[base_idx + 3]) << U64(24)) |
                (U64(mem_sections_flat[base_idx + 4]) << U64(32)) |
                (U64(mem_sections_flat[base_idx + 5]) << U64(40)) |
                (U64(mem_sections_flat[base_idx + 6]) << U64(48)) |
                (U64(mem_sections_flat[base_idx + 7]) << U64(56)))
    else:
        return U64(0xFFFFFFFFFFFFFFFF)  # Error marker


@njit
def sync_state_and_return(reg, registers_out, status, status_out, pc, pc_out, 
                         gas, gas_out, inst_nr, inst_nr_out, exit_value, exit_value_out, error_code):
    """Helper function to sync state and return error code - reduces code duplication."""
    for i in range(len(reg)):
        registers_out[i] = reg[i]
    status_out[0] = status
    pc_out[0] = pc
    gas_out[0] = gas
    inst_nr_out[0] = inst_nr
    exit_value_out[0] = exit_value
    return error_code


@njit
def branch_jit(pc: U32, offset: I64, condition: bool, inst_pos_keys) -> I32:
    """JIT implementation of branch with validation."""
    if condition:
        target_pc = pc + offset
        # Check if target PC is valid
        found = False
        for i in range(len(inst_pos_keys)):
            if inst_pos_keys[i] == target_pc:
                found = True
                break
        
        if not found:
            return I32(-1)  # Invalid branch - panic
        
        return I32(offset)  # Valid branch
    else:
        return I32(0)  # No branch - continue


@njit
def djump_jit(a: U32, jump_table, pc: U32, inst_pos_keys) -> I32:
    """JIT implementation of djump with validation."""
    halt_value = U32(2**32 - 2**16)
    if a == halt_value:
        return I32(-1)  # Special return code for halt
    
    # Check various invalid conditions
    if (a == 0 or 
        a >= len(jump_table) * 4 or  # TODO: use constant PVM_DYNAMIC_ALIGNMENT_FACTOR = 4
        a % 4 != 0):
        return I32(-2)  # Invalid jump
        
    jump_idx = a // 4 - 1
    if jump_idx >= len(jump_table):
        return I32(-2)  # Invalid jump
        
    target_pc = jump_table[jump_idx]
    
    # Check if target_pc is in inst_pos_keys
    found = False
    for i in range(len(inst_pos_keys)):
        if inst_pos_keys[i] == target_pc:
            found = True
            break
    
    if not found:
        return I32(-2)  # Invalid jump
        
    return I32(target_pc - pc)  # Valid skip_len


@njit
def invoke_native(
        pc_start, gas_start,
        code, code_size,
        inst_pos_keys, inst_pos_vals, inst_arg_len,
        opcode_scheme, jump_table,
        mem_ops_read, mem_ops_write, mem_ops_bytes,
        mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets,
        registers_in,
        # Output parameters (modified in-place)
        registers_out,
        status_out, exit_value_out, pc_out, gas_out, inst_nr_out
):
    """
    JIT-compiled core interpreter loop.

    Returns:
        Error code (0 = success, >0 = specific error)
    """
    # Initialize local state
    pc = U32(pc_start)
    gas = I64(gas_start)
    status = EXIT_RESUME
    exit_value = I64(0)
    skip_len = 0
    inst_nr = U32(0)

    # Copy registers
    reg = registers_in.copy()

    # Main execution loop
    while status == EXIT_RESUME and gas > 0:
        # Calculate next PC but don't update yet
        next_pc = U32(pc + skip_len)
        
        if next_pc >= code_size:
            status = EXIT_PANIC
            break

        # Find instruction index at next PC
        inst_index = -1
        for i in range(len(inst_pos_keys)):
            if inst_pos_keys[i] == next_pc:
                inst_index = inst_pos_vals[i]
                break

        if inst_index < 0:
            # Can't find instruction - need to return with next_pc for Python to handle
            # Python will validate and handle the invalid PC appropriately
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            status_out[0] = status
            exit_value_out[0] = exit_value
            pc_out[0] = next_pc  # Return the problematic next_pc for Python to handle
            gas_out[0] = gas  # Return current gas
            inst_nr_out[0] = inst_nr  # Return current inst_nr
            return ERROR_PANIC_TRAP
        
        # Now we know we can proceed, so update state
        gas -= 1
        pc = next_pc
        inst_nr += 1

        # Fetch opcode and decode
        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = inst_arg_len[inst_index] + 1
        
        #GP-0.6.7-section:A.5.1
        if inst_type == inst_none:
            if opcode == op_trap:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out, 
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)
            elif opcode == op_fallthrough:
                pass
            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.2
        elif inst_type == inst_imm:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_X_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_ecalli:
                return sync_state_and_return(reg, registers_out, EXIT_HOST_HALT, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           v_x, exit_value_out, ERROR_NONE)
            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.3
        elif inst_type == inst_reg_ext_imm:
            r_a = min(12, code[pc + 1] % 16)
            v_x = read_uint_jit(code, pc + 2, 8)

            if opcode == op_load_imm_64:
                reg[r_a] = v_x
            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.4
        elif inst_type == inst_imm_imm:
            l_x = min(4, code[pc + 1] % 8)
            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), np.uint8(l_y))
            
            if opcode == op_store_imm_u8:
                if mem_write_jit(v_x, v_y % (2**8), U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
            elif opcode == op_store_imm_u16:
                if mem_write_jit(v_x, v_y % (2**16), U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
            elif opcode == op_store_imm_u32:
                if mem_write_jit(v_x, v_y % (2**32), U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
            elif opcode == op_store_imm_u64:
                if mem_write_jit(v_x, v_y, U8(8), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.5
        elif inst_type == inst_offset:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_jump:
                skip_len = v_x
            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.6
        elif inst_type == inst_reg_imm:
            r_a = min(12, code[pc + 1] % 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))

            if opcode == op_jump_ind:
                jump_target = U32(reg[r_a] + v_x)
                djump_result = djump_jit(jump_target, jump_table, pc, inst_pos_keys)
                if djump_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_HALT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_NONE)
                elif djump_result == I32(-2):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_DJUMP)
                else:
                    skip_len = djump_result

            elif opcode == op_load_imm:
                reg[r_a] = v_x

            elif opcode == op_load_u8:
                loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_load_i8:
                loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(1))

            elif opcode == op_load_u16:
                loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_load_i16:
                loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(2))

            elif opcode == op_load_u32:
                loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_load_i32:
                loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(4))

            elif opcode == op_load_u64:
                loaded_value = mem_read_jit(v_x, U8(8), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets)
                if loaded_value == U64(0xFFFFFFFFFFFFFFFF):
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_store_u8:
                if mem_write_jit(v_x, reg[r_a] % (2**8), U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_u16:
                if mem_write_jit(v_x, reg[r_a] % (2**16), U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_u32:
                if mem_write_jit(v_x, reg[r_a] % (2**32), U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_u64:
                if mem_write_jit(v_x, reg[r_a], U8(8), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        #GP-0.6.7-section:A.5.7
        elif inst_type == inst_reg_imm_imm:
            r_a = min(12, code[pc + 1] % 16)
            w_a = reg[r_a]
            
            l_x = min(4, (code[pc + 1] // 16) % 8)
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), U8(l_x))
            
            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), U8(l_y))
            
            if opcode == op_store_imm_ind_u8:
                store_addr = w_a + v_x
                if mem_write_jit(store_addr, v_y % (2**8), U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_imm_ind_u16:
                store_addr = w_a + v_x
                if mem_write_jit(store_addr, v_y % (2**16), U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_imm_ind_u32:
                store_addr = w_a + v_x
                if mem_write_jit(store_addr, v_y % (2**32), U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            elif opcode == op_store_imm_ind_u64:
                store_addr = w_a + v_x
                if mem_write_jit(store_addr, v_y, U8(8), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    return sync_state_and_return(reg, registers_out, EXIT_PAGE_FAULT, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_MEMORY_FAULT)

            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)
            
        #GP-0.6.7-section:A.5.8
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

            elif opcode == op_branch_eq_imm:
                branch_result = branch_jit(pc, v_y, w_a == v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_ne_imm:
                branch_result = branch_jit(pc, v_y, w_a != v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_lt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a < v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_le_u_imm:
                branch_result = branch_jit(pc, v_y, w_a <= v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_ge_u_imm:
                branch_result = branch_jit(pc, v_y, w_a >= v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_gt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a > v_x, inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_lt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) < pvm_Z_jit(v_x, 8), inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_le_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) <= pvm_Z_jit(v_x, 8), inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_ge_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) >= pvm_Z_jit(v_x, 8), inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            elif opcode == op_branch_gt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) > pvm_Z_jit(v_x, 8), inst_pos_keys)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                               pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                               exit_value, exit_value_out, ERROR_PANIC_INVALID_BRANCH)
                skip_len = branch_result

            else:
                return sync_state_and_return(reg, registers_out, EXIT_PANIC, status_out,
                                           pc, pc_out, gas, gas_out, inst_nr, inst_nr_out,
                                           exit_value, exit_value_out, ERROR_PANIC_TRAP)

        # Type 8: InstructionType.reg_reg
        elif inst_type == inst_reg_reg:
            r_d = min(12, code[pc + 1] % 16)
            r_a = min(12, code[pc + 1] // 16)

            if opcode == op_move_reg:
                reg[r_d] = reg[r_a]
            elif opcode == op_sbrk:
                # Heap allocation - fall back to Python for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_PANIC_TRAP
            elif opcode == op_count_set_bits_64:
                # Manual bit counting (np.bitwise_count not available in numba)
                val = reg[r_a]
                count = U64(0)
                for _ in range(64):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
            elif opcode == op_count_set_bits_32:
                val = U32(reg[r_a] % (2**32))
                count = U64(0)
                for _ in range(32):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
            elif opcode == op_leading_zero_bits_64:
                reg[r_d] = count_leading_zeroes_jit(reg[r_a])
            elif opcode == op_leading_zero_bits_32:
                reg[r_d] = count_leading_zeroes_jit(reg[r_a] % (2**32), 32)
            elif opcode == op_trailing_zero_bits_64:
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a])
            elif opcode == op_trailing_zero_bits_32:
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a] % (2**32), 32)
            elif opcode == op_sign_extend_8:
                reg[r_d] = pvm_X_jit(reg[r_a], U8(1))
            elif opcode == op_sign_extend_16:
                reg[r_d] = pvm_X_jit(reg[r_a], U8(2))
            elif opcode == op_zero_extend_16:
                reg[r_d] = reg[r_a] & U64(0xFFFF)
            elif opcode == op_reverse_bytes:
                reg[r_d] = reverse_bytes_jit(reg[r_a])
            else:
                # Fall back for unimplemented - copy state first
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_PANIC_TRAP

        # Type 9: InstructionType.reg_reg_imm
        elif inst_type == inst_reg_reg_imm:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            
            w_a = reg[r_a]
            w_b = reg[r_b]
            
            if opcode == op_load_ind_u64:
                # Memory operation - fall back to Python
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_PANIC_TRAP
            elif opcode == op_add_imm_32:
                reg[r_a] = pvm_X_jit((w_b + v_x) % (2 ** 32), np.uint8(4))
            elif opcode == op_and_imm:
                reg[r_a] = w_b & v_x
            elif opcode == op_xor_imm:
                reg[r_a] = w_b ^ v_x
            elif opcode == op_or_imm:
                reg[r_a] = w_b | v_x
            elif opcode == op_mul_imm_32:
                reg[r_a] = pvm_X_jit((w_b * v_x) % (2 ** 32), np.uint8(4))
            elif opcode == op_add_imm_64:
                reg[r_a] = (w_b + v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == op_mul_imm_64:
                reg[r_a] = (w_b * v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == op_shlo_l_imm_64:
                if v_x < 64:
                    reg[r_a] = (w_b << v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_a] = np.uint64(0)
            elif opcode == op_shlo_r_imm_64:
                if v_x < 64:
                    reg[r_a] = w_b >> v_x
                else:
                    reg[r_a] = np.uint64(0)
            elif opcode == op_shar_r_imm_64:
                v_x_clamped = min(v_x, 63)
                w_b_signed = pvm_Z_jit(w_b, 8)
                if w_b_signed >= 0:
                    reg[r_a] = w_b >> U64(v_x_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - v_x_clamped)
                    reg[r_a] = (w_b >> U64(v_x_clamped)) | sign_bits
            elif opcode == op_neg_add_imm_64:
                reg[r_a] = U64(v_x) + U64(-w_b)
            elif opcode == op_shlo_l_imm_alt_64:
                if w_b < 64:
                    reg[r_a] = (v_x << w_b) & U64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_a] = U64(0)
            elif opcode == op_shlo_r_imm_alt_64:
                if w_b < 64:
                    reg[r_a] = v_x >> w_b
                else:
                    reg[r_a] = U64(0)
            elif opcode == op_shar_r_imm_alt_64:
                w_b_clamped = min(w_b, 63)
                v_x_signed = pvm_Z_jit(v_x, 8)
                if v_x_signed >= 0:
                    reg[r_a] = v_x >> U64(w_b_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - w_b_clamped)
                    reg[r_a] = (v_x >> U64(w_b_clamped)) | sign_bits
            elif opcode == op_store_ind_u8:
                store_addr = w_b + v_x
                store_value = w_a % (2**8)
                if mem_write_jit(store_addr, store_value, U8(1), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    status = EXIT_PAGE_FAULT
                    for i in range(len(reg)):
                        registers_out[i] = reg[i]
                    status_out[0] = status
                    pc_out[0] = pc
                    gas_out[0] = gas
                    inst_nr_out[0] = inst_nr
                    return ERROR_MEMORY_FAULT
            elif opcode == op_store_ind_u16:
                store_addr = w_b + v_x
                store_value = w_a % (2**16)
                if mem_write_jit(store_addr, store_value, U8(2), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    status = EXIT_PAGE_FAULT
                    for i in range(len(reg)):
                        registers_out[i] = reg[i]
                    status_out[0] = status
                    pc_out[0] = pc
                    gas_out[0] = gas
                    inst_nr_out[0] = inst_nr
                    return ERROR_MEMORY_FAULT
            elif opcode == op_store_ind_u32:
                store_addr = w_b + v_x
                store_value = w_a % (2**32)
                if mem_write_jit(store_addr, store_value, U8(4), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    status = EXIT_PAGE_FAULT
                    for i in range(len(reg)):
                        registers_out[i] = reg[i]
                    status_out[0] = status
                    pc_out[0] = pc
                    gas_out[0] = gas
                    inst_nr_out[0] = inst_nr
                    return ERROR_MEMORY_FAULT
            elif opcode == op_store_ind_u64:
                store_addr = w_b + v_x
                if mem_write_jit(store_addr, w_a, U8(8), mem_section_starts, mem_section_ends, mem_sections_flat, mem_sections_offsets) < 0:
                    status = EXIT_PAGE_FAULT
                    for i in range(len(reg)):
                        registers_out[i] = reg[i]
                    status_out[0] = status
                    pc_out[0] = pc
                    gas_out[0] = gas
                    inst_nr_out[0] = inst_nr
                    return ERROR_MEMORY_FAULT
            else:
                # Fall back for unimplemented - copy state first
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_PANIC_TRAP
        
        # Type 10: InstructionType.reg_reg_offset
        elif inst_type == inst_reg_reg_offset:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 2, l_x), l_x)
            
            if opcode == op_branch_eq:
                if reg[r_a] == reg[r_b]:
                    skip_len = v_x
            elif opcode == op_branch_ne:
                if reg[r_a] != reg[r_b]:
                    skip_len = v_x
            elif opcode == op_branch_lt_u:
                if reg[r_a] < reg[r_b]:
                    skip_len = v_x
            elif opcode == op_branch_lt_s:
                a_signed = pvm_Z_jit(reg[r_a], 8)
                b_signed = pvm_Z_jit(reg[r_b], 8)
                if a_signed < b_signed:
                    skip_len = v_x
            elif opcode == op_branch_ge_u:
                if reg[r_a] >= reg[r_b]:
                    skip_len = v_x
            elif opcode == op_branch_ge_s:
                a_signed = pvm_Z_jit(reg[r_a], 8)
                b_signed = pvm_Z_jit(reg[r_b], 8)
                if a_signed >= b_signed:
                    skip_len = v_x
            else:
                # Fall back for unimplemented
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_PANIC_TRAP
        
        # Type 12: InstructionType.reg_reg_reg
        elif inst_type == inst_reg_reg_reg:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            r_d = min(12, code[pc + 2])

            w_a = reg[r_a]
            w_b = reg[r_b]

            if opcode == op_add_32:
                reg[r_d] = pvm_X_jit((w_a + w_b) % (2 ** 32), np.uint8(4))
            elif opcode == op_sub_32:
                reg[r_d] = pvm_X_jit((w_a + 2 ** 32 - (w_b % 2 ** 32)) % 2 ** 32, np.uint8(4))
            elif opcode == op_mul_32:
                reg[r_d] = pvm_X_jit((w_a * w_b) % (2 ** 32), np.uint8(4))
            elif opcode == op_add_64:
                reg[r_d] = (w_a + w_b) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == op_sub_64:
                # Perform modular subtraction without overflow
                if w_a >= w_b:
                    reg[r_d] = w_a - w_b
                else:
                    reg[r_d] = np.uint64(0xFFFFFFFFFFFFFFFF) - (w_b - w_a) + np.uint64(1)
            elif opcode == op_mul_64:
                reg[r_d] = (w_a * w_b) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == op_and:
                reg[r_d] = w_a & w_b
            elif opcode == op_xor:
                reg[r_d] = w_a ^ w_b
            elif opcode == op_or:
                reg[r_d] = w_a | w_b
            elif opcode == op_div_u_32:
                if (w_b % (2**32)) == 0:
                    reg[r_d] = pvm_X_jit(U64(0xFFFFFFFF), U8(4))
                else:
                    reg[r_d] = pvm_X_jit(U64(w_a % (2**32)) // U64(w_b % (2**32)), U8(4))
            elif opcode == op_div_s_32:
                # Signed 32-bit division
                a_signed = pvm_Z_jit(w_a % (2**32), 4)
                b_signed = pvm_Z_jit(w_b % (2**32), 4) 
                if b_signed == 0:
                    reg[r_d] = pvm_X_jit(U64(0xFFFFFFFF), U8(4))
                else:
                    result = pvm_rtz_div_jit(a_signed, b_signed)
                    reg[r_d] = pvm_X_jit(pvm_Z_inv_jit(result, U8(4)), U8(4))
            elif opcode == op_div_u_64:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)  # Division by zero
                else:
                    reg[r_d] = w_a // w_b
            elif opcode == op_div_s_64:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)  # Division by zero
                elif pvm_Z_jit(w_a, 8) == I64(-9223372036854775808) and pvm_Z_jit(w_b, 8) == I64(-1):
                    reg[r_d] = w_a  # Overflow case: -2^63 / -1 = -2^63 (overflow)
                else:
                    # Normal signed division using truncated division
                    reg[r_d] = pvm_Z_inv_jit(pvm_rtz_div_jit(pvm_Z_jit(w_a, 8), pvm_Z_jit(w_b, 8)), U8(8))
            elif opcode == op_rem_u_32:
                if (w_b % (2**32)) == 0:
                    reg[r_d] = pvm_X_jit(w_a % (2**32), U8(4))
                else:
                    reg[r_d] = pvm_X_jit((w_a % (2**32)) % (w_b % (2**32)), U8(4))
            elif opcode == op_shlo_r_32:
                shift_amount = U32(w_b & U64(31))  # Clamp to 0-31 range
                shifted_value = U32(w_a) >> shift_amount
                reg[r_d] = pvm_X_jit(U64(shifted_value), U8(4))
            elif opcode == op_shlo_l_64:
                shift_amount = w_b % 64
                if shift_amount < 64:
                    reg[r_d] = (w_a << shift_amount) & U64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_d] = U64(0)
            elif opcode == op_shlo_r_64:
                reg[r_d] = w_a >> U64(w_b & U64(63))
            elif opcode == op_shar_r_64:
                w_b_clamped = min(w_b % 64, 63)
                w_a_signed = pvm_Z_jit(w_a, 8)
                if w_a_signed >= 0:
                    reg[r_d] = w_a >> U64(w_b_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - w_b_clamped)
                    reg[r_d] = (w_a >> U64(w_b_clamped)) | sign_bits
            elif opcode == op_and:
                reg[r_d] = w_a & w_b
            elif opcode == op_xor:
                reg[r_d] = w_a ^ w_b
            elif opcode == op_or:
                reg[r_d] = w_a | w_b
            elif opcode == op_set_lt_u:
                reg[r_d] = U64(1) if w_a < w_b else U64(0)
            elif opcode == op_set_lt_s:
                reg[r_d] = U64(1) if pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8) else U64(0)
            elif opcode == op_rot_l_64:
                reg[r_d] = roli64_jit(w_a, w_b % 64)
            elif opcode == op_rot_r_64:
                reg[r_d] = rori64_jit(w_a, w_b % 64)
            elif opcode == op_and_inv:
                reg[r_d] = U64(~(w_a & w_b))
            else:
                # Fall back for unimplemented - copy state first
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_PANIC_TRAP
        elif inst_type == inst_undefined: #TODO!!!!!!!!!!!!HUH?>????????
            # Undefined opcode - should halt
            status = EXIT_HALT
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            status_out[0] = status
            exit_value_out[0] = exit_value
            pc_out[0] = pc
            gas_out[0] = gas
            inst_nr_out[0] = inst_nr
            return ERROR_NONE
        else:
            # Unsupported instruction type - fall back to Python
            # Return state BEFORE this instruction (Python will execute it)
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            status_out[0] = status
            exit_value_out[0] = exit_value
            pc_out[0] = pc  # PC already points to current instruction
            gas_out[0] = gas + 1  # Return gas before decrement
            inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
            return ERROR_PANIC_TRAP

    # Copy output state
    for i in range(len(reg)):
        registers_out[i] = reg[i]
    status_out[0] = status
    exit_value_out[0] = exit_value
    pc_out[0] = pc + skip_len  # Return next PC
    gas_out[0] = gas
    inst_nr_out[0] = inst_nr

    return ERROR_NONE


class PVMInterpreter(PVMInterpreterBase):
    """
    Pure JIT-optimized PVM interpreter using Numba compilation only.
    No fallback to Python interpreter.
    """

    def __init__(self, program: PVMProgram, logger_cls=None):
        """Initialize the interpreter with a program."""
        super().__init__(program, logger_cls)
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
            self.opcode_scheme_array[opcode] = scheme
            
    def _prepare_memory_for_jit(self):
        """Prepare memory sections as flat arrays for JIT access."""
        if not self.mem_sections:
            return np.array([], dtype=np.uint8), np.array([], dtype=np.uint32)
            
        # Calculate total memory size and create offsets
        total_size = 0
        offsets = []
        for section in self.mem_sections:
            offsets.append(total_size)
            total_size += len(section) if section is not None else 0
            
        # Create flat array
        flat_memory = np.zeros(total_size, dtype=np.uint8)
        current_offset = 0
        for i, section in enumerate(self.mem_sections):
            if section is not None:
                section_size = len(section)
                flat_memory[current_offset:current_offset + section_size] = section[:]
                current_offset += section_size
        
        return flat_memory, np.array(offsets, dtype=np.uint32)
    
    def _update_memory_from_jit(self, mem_sections_flat, mem_sections_offsets):
        """Update memory sections from flat array after JIT execution."""
        current_offset = 0
        for i, section in enumerate(self.mem_sections):
            if section is not None:
                section_size = len(section)
                section[:] = mem_sections_flat[current_offset:current_offset + section_size]
                current_offset += section_size

    def invoke(self, pc: int, gas: int):
        """
        Pure JIT invoke that uses only Numba compilation.
        No fallback to Python interpreter.
        """
        self.pc = pc
        self.gas = gas

        jump_table_array = np.array(self.jump_table, dtype=np.int32)

        # Prepare memory arrays for JIT
        mem_sections_flat, mem_sections_offsets = self._prepare_memory_for_jit()

        # TODO: kan dit efficienter / buiten de loop??
        # Prepare output arrays
        registers_out = np.zeros(13, dtype=np.uint64)
        status_out = np.array([0], dtype=np.int32)
        exit_value_out = np.array([0], dtype=np.int64)
        pc_out = np.array([0], dtype=np.uint32)
        gas_out = np.array([0], dtype=np.int64)
        inst_nr_out = np.array([0], dtype=np.uint32)

        # Call JIT-compiled function
        error_code = invoke_native(
            self.pc, self.gas,
            self.code, self.code_size,
            self.inst_pos_keys, self.inst_pos_vals, self.inst_arg_len_array,
            self.opcode_scheme_array, jump_table_array,
            self.mem_ops_read, self.mem_ops_write, self.mem_ops_bytes,
            self.mem_section_starts, self.mem_section_ends, mem_sections_flat, mem_sections_offsets,
            self.reg,
            # Outputs
            registers_out, status_out, exit_value_out,
            pc_out, gas_out, inst_nr_out
        )

        # Update state from outputs
        self.reg[:] = registers_out
        self.status = status_out[0]
        self.exit_value = exit_value_out[0]
        old_pc = self.pc
        self.pc = pc_out[0]

        self.gas = gas_out[0]
        self.inst_nr += inst_nr_out[0]

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

        # Update memory sections from flat array
        self._update_memory_from_jit(mem_sections_flat, mem_sections_offsets)
