import numpy as np
import numpy.typing as npt

import struct
from typing import List, Dict

from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
from .types import PVMProgram, PVMMemory, PVMMemoryMode

from .constants import (
    ExitReason,
    MemOps,
    OpcodeNames,
    ExitCondition,
    PVM_PAGE_SIZE,

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
    op_max_u, op_min, op_min_u,
)

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR


# Numpy aliasses
U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64

# Python coercing helpers (should refactor to coresponding numpy types for native)
MASK8 = (1 << 8) - 1
MASK16 = (1 << 16) - 1
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1
SIGN8 = 1 << 7
SIGN16 = 1 << 15
SIGN32 = 1 << 31
SIGN64 = 1 << 63


def u8(x: int) -> int:
    x = int(x)
    return x & MASK8

def s8(x: int) -> int:
    x = int(x)
    x &= MASK8
    return x - (1 << 8) if x & SIGN8 else x

def u16(x: int) -> int:
    x = int(x)
    return x & MASK16

def s16(x: int) -> int:
    x = int(x)
    x &= MASK16
    return x - (1 << 16) if x & SIGN16 else x

def u32(x: int) -> int:
    x = int(x)
    return x & MASK32

def s32(x: int) -> int:
    x = int(x)
    x &= MASK32
    return x - (1 << 32) if x & SIGN32 else x

def u64(x: int) -> int:
    x = int(x)
    return x & MASK64

def s64(x: int) -> int:
    x = int(x)
    x &= MASK64
    return x - (1 << 64) if x & SIGN64 else x


# Pvm helper functions:
def rori64(x, shift_amount):
    x = int(x)
    shift_amount = int(shift_amount) & 63
    return ((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF


def roli64(x, shift_amount):
    x = int(x)
    shift_amount = int(shift_amount) & 63
    return ((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF


def rotl32(x, s):
    s = int(s) & 31
    x = int(x) & MASK32
    return ((x << s) | (x >> (32 - s))) & MASK32

def rotr32(x, s):
    s = int(s) & 31
    x = int(x) & MASK32
    return ((x >> s) | (x << (32 - s))) & MASK32

def rori32(x, shift_amount):
    x = int(x)
    shift_amount = int(shift_amount) & 31
    return ((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF


def roli32(x, shift_amount):
    x = int(x)
    shift_amount = int(shift_amount) & 31
    return ((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF


def reverse_bytes(x):
    """
    Reverse the byte order of a 64-bit integer (endianness swap).

    Converts between big-endian and little-endian representations.
    Example: 0x0123456789ABCDEF -> 0xEFCDAB8967452301

    Note:
        Optimized using Python's built-in bytes operations.
        Provides ~4x speedup over bitwise operations.
    """
    return struct.unpack('<Q', struct.pack('>Q', x))[0]


def count_trailing_zeroes(value, max_bits=64):
    # https://stackoverflow.com/a/63552117
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    value = int(value)
    if value == 0:
        return max_bits
    return int(value & -value).bit_length() - 1


def count_leading_zeroes(value, max_bits=64):
    # https://stackoverflow.com/a/71888844
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    value = int(value)
    value &= (1 << max_bits) - 1  # truncate; treat negatives as 2's compliment
    if value == 0:
        return max_bits
    significant_bits = len(bin(value)) - 2  # has "0b" prefix
    return max_bits - significant_bits


def pvm_smod(a: int, b: int) -> int:
    """
    Signed modulo operation optimized using conditional branching
    to avoid function call overhead.

    Returns a % b with sign of a preserved.
    Special case: if b == 0, returns a.

    Note:
        Optimized using conditional branching instead of abs() and sign functions
        for ~18% performance improvement.
    """
    if b == 0:
        return a

    # Use conditional branching to avoid abs() function calls
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


def pvm_rtz_div(a: int, b: int) -> int:
    """
    Truncated division (rounds toward zero).

    Returns the quotient of a/b rounded toward zero.
    Examples: 7/3=2, -7/3=-2, 7/-3=-2, -7/-3=2

    Note:
        Optimized using conditional branching to avoid abs() and divmod() overhead.
        Provides ~1.4x speedup while maintaining exact correctness for all integer values.
        This approach avoids floating point precision issues with very large integers.
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


def pvm_X(x: int, n: int) -> int:
    """
    Sign extend a number to two's complement form for value X and number of bytes n

    Optimized version using bit operations.
    """
    # Optimized sign extension for each n
    if n == 1:
        masked = x & 0xFF
        if masked & 0x80:  # Check sign bit
            return masked | 0xFFFFFFFFFFFFFF00
        return masked
    elif n == 2:
        masked = x & 0xFFFF
        if masked & 0x8000:  # Check sign bit
            return masked | 0xFFFFFFFFFFFF0000
        return masked
    elif n == 3:
        masked = x & 0xFFFFFF
        # Check if sign bit (bit 23) is set
        if masked & 0x800000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFFFFFF000000
        else:
            # Positive
            return masked
    elif n == 4:
        masked = x & 0xFFFFFFFF
        if masked & 0x80000000:  # Check sign bit
            return masked | 0xFFFFFFFF00000000
        return masked
    elif n == 5:
        masked = x & 0xFFFFFFFFFF
        # Check if sign bit (bit 39) is set
        if masked & 0x8000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFFFF0000000000
        else:
            # Positive
            return masked
    elif n == 6:
        masked = x & 0xFFFFFFFFFFFF
        # Check if sign bit (bit 47) is set
        if masked & 0x800000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFFFF000000000000
        else:
            # Positive
            return masked
    elif n == 7:
        masked = x & 0xFFFFFFFFFFFFFF
        # Check if sign bit (bit 55) is set
        if masked & 0x80000000000000:
            # Negative - sign extend to 64 bits
            return masked | 0xFF00000000000000
        else:
            # Positive
            return masked
    elif n == 8:
        return x & 0xFFFFFFFFFFFFFFFF
    else:
        return x


def pvm_Z(a: int, n: int) -> int:
    """
    Interpret the low n bytes of `a` as a signed two's-complement integer.
    """
    if n <= 0:
        return 0
    a = int(a)
    bits = n * 8
    mask = (1 << bits) - 1
    sign = 1 << (bits - 1)
    u = a & mask
    return (u ^ sign) - sign


def pvm_Z_inv(a: int, n: int) -> int:
    if n <= 0:
        return 0
    bits = n * 8
    mask = (1 << bits) - 1
    return u64(a) & mask


def read_uint(mem, addr, n):
    if n == 0:
        return 0 & 0xFF
    if n == 1:
        return mem[addr]
    elif n == 2:
        return struct.unpack_from('<H', mem, addr)[0]
    elif n == 4:
        return struct.unpack_from('<I', mem, addr)[0]
    elif n == 8:
        return struct.unpack_from('<Q', mem, addr)[0]
    elif n == 3:
        # Safely read 3 bytes without requiring 4-byte availability
        lo = struct.unpack_from('<H', mem, addr)[0]
        hi = struct.unpack_from('<B', mem, addr + 2)[0]
        return lo | (hi << 16)

    raise Exception("read_uint: unsupported length")


def _op_invalid(vm):
    raise InvalidOpcode(f"Invalid opcode: {vm.opcode}")

def _op_trap(vm):
    vm.log and vm.log()
    raise PanicError("trap")


def _op_fallthrough(vm):
    vm.log and vm.log()
    return


def _op_ecalli(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.inst_arg_len[inst_index]))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 1, l_x), l_x)
    vm.status = ExitReason.host_halt.value
    vm.exit_value = v_x
    vm.log and vm.log(imm1=v_x)


def _op_load_imm_64(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    v_x = read_uint(vm.mv_code, vm.pc + 2, 8)
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_jump(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.inst_arg_len[inst_index]))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 1, l_x), l_x)
    vm.skip_len = v_x
    vm.log and vm.log(off1=v_x, context={"skip_len": v_x})


def _op_jump_ind(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.skip_len = vm.djump(u32(int(vm.reg[r_a]) + int(v_x)))
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"skip_len": vm.skip_len})


def _op_load_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x)


# ---- reg_imm_offset (load_imm_jump + conditional branches with immediate) ----

def _op_load_imm_jump(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    # length encoded in the upper nibble (bits 4-6), per legacy interpreter
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    # Parity with legacy: set skip_len directly and then write reg
    vm.skip_len = v_y
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_eq_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a == v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_ne_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a != v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_lt_u_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a < v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_le_u_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a <= v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_ge_u_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a >= v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_gt_u_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, w_a > v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_lt_s_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, pvm_Z(w_a, 8) < pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_le_s_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, pvm_Z(w_a, 8) <= pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_ge_s_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, pvm_Z(w_a, 8) >= pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


def _op_branch_gt_s_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.branch(v_y, pvm_Z(w_a, 8) > pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)


# ---- reg_reg_offset (branches with two registers) ----

def _op_branch_eq(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, w_a == w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


def _op_branch_ne(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, w_a != w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


def _op_branch_lt_u(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, w_a < w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


def _op_branch_lt_s(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, pvm_Z(w_a, 8) < pvm_Z(w_b, 8))
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


def _op_branch_ge_u(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, w_a >= w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


def _op_branch_ge_s(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.branch(v_x, pvm_Z(w_a, 8) >= pvm_Z(w_b, 8))
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)


# ---- reg_reg_imm (loads/stores indirect, 32/64-bit immediates, cmovs, rotates) ----

def _fetch_reg_reg_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, max(0, vm.inst_arg_len[inst_index] - 1)))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    return r_a, r_b, w_a, w_b, v_x


def _op_store_ind_u8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u8, u32(int(w_b) + int(v_x)), u8(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u8(w_a), "w_b": w_b})


def _op_store_ind_u16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u16, u32(int(w_b) + int(v_x)), u16(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u16(w_a), "w_b": w_b})


def _op_store_ind_u32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u32, u32(int(w_b) + int(v_x)), u32(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u32(w_a), "w_b": w_b})


def _op_store_ind_u64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u64, u32(int(w_b) + int(v_x)), w_a)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_u8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u8, u32(int(w_b) + int(v_x)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_i8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i8, u32(int(w_b) + int(v_x))), 1), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_u16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u16, u32(int(w_b) + int(v_x)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_i16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i16, u32(int(w_b) + int(v_x))), 2), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_u32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u32, u32(int(w_b) + int(v_x)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_i32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i32, u32(int(w_b) + int(v_x))), 4), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_load_ind_u64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u64, u32(int(w_b) + int(v_x)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})


def _op_add_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(w_b) + int(v_x)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_and_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b & v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_xor_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b ^ v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_or_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b | v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_mul_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(w_b) * int(v_x)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_set_lt_u_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if w_b < v_x else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_set_lt_s_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if pvm_Z(w_b, 8) < pvm_Z(v_x, 8) else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_shlo_l_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(w_b) << (int(v_x) & 31)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_shlo_r_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(w_b)) >> (int(v_x) & 31), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})


def _op_shar_r_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(int(w_b) & MASK32, 4) >> (int(v_x) & 31), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_neg_add_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(v_x) + (1 << 32) - int(w_b)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_set_gt_u_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if w_b > v_x else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_set_gt_s_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if pvm_Z(w_b, 8) > pvm_Z(v_x, 8) else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_l_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(v_x) << (int(w_b) & 31)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_r_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(int(v_x)) >> (int(w_b) & 31), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shar_r_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    shift = int(w_b) & 31
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(v_x & 0xFFFFFFFF, 4) >> shift, 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_cmov_iz_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    if w_b == 0:
        vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_cmov_nz_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    if w_b != 0:
        vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_add_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = u64(int(w_b) + int(v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_mul_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = u64(int(w_b) * int(v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_l_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X((int(w_b) << (int(v_x) & 63)), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_r_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(int(w_b) >> (int(v_x) & 63), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shar_r_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(int(w_b), 8) >> (int(v_x) & 63), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_neg_add_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = ((int(v_x) + (1 << 64) - int(w_b)) & MASK64)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_l_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = (int(v_x) << (int(w_b) & 63)) & MASK64
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shlo_r_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = int(v_x) >> (int(w_b) & 63)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_shar_r_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    signed_val = pvm_Z(v_x, 8)
    shift_amount = int(w_b & 63)
    shifted = signed_val >> shift_amount
    if shifted < 0:
        shifted = shifted + (1 << 64)
    vm.reg[r_a] = shifted & MASK64
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_rot_r_64_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = rori64(int(w_b), int(v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_rot_r_64_imm_alt(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = rori64(int(v_x), int(w_b))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_rot_r_32_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(rori32(int(w_b), int(v_x)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


def _op_rot_r_32_imm_alt(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(rori32(int(v_x), int(w_b)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})


# ---- reg_reg_reg (binary ALU ops and shifts/rotates) ----

def _fetch_reg_reg_reg(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    r_d = min(12, vm.code[vm.pc + 2])
    a = int(vm.reg[r_a])
    b = int(vm.reg[r_b])
    return r_a, r_b, r_d, a, b


def _op_add_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a + b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_sub_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a + (1 << 32) - u32(b)), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_mul_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a * b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_div_u_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    else:
        vm.reg[r_d] = pvm_X(u32(a) // u32(b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_div_s_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s32 = pvm_Z(u32(a), 4)
    b_s32 = pvm_Z(u32(b), 4)
    if b_s32 == 0:
        vm.reg[r_d] = (1 << 64) - 1
    elif a_s32 == -(1 << 31) and b_s32 == -1:
        vm.reg[r_d] = pvm_Z_inv(a_s32, 8)
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_rtz_div(a_s32, b_s32), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rem_u_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if (b & MASK32) == 0:
        vm.reg[r_d] = pvm_X(a & MASK32, 4)
    else:
        vm.reg[r_d] = pvm_X((a & MASK32) % (b & MASK32), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rem_s_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s32 = pvm_Z(u32(a), 4)
    b_s32 = pvm_Z(u32(b), 4)
    if b_s32 == 0:
        vm.reg[r_d] = pvm_Z_inv(a_s32, 8)
    elif a_s32 == -(1 << 31) and b_s32 == -1:
        vm.reg[r_d] = 0
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_smod(a_s32, b_s32), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shlo_l_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X((a << (b & 31)) & MASK32, 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shlo_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X((a & MASK32) >> (b & 31), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shar_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    val_32 = a & MASK32
    if val_32 >= (1 << 31):
        val_32 = val_32 - (1 << 32)
    result = val_32 >> (b & 31)
    if result < 0:
        result = result + (1 << 64)
    vm.reg[r_d] = pvm_Z_inv(result, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_sub_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a + (1 << 64) - b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_mul_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a * b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_div_u_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    else:
        vm.reg[r_d] = a // b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_div_s_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    elif pvm_Z(a, 8) == -(1 << 63) and pvm_Z(b, 8) == -1:
        vm.reg[r_d] = a
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_rtz_div(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rem_u_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = a
    else:
        vm.reg[r_d] = a % b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rem_s_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s64 = pvm_Z(a, 8)
    b_s64 = pvm_Z(b, 8)
    if b == 0:
        vm.reg[r_d] = a
    elif a_s64 == -(1 << 63) and b_s64 == -1:
        vm.reg[r_d] = 0
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_smod(a_s64, b_s64), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shlo_l_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a << (b & 63))
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shlo_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a >> (b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_shar_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    signed_val = pvm_Z(a, 8)
    shifted = signed_val >> (b & 63)
    vm.reg[r_d] = pvm_Z_inv(shifted, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_and(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a & b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_xor(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a ^ b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_or(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a | b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_mul_upper_s_s(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv((pvm_Z(a, 8) * pvm_Z(b, 8)) >> 64, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_mul_upper_u_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = (a * b) >> 64
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_mul_upper_s_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv((pvm_Z(a, 8) * b) >> 64, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_set_lt_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a < b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_set_lt_s(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(pvm_Z(a, 8) < pvm_Z(b, 8))
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_cmov_iz(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = a
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_cmov_nz(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b != 0:
        vm.reg[r_d] = a
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rot_l_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = roli64(a, b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rot_l_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(rotl32(a, b), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rot_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = rori64(a, b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_rot_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(rotr32(a, b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_and_inv(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a & u64(~b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_or_inv(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a | u64(~b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_xnor(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = ~(a ^ b) & MASK64
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_max(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(max(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_max_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = max(a, b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_min(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(min(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_min_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = min(a, b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_load_u8(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = vm.mem_read(op_load_u8, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_i8(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i8, v_x), 1)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_u16(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = vm.mem_read(op_load_u16, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_i16(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i16, v_x), 2)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_u32(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = vm.mem_read(op_load_u32, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_i32(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i32, v_x), 4)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_u64(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.reg[r_a] = vm.mem_read(op_load_u64, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_store_u8(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.mem_write(op_store_u8, v_x, u8(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"u'_vx": vm._mem_read_int(v_x, 1)})


def _op_store_u16(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.mem_write(op_store_u16, v_x, u16(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"u'_vx": vm._mem_read_int(v_x, 2)})


def _op_store_u32(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.mem_write(op_store_u32, v_x, u32(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"u'_vx": vm._mem_read_int(v_x, 4)})


def _op_store_u64(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    vm.mem_write(op_store_u64, v_x, vm.reg[r_a])
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"u'_vx": vm._mem_read_int(v_x, 8)})


# ---- reg_reg operations ----

def _op_move_reg(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = vm.reg[r_a]
    vm.log and vm.log(reg1=r_d, reg2=r_a)


def _op_sbrk(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = vm._sbrk(vm.reg[r_a])
    vm.log and vm.log(reg1=r_d, reg2=r_a)


def _op_count_set_bits_64(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = int(vm.reg[r_a]).bit_count()
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_count_set_bits_32(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = pvm_X(u32(int(vm.reg[r_a])).bit_count(), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_leading_zero_bits_64(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = count_leading_zeroes(vm.reg[r_a], 64)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_leading_zero_bits_32(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = pvm_X(count_leading_zeroes(vm.reg[r_a], 32) - 32, 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_trailing_zero_bits_64(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = count_trailing_zeroes(vm.reg[r_a], 64)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_trailing_zero_bits_32(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = count_trailing_zeroes(u32(vm.reg[r_a]), 32)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_sign_extend_8(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = pvm_Z_inv(pvm_Z(u8(vm.reg[r_a]), 1), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_sign_extend_16(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = pvm_Z_inv(pvm_Z(u16(vm.reg[r_a]), 2), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_zero_extend_16(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = u16(vm.reg[r_a])
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_reverse_bytes(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    vm.reg[r_d] = reverse_bytes(vm.reg[r_a])
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})


def _op_store_imm_u8(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.code[vm.pc + 1] % 8))
    l_y = int(min(4, max(0, vm.inst_arg_len[inst_index] - l_x - 1)))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.mem_write(op_store_imm_u8, v_x, v_y % 2 ** 8)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 1)})


def _op_store_imm_u16(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.code[vm.pc + 1] % 8))
    l_y = int(min(4, max(0, vm.inst_arg_len[inst_index] - l_x - 1)))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.mem_write(op_store_imm_u16, v_x, v_y % 2 ** 16)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 2)})


def _op_store_imm_u32(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.code[vm.pc + 1] % 8))
    l_y = int(min(4, max(0, vm.inst_arg_len[inst_index] - l_x - 1)))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.mem_write(op_store_imm_u32, v_x, u32(v_y))
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 4)})


def _op_store_imm_u64(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = int(min(4, vm.code[vm.pc + 1] % 8))
    l_y = int(min(4, max(0, vm.inst_arg_len[inst_index] - l_x - 1)))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    vm.mem_write(op_store_imm_u64, v_x, v_y)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 8)})


# ---- reg_imm_imm: store_imm_ind_u{8,16,32,64} ----

def _fetch_reg_imm_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, vm.code[vm.pc + 1] % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    return r_a, w_a, v_x, v_y


def _op_store_imm_ind_u8(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = v_x + w_a
    vm.mem_write(op_store_imm_ind_u8, addr, v_y % (1 << 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 1)})


def _op_store_imm_ind_u16(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = v_x + w_a
    vm.mem_write(op_store_imm_ind_u16, addr, v_y % (1 << 16))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 2)})


def _op_store_imm_ind_u32(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = v_x + w_a
    vm.mem_write(op_store_imm_ind_u32, addr, u32(v_y))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 4)})


def _op_store_imm_ind_u64(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = v_x + w_a
    vm.mem_write(op_store_imm_ind_u64, addr, v_y)
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 8)})


def _op_add_64(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    r_d = min(12, vm.code[vm.pc + 2])
    a = int(vm.reg[r_a])
    b = int(vm.reg[r_b])
    vm.reg[r_d] = u64(a + b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})


def _op_load_imm_jump_ind(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = vm.code[vm.pc + 1] // 16
    w_b = vm.reg[r_b]
    l_x = int(min(4, vm.code[vm.pc + 2] % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 3, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 2)))
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 3 + l_x, l_y), l_y)
    vm.reg[r_a] = v_x
    vm.skip_len = vm.djump(u32(int(w_b) + int(v_y)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": vm.skip_len})


def _build_handlers():
    # Default to fallback which calls the legacy ladder for unmigrated opcodes
    H = [_op_fallthrough] * 256
    for i in range(256):
        H[i] = _op_invalid  # start invalid
    # None
    H[op_trap] = _op_trap
    H[op_fallthrough] = _op_fallthrough
    # imm
    H[op_ecalli] = _op_ecalli
    # reg_ext_imm
    H[op_load_imm_64] = _op_load_imm_64
    # offset
    H[op_jump] = _op_jump
    # reg_imm_offset
    H[op_load_imm_jump] = _op_load_imm_jump
    H[op_branch_eq_imm] = _op_branch_eq_imm
    H[op_branch_ne_imm] = _op_branch_ne_imm
    H[op_branch_lt_u_imm] = _op_branch_lt_u_imm
    H[op_branch_le_u_imm] = _op_branch_le_u_imm
    H[op_branch_ge_u_imm] = _op_branch_ge_u_imm
    H[op_branch_gt_u_imm] = _op_branch_gt_u_imm
    H[op_branch_lt_s_imm] = _op_branch_lt_s_imm
    H[op_branch_le_s_imm] = _op_branch_le_s_imm
    H[op_branch_ge_s_imm] = _op_branch_ge_s_imm
    H[op_branch_gt_s_imm] = _op_branch_gt_s_imm
    # reg_imm
    H[op_jump_ind] = _op_jump_ind
    H[op_load_imm] = _op_load_imm
    H[op_load_u8] = _op_load_u8
    H[op_load_i8] = _op_load_i8
    H[op_load_u16] = _op_load_u16
    H[op_load_i16] = _op_load_i16
    H[op_load_u32] = _op_load_u32
    H[op_load_i32] = _op_load_i32
    H[op_load_u64] = _op_load_u64
    H[op_store_u8] = _op_store_u8
    H[op_store_u16] = _op_store_u16
    H[op_store_u32] = _op_store_u32
    H[op_store_u64] = _op_store_u64
    # reg_reg
    H[op_move_reg] = _op_move_reg
    H[op_sbrk] = _op_sbrk
    H[op_count_set_bits_64] = _op_count_set_bits_64
    H[op_count_set_bits_32] = _op_count_set_bits_32
    H[op_leading_zero_bits_64] = _op_leading_zero_bits_64
    H[op_leading_zero_bits_32] = _op_leading_zero_bits_32
    H[op_trailing_zero_bits_64] = _op_trailing_zero_bits_64
    H[op_trailing_zero_bits_32] = _op_trailing_zero_bits_32
    H[op_sign_extend_8] = _op_sign_extend_8
    H[op_sign_extend_16] = _op_sign_extend_16
    H[op_zero_extend_16] = _op_zero_extend_16
    H[op_reverse_bytes] = _op_reverse_bytes
    # imm_imm
    H[op_store_imm_u8] = _op_store_imm_u8
    H[op_store_imm_u16] = _op_store_imm_u16
    H[op_store_imm_u32] = _op_store_imm_u32
    H[op_store_imm_u64] = _op_store_imm_u64
    # reg_imm_imm (indirect immediates)
    H[op_store_imm_ind_u8] = _op_store_imm_ind_u8
    H[op_store_imm_ind_u16] = _op_store_imm_ind_u16
    H[op_store_imm_ind_u32] = _op_store_imm_ind_u32
    H[op_store_imm_ind_u64] = _op_store_imm_ind_u64
    # reg_reg_reg
    H[op_add_64] = _op_add_64
    H[op_add_32] = _op_add_32
    H[op_sub_32] = _op_sub_32
    H[op_mul_32] = _op_mul_32
    H[op_div_u_32] = _op_div_u_32
    H[op_div_s_32] = _op_div_s_32
    H[op_rem_u_32] = _op_rem_u_32
    H[op_rem_s_32] = _op_rem_s_32
    H[op_shlo_l_32] = _op_shlo_l_32
    H[op_shlo_r_32] = _op_shlo_r_32
    H[op_shar_r_32] = _op_shar_r_32
    H[op_sub_64] = _op_sub_64
    H[op_mul_64] = _op_mul_64
    H[op_div_u_64] = _op_div_u_64
    H[op_div_s_64] = _op_div_s_64
    H[op_rem_u_64] = _op_rem_u_64
    H[op_rem_s_64] = _op_rem_s_64
    H[op_shlo_l_64] = _op_shlo_l_64
    H[op_shlo_r_64] = _op_shlo_r_64
    H[op_shar_r_64] = _op_shar_r_64
    H[op_and] = _op_and
    H[op_xor] = _op_xor
    H[op_or] = _op_or
    H[op_mul_upper_s_s] = _op_mul_upper_s_s
    H[op_mul_upper_u_u] = _op_mul_upper_u_u
    H[op_mul_upper_s_u] = _op_mul_upper_s_u
    H[op_set_lt_u] = _op_set_lt_u
    H[op_set_lt_s] = _op_set_lt_s
    H[op_cmov_iz] = _op_cmov_iz
    H[op_cmov_nz] = _op_cmov_nz
    H[op_rot_l_64] = _op_rot_l_64
    H[op_rot_l_32] = _op_rot_l_32
    H[op_rot_r_64] = _op_rot_r_64
    H[op_rot_r_32] = _op_rot_r_32
    H[op_and_inv] = _op_and_inv
    H[op_or_inv] = _op_or_inv
    H[op_xnor] = _op_xnor
    H[op_max] = _op_max
    H[op_max_u] = _op_max_u
    H[op_min] = _op_min
    H[op_min_u] = _op_min_u
    # reg_reg_imm_imm
    H[op_load_imm_jump_ind] = _op_load_imm_jump_ind

    # reg_reg_offset
    H[op_branch_eq] = _op_branch_eq
    H[op_branch_ne] = _op_branch_ne
    H[op_branch_lt_u] = _op_branch_lt_u
    H[op_branch_lt_s] = _op_branch_lt_s
    H[op_branch_ge_u] = _op_branch_ge_u
    H[op_branch_ge_s] = _op_branch_ge_s

    # reg_reg_imm
    H[op_store_ind_u8] = _op_store_ind_u8
    H[op_store_ind_u16] = _op_store_ind_u16
    H[op_store_ind_u32] = _op_store_ind_u32
    H[op_store_ind_u64] = _op_store_ind_u64
    H[op_load_ind_u8] = _op_load_ind_u8
    H[op_load_ind_i8] = _op_load_ind_i8
    H[op_load_ind_u16] = _op_load_ind_u16
    H[op_load_ind_i16] = _op_load_ind_i16
    H[op_load_ind_u32] = _op_load_ind_u32
    H[op_load_ind_i32] = _op_load_ind_i32
    H[op_load_ind_u64] = _op_load_ind_u64
    H[op_add_imm_32] = _op_add_imm_32
    H[op_and_imm] = _op_and_imm
    H[op_xor_imm] = _op_xor_imm
    H[op_or_imm] = _op_or_imm
    H[op_mul_imm_32] = _op_mul_imm_32
    H[op_set_lt_u_imm] = _op_set_lt_u_imm
    H[op_set_lt_s_imm] = _op_set_lt_s_imm
    H[op_shlo_l_imm_32] = _op_shlo_l_imm_32
    H[op_shlo_r_imm_32] = _op_shlo_r_imm_32
    H[op_shar_r_imm_32] = _op_shar_r_imm_32
    H[op_neg_add_imm_32] = _op_neg_add_imm_32
    H[op_set_gt_u_imm] = _op_set_gt_u_imm
    H[op_set_gt_s_imm] = _op_set_gt_s_imm
    H[op_shlo_l_imm_alt_32] = _op_shlo_l_imm_alt_32
    H[op_shlo_r_imm_alt_32] = _op_shlo_r_imm_alt_32
    H[op_shar_r_imm_alt_32] = _op_shar_r_imm_alt_32
    H[op_cmov_iz_imm] = _op_cmov_iz_imm
    H[op_cmov_nz_imm] = _op_cmov_nz_imm
    H[op_add_imm_64] = _op_add_imm_64
    H[op_mul_imm_64] = _op_mul_imm_64
    H[op_shlo_l_imm_64] = _op_shlo_l_imm_64
    H[op_shlo_r_imm_64] = _op_shlo_r_imm_64
    H[op_shar_r_imm_64] = _op_shar_r_imm_64
    H[op_neg_add_imm_64] = _op_neg_add_imm_64
    H[op_shlo_l_imm_alt_64] = _op_shlo_l_imm_alt_64
    H[op_shlo_r_imm_alt_64] = _op_shlo_r_imm_alt_64
    H[op_shar_r_imm_alt_64] = _op_shar_r_imm_alt_64
    H[op_rot_r_64_imm] = _op_rot_r_64_imm
    H[op_rot_r_64_imm_alt] = _op_rot_r_64_imm_alt
    H[op_rot_r_32_imm] = _op_rot_r_32_imm
    H[op_rot_r_32_imm_alt] = _op_rot_r_32_imm_alt
    return H


class PVMInterpreter:

    def __init__(self, program: PVMProgram, logger_cls=None):
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

        # Initialize memory sections storage
        self._init_mem_ops_lookup()

        # Initialize memory sections storage
        self.mem_sections = []
        self.mem_section_starts = np.array([], dtype=U32)
        self.mem_section_ends = np.array([], dtype=U32)
        self.mem_section_size = np.array([], dtype=U32)
        self.mem_acl: Dict[int, int] = {}

        self._mem_addr: int = -1

        self.ROM_ADDR = 0xFFFFFFFF
        self.ROM_END = -1
        self.HEAP_ADDR = 0xFFFFFFFF
        self.HEAP_END = -1
        self.STACK_ADDR = 0xFFFFFFFF
        self.STACK_END = -1
        self.ARG_ADDR = 0xFFFFFFFF
        self.ARG_END = -1

        self.mem_inaccesible = PVMMemoryMode.inaccesible.value
        self.mem_readable = PVMMemoryMode.readable.value
        self.mem_writable = PVMMemoryMode.writable.value

        self.mv_code = None
        self._sec_mv = [None, None, None, None]

        self.log = None

        self.reset(program)
        self.handlers = _build_handlers()

        if logger_cls:
            self.program = program
            self.log = logger_cls(pvm=self)
            self.log._pvm = self
            self.log._pvm_id = self.name
            for opcode_name in OpcodeNames.values():
                if opcode_name not in self.log.log_opcodes:
                    self.log.log_opcodes[opcode_name] = 0


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
            self.inst_pos[inst_bitmask_idx - 1] = inst_nr


    def branch(self, b:int, C:bool):
        """
        #GP-0.6.4-eq:A.17
        """
        if C:
            inst_pos = self.pc + b
            if inst_pos not in self.inst_pos:
                #self.status = ExitCondition.panic.value
                raise PanicError(f"Invalid branch instruction: C={C} b={b} inst_pos={inst_pos}")
            else:
                self.skip_len = b


    def reset(self, program: PVMProgram):
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

    #TODO: registers_as_int
    def get_registers(self):
        return [int(x) for x in self.reg]


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


    def _link_memory(self, memory):
        """Initialize memory sections as numpy arrays"""
        # Store memory sections as numpy arrays with their boundaries
        mem_section_starts = []
        mem_section_ends = []  # This will use paged_tail, not size
        mem_section_size = []

        self.mv_code = memoryview(self.code)

        # Access the actual memory sections (rom, heap, stack, args)
        for idx, section in enumerate([memory._rom, memory._heap, memory._stack, memory._args]):

            if section:
                if idx == 0:
                    self.ROM_ADDR = int(section.address)
                    self.ROM_END = int(section.paged_tail)
                if idx == 1:
                    self.HEAP_ADDR = int(section.address)
                    self.HEAP_END = int(section.paged_tail)
                if idx == 2:
                    self.STACK_ADDR = int(section.address)
                    self.STACK_END = int(section.paged_tail)
                if idx == 3:
                    self.ARG_ADDR = int(section.address)
                    self.ARG_END = int(section.paged_tail)


                self.mem_sections.append(section.contents)
                mem_section_starts.append(section.address)
                mem_section_ends.append(section.paged_tail)
                mem_section_size.append(section.size)
                self._sec_mv[idx] = memoryview(section.contents)
            else:
                self.mem_sections.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)
                self._sec_mv[idx] = None

        self.mem_section_starts = np.array(mem_section_starts, dtype=U32)
        self.mem_section_ends = np.array(mem_section_ends, dtype=U32)
        self.mem_section_size = np.array(mem_section_size, dtype=U32)
        self.mem_acl = memory._acl #TODO: pure ref for now, use from numba.typed import Dict for jit version


    def _sync_memory(self):
        """Sync memory state back to original PVMMemory and MemorySection objects after execution"""
        if self.mem_sections and self.mem_section_starts[1]:
            self.mem._heap.contents = self.mem_sections[1]
            self.mem._heap.size = len(self.mem_sections[1])
            self.mem._heap.paged_tail = self.mem_section_ends[1]
            self.mem._acl = self.mem_acl
            self.mem._mem_addr = self._mem_addr
            self._last_sec = -1


    def _sbrk(self, size):
        heap = self.mem_sections[1]

        #logging.critical(f"SBRK: {heap.size}")
        if size == 0:
            return self.mem_section_ends[1]

        current_heap_ptr = self.mem_section_ends[1]
        new_heap_ptr = current_heap_ptr + size
        if new_heap_ptr >= self.mem_section_starts[2]:
            return 0

        next_page_boundary = PVMMemory.page_size(current_heap_ptr)
        #logging.critical(f"{new_heap_ptr} > {next_page_boundary}")

        if new_heap_ptr > next_page_boundary:
            new_heap_end = PVMMemory.page_size(new_heap_ptr)
            growth = new_heap_end - next_page_boundary

            # Only grow when we exceed pre-allocated heap mem
            if new_heap_end - self.mem_section_starts[1] > len(heap):
                heap = np.concatenate((heap, np.zeros(growth, dtype=U8)))
                self.mem_sections[1] = heap
                self._sec_mv[1] = memoryview(self.mem_sections[1])
                #logging.critical(f"EXTENDING HEAP: {heap.size}")

            # Create ACL of new pages
            next_page_nr = current_heap_ptr // PVM_PAGE_SIZE
            pages = growth // PVM_PAGE_SIZE + 1
            for page_nr in range(pages):
                self.mem_acl[next_page_nr + page_nr] = self.mem_writable

            #logging.critical(f"????: {heap.size} - {pages} - {next_page_nr}")

        self.mem_section_ends[1] = new_heap_ptr
        self.HEAP_END = new_heap_ptr
        return new_heap_ptr


    def mem_write(self, opcode, addr, value):
        """Write to memory based on opcode"""
        #TODO: necessary?
        if not self.mem_ops_write[opcode]:
            raise Exception(f"Opcode {opcode} is not a valid memory write operation")

        bytes_to_write = int(self.mem_ops_bytes[opcode])
        addr = int(addr)
        #addr = addr % (2 ** 32)  #TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # Find the memory section
        section_idx = -1
        if self.STACK_ADDR <= addr <= self.STACK_END: section_idx = 2
        elif self.HEAP_ADDR <= addr <= self.HEAP_END: section_idx = 1
        elif self.ROM_ADDR <= addr <= self.ROM_END: section_idx = 0
        elif self.ARG_ADDR <= addr <= self.ARG_END: section_idx = 3

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            raise PVMMemoryError(f"mem_write: Memory address {addr} not found in any section")

        # Check if writable using page-based ACL (if available)
        if self.mem_acl is not None:
            page_nr = addr // PVM_PAGE_SIZE
            if page_nr not in self.mem_acl or self.mem_acl[page_nr] < self.mem_writable:
                raise PVMMemoryError(f"Memory at address {addr} is not writable")

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        # Check bounds against the actual section size (not paged_tail)
        # The section might be larger than paged_tail if it has been extended
        if section_offset + bytes_to_write > len(section):
            raise PVMMemoryError(f"Memory write at {addr} would overflow section")

        # Apply modulus for values less than 8 bytes
        if bytes_to_write < 8:
            value = value % (2 ** (bytes_to_write * 8))
        # Write bytes in little-endian order
        mv = self._sec_mv[section_idx]
        n = bytes_to_write
        if n == 1:
            mv[section_offset] = value & 0xFF
        elif n == 2:
            struct.pack_into('<H', mv, section_offset, value)
        elif n == 4:
            struct.pack_into('<I', mv, section_offset, value)
        elif n == 8:
            struct.pack_into('<Q', mv, section_offset, value)
        else:
            raise PVMMemoryError(f"Invalid write length: {bytes_to_write}")


    def _mem_read_int(self, addr: int, bytes_to_read: int):
        section_idx = -1
        if self.STACK_ADDR <= addr <= self.STACK_END: section_idx = 2
        elif self.HEAP_ADDR <= addr <= self.HEAP_END: section_idx = 1
        elif self.ROM_ADDR <= addr <= self.ROM_END: section_idx = 0
        elif self.ARG_ADDR <= addr <= self.ARG_END: section_idx = 3

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            raise PVMMemoryError(f"mem_read_int: Memory address {addr} not found in any section")

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        # Check bounds against the actual section size
        if section_offset + bytes_to_read > len(section):
            raise PVMMemoryError(f"mem_read_int: Memory read at {addr} would overflow section")

        return read_uint(section, section_offset, bytes_to_read)


    def mem_read(self, opcode, addr):
        """Read from memory based on opcode"""
        # TODO: necessary?
        if not self.mem_ops_read[opcode]:
            raise Exception(f"Opcode {opcode} is not a valid memory read operation")

        bytes_to_read = int(self.mem_ops_bytes[opcode])
        addr = int(addr)
        #addr = addr % (2 ** 32)  # TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        section_idx = -1
        if self.STACK_ADDR <= addr <= self.STACK_END: section_idx = 2
        elif self.HEAP_ADDR <= addr <= self.HEAP_END: section_idx = 1
        elif self.ROM_ADDR <= addr <= self.ROM_END: section_idx = 0
        elif self.ARG_ADDR <= addr <= self.ARG_END: section_idx = 3

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            raise PVMMemoryError(f"mem_read: Memory address {addr} not found in any section")

        if self.mem and self.mem_acl is not None:
            page_nr = addr // PVM_PAGE_SIZE
            if page_nr not in self.mem_acl or self.mem_acl[page_nr] == self.mem_inaccesible:
                raise PVMMemoryError(f"Memory at address {addr} is not accessible")

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        if section_offset + bytes_to_read > len(section):
            raise PVMMemoryError(f"Memory read at {addr} would overflow section")

        return read_uint(self._sec_mv[section_idx], section_offset, bytes_to_read)


    #GP-0.6.7-section:A.15
    def djump(self, a: int):
        if a == 2 ** 32 - 2 ** 16:
            self.status = ExitReason.halt.value
            return 0
        elif (a == 0 or
              a > len(self.jump_table) * PVM_DYNAMIC_ALIGNMENT_FACTOR or
              a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0 or
              self.jump_table[a//PVM_DYNAMIC_ALIGNMENT_FACTOR-1] not in self.inst_pos):
            raise PanicError(f"Invalid djump operation: a={a}")
        else:
            return self.jump_table[a//PVM_DYNAMIC_ALIGNMENT_FACTOR-1] - self.pc


    def get_exit_condition(self) -> ExitCondition:
        exit_value = None
        exit_reason = self.status

        if self.status in (ExitReason.host_halt.value, ExitReason.page_fault.value):
            exit_value = int(self.exit_value)
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
        self.skip_len = self.inst_arg_len[inst_index] + 1


    def invoke(
        self,
        pc: int,
        gas: int
    ):
        self.pc = pc
        self.gas = gas

        if self.log:
            self.log.pvm_counters()
            self.log.pvm_header()

        # GP-0.7.0-section:A.1 Single-Step State Transition
        while self.status == ExitReason.resume.value:

            if self.gas <= 0:
                self.status = ExitReason.out_of_gas.value
                self.exit_value = None
                break

            self.gas -= 1
            self.pc = self.pc + self.skip_len
            self.inst_nr += 1

            if self.pc >= self.code_size:
                self.status = ExitReason.panic.value
                self.exit_value = None
                break

            inst_index = self.inst_pos[self.pc]
            self.opcode = opcode = self.code[self.pc]
            self.skip_len = self.inst_arg_len[inst_index] + 1

            try:
                self.handlers[opcode](self)
                continue
            except PVMMemoryError:
                self.status = ExitReason.page_fault.value
                self.exit_value = self._mem_addr
                break
            except PanicError:
                self.status = ExitReason.panic.value
                break

        #self.mem._pvm_invoke_nr += 1
        self._sync_memory()
