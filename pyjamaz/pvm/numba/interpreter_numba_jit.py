"""
An optimized PVM interpreter using Numba JIT compiler for the main loop & functions.
"""
#TODO: share met andere files/constants and types!!!
#TODO: signatures toevoegen aan njit decorator
#TODO: port de opcodes vd laatste versie van mb-pvm-pyd
#TODO: sort de if/else statements op frequentie dat een opcode voorkomt!

#import time as _pytime

import ctypes
import math
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt

from numba import njit, types, objmode
from numba.typed import Dict, List
from numba import uint8, uint32, int32, uint64, int64, boolean


from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR
from ..rpython.interpreter_rpython import PVMInterpreter as PVMInterpreterBase
from .types import PVMProgram
from ..constants import (
    ExitReason, OpcodeScheme, OpcodeNames,

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

    inst_none, inst_imm, inst_reg_ext_imm, inst_imm_imm, inst_offset, inst_reg_imm,
    inst_reg_imm_imm, inst_reg_imm_offset, inst_reg_reg, inst_reg_reg_imm,
    inst_reg_reg_offset, inst_reg_reg_imm_imm, inst_reg_reg_reg
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


# Set up Numba caching for persistent compilation
#PVM_AOT_CACHE: str = "./pyjamaz_numba_cache"
#_cache_dir = os.path.expanduser("./pyjamaz_numba_cache")
#_cache_dir = os.path.expanduser("/tmp/numba-cache/")
#os.makedirs(_cache_dir, exist_ok=True)
#os.environ['NUMBA_CACHE_DIR'] = _cache_dir
#os.environ['NUMBA_CACHE'] = '1'
NUMBA_CACHE = True
#os.environ['NUMBA_CACHE_DIR'] = _cache_dir

# os.environ['NUMBA_DISABLE_PERFORMANCE_WARNINGS'] = '1'
# os.environ['NUMBA_BOUNDSCHECK'] = '0'  # Disable bounds checking for speed
# os.environ['NUMBA_DISABLE_JIT'] = '0'  # Ensure JIT is enabled
# os.environ['NUMBA_OPT'] = '3'  # Maximum optimization level
# os.environ['NUMBA_EAGERNESS'] = '1'  # Compile all branches eagerly
# os.environ['NUMBA_NUM_THREADS'] = '1'  # Avoid parallel compilation issues
# os.environ['NUMBA_THREADING_LAYER'] = 'sequential'

U64_MASK = U64(0xFFFFFFFFFFFFFFFF)
U32_MASK = U64(0xFFFFFFFF)

u8_array_1d = types.Array(uint8, 1, 'C')
u8_array_list = types.ListType(u8_array_1d)
int32_array_1d = types.Array(int32, 1, 'C')


def _ensure_uint8_array(buffer) -> np.ndarray:
    """Return a C-contiguous np.uint8 array view of the buffer without copying."""
    if isinstance(buffer, np.ndarray) and buffer.dtype == np.uint8 and buffer.flags.c_contiguous:
        return buffer

    mv = memoryview(buffer)
    ptr_type = ctypes.c_uint8 * mv.nbytes
    ptr = ptr_type.from_buffer(mv)
    arr = np.ctypeslib.as_array(ptr)
    return arr


@njit(types.UniTuple(uint64, 2)(uint64, uint64), cache=NUMBA_CACHE)
def umul64wide_jit(a: U64, b: U64) -> (U64, U64):
    """Unsigned 64x64 -> (hi, lo) as uint64s."""
    mask32 = U64(0xFFFFFFFF)
    a_lo = a & mask32
    a_hi = a >> U64(32)
    b_lo = b & mask32
    b_hi = b >> U64(32)

    ll = a_lo * b_lo  # 64-bit
    lh = a_lo * b_hi
    hl = a_hi * b_lo
    hh = a_hi * b_hi

    carry = (ll >> U64(32)) + (lh & mask32) + (hl & mask32)
    lo = (ll & mask32) | ((carry & mask32) << U64(32))
    hi = hh + (lh >> U64(32)) + (hl >> U64(32)) + (carry >> U64(32))
    return U64(hi), U64(lo)


@njit(types.UniTuple(uint64, 2)(int64, int64), cache=NUMBA_CACHE)
def imul64wide_jit(a: I64, b: I64) -> (U64, U64):
    """Signed 64x64 -> (hi, lo) representing 128-bit two's-complement product."""
    ua = U64(a)  # reinterpret
    ub = U64(b)
    hi, lo = umul64wide_jit(ua, ub)
    # Adjust high word for two's-complement signs (see Hacker's Delight)
    if a < 0:
        hi = U64(hi - ub)
    if b < 0:
        hi = U64(hi - ua)
    return U64(hi), U64(lo)


@njit(types.UniTuple(uint64, 2)(int64, uint64), cache=NUMBA_CACHE)
def smul_u64wide_jit(a: I64, b: U64) -> (U64, U64):
    """Signed * Unsigned -> (hi, lo), two's-complement."""
    ua = U64(a)
    hi, lo = umul64wide_jit(ua, b)
    if a < 0:
        hi = U64(hi - b)
    return U64(hi), U64(lo)


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def rori64_jit(x: U64, shift_amount: U64) -> U64:
    """Rotate right for 64-bit integers."""
    return U64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def roli64_jit(x: U64, shift_amount: U64) -> U64:
    """Rotate left for 64-bit integers."""
    return U64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit(uint32(uint32, uint32), cache=NUMBA_CACHE)
def rori32_jit(x: U32, shift_amount: U32) -> U32:
    """Rotate right for 32-bit integers."""
    return U32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


@njit(uint32(uint32, uint32), cache=NUMBA_CACHE)
def roli32_jit(x: U32, shift_amount: U32) -> U32:
    """Rotate left for 32-bit integers."""
    return U32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def pvm_smod_jit(a: I64, b: I64) -> I64:
    """
    Signed modulo operation.
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


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def pvm_rtz_div_jit(a: I64, b: I64) -> I64:
    """
    Truncated division (rounds toward zero).
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


@njit(uint64(uint64, uint64), cache=NUMBA_CACHE)
def pvm_X_jit(x: U64, n: U64) -> U64:
    # TODO: remove cast
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


@njit(int64(uint64, uint64), cache=NUMBA_CACHE)
def pvm_Z_jit(a: U64, n: U64) -> I64:
    """
    Unsigned->signed conversion for n bytes (1..8).
    Returns I64 with proper two's-complement sign extension without Python big-ints.
    """
    #TODO: remove casts
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


@njit(uint64(uint64, uint8), cache=NUMBA_CACHE)
def count_leading_zeroes_jit(value: U64, max_bits:U8) -> U64:
    """
    Count-leading-zeroes with explicit 64-bit masking and shifts.
    Matches Python implementation for max_bits in {32,64}.
    """
    mb = U64(max_bits)
    # Build mask and starting test bit using 64-bit arithmetic
    if mb >= U64(64):
        mask = U64(0xFFFFFFFFFFFFFFFF)
        test_bit = U64(1) << U64(63)
        maxb = 64
    else:
        mask = (U64(1) << mb) - U64(1)
        test_bit = U64(1) << (mb - U64(1))
        maxb = int(mb)

    val = U64(value) & mask
    if val == U64(0):
        return maxb

    count = 0
    while (val & test_bit) == U64(0) and count < maxb:
        count += 1
        test_bit = test_bit >> U64(1)

    return count


@njit(uint64(uint64, uint8), cache=NUMBA_CACHE)
def count_trailing_zeroes_jit(value: U64, max_bits: U8) -> U64:
    #TODO: optimize?
    if value == 0:
        return max_bits

    count = 0
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


@njit(uint64(uint64), cache=NUMBA_CACHE)
def reverse_bytes_jit(x: U64) -> U64:
    #TODO: optimize?
    result = U64(0)
    for i in range(8):
        byte = U64((x >> U64(i * 8)) & U64(0xFF))
        result |= U64(byte << U64((7 - i) * 8))
    return result


@njit(int64(int64, int64), cache=NUMBA_CACHE)
def riscv_div_jit(a: I64, b: I64) -> I64:
    if b == 0:
        return I64(-1)
    return a // b


@njit(uint64(int64, uint8), cache=NUMBA_CACHE)
def pvm_Z_inv_jit(a: I64, n: U8) -> U64:
    """
    Signed to unsigned.
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


@njit(uint64(uint8[::1], uint32, uint8), cache=NUMBA_CACHE)
def read_uint_jit(code: npt.NDArray[U8], addr: U32, length: U8) -> U64:
    addr32 = U32(addr)  # wrap to 32-bit address space
    len8 = U8(length)

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
        return (b0 | (b1 << U64(8)) | (b2 << U64(16)) |
                (b3 << U64(24)) | (b4 << U64(32)) |
                (b5 << U64(40)) | (b6 << U64(48)) |
                (b7 << U64(56)))

    raise Exception("read_uint: unsupported length")


@njit(int32(
    uint64,       # addr
    uint64,       # value
    uint8,        # bytes_to_write
    uint64[::1],  # section_starts
    uint64[::1],  # section_ends
    u8_array_list,# section_arrays
    int32[::1],   # acl_array
    int32[::1],   # acl_extra_start
    int32[::1]    # acl_extra_count
), cache=NUMBA_CACHE)
def mem_write_jit(addr: U64, value: U64, bytes_to_write: U8,
                  section_starts, section_ends, section_arrays,
                  acl_array, acl_extra_start, acl_extra_count) -> I32:
    """
    Returns status:I32 where status==0 on success, -1 on fault.
    """
    idx = I32(-1)
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = I32(i)
            break
    if idx < 0:
        return I32(-1)

    page_nr = int(U64(addr >> PVM_PAGE_SHIFT) & U32_MASK)
    allowed = False
    if len(acl_array) > 0 and 0 <= page_nr < len(acl_array):
        allowed = acl_array[page_nr] >= MEM_WRITABLE
    if not allowed:
        start_page = int(acl_extra_start[0])
        count = int(acl_extra_count[0])
        if count > 0 and start_page <= page_nr < start_page + count:
            allowed = True
    if not allowed:
        return I32(-1)

    start = U64(section_starts[idx])
    off = addr - start

    a = section_arrays[idx]  # uint8[::1]
    if off + U64(bytes_to_write) > U64(len(a)):
        return I32(-1)

    # Mask value for <8 byte writes
    if bytes_to_write < U8(8):
        shift = U64(bytes_to_write) * U64(8)
        mask = (U64(1) << shift) - U64(1)
        value = value & mask

    base = int(off)

    if bytes_to_write == U8(1):
        a[base] = U8(value & U64(0xFF))
    elif bytes_to_write == U8(2):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
    elif bytes_to_write == U8(4):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
        a[base + 2] = U8((value >> U64(16)) & U64(0xFF))
        a[base + 3] = U8((value >> U64(24)) & U64(0xFF))
    elif bytes_to_write == U8(8):
        a[base] = U8(value & U64(0xFF))
        a[base + 1] = U8((value >> U64(8)) & U64(0xFF))
        a[base + 2] = U8((value >> U64(16)) & U64(0xFF))
        a[base + 3] = U8((value >> U64(24)) & U64(0xFF))
        a[base + 4] = U8((value >> U64(32)) & U64(0xFF))
        a[base + 5] = U8((value >> U64(40)) & U64(0xFF))
        a[base + 6] = U8((value >> U64(48)) & U64(0xFF))
        a[base + 7] = U8((value >> U64(56)) & U64(0xFF))
    else:
        return I32(-1)

    return I32(0)


@njit(types.Tuple((int32, uint64))(
    uint64,       # addr
    uint8,        # bytes_to_read
    uint64[::1],  # section_starts
    uint64[::1],  # section_ends
    u8_array_list,# section_arrays
    int32[::1],   # acl_array
    int32[::1],   # acl_extra_start
    int32[::1]    # acl_extra_count
), cache=NUMBA_CACHE)
def mem_read_jit(addr: U64, bytes_to_read: U8,
                 section_starts, section_ends, section_arrays,
                 acl_array, acl_extra_start, acl_extra_count) -> (I32, U64):
    """
    Returns (status:I32, value:U64) where status==0 on success, -1 on fault.
    """
    idx = I32(-1)
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = I32(i)
            break
    if idx < 0:
        return I32(-1), U64(0)

    page_nr = int(U64(addr >> PVM_PAGE_SHIFT) & U32_MASK)
    allowed = False
    if len(acl_array) > 0 and 0 <= page_nr < len(acl_array):
        allowed = acl_array[page_nr] != MEM_INACCESSIBLE
    if not allowed:
        start_page = int(acl_extra_start[0])
        count = int(acl_extra_count[0])
        if count > 0 and start_page <= page_nr < start_page + count:
            allowed = True
    if not allowed:
        return I32(-1), U64(0)

    start = U64(section_starts[idx])
    off = addr - start

    a = section_arrays[idx]  # uint8[::1] array
    if off + U64(bytes_to_read) > U64(len(a)):
        return I32(-1), U64(0)
    base = int(off)

    if bytes_to_read == U8(1):
        return I32(0), U64(a[base])
    elif bytes_to_read == U8(2):
        return I32(0), (U64(a[base]) | (U64(a[base + 1]) << U64(8)))
    elif bytes_to_read == U8(4):
        return I32(0), (U64(a[base]) |
                        (U64(a[base + 1]) << U64(8)) |
                        (U64(a[base + 2]) << U64(16)) |
                        (U64(a[base + 3]) << U64(24)))
    elif bytes_to_read == U8(8):
        return I32(0), (U64(a[base]) |
                        (U64(a[base + 1]) << U64(8)) |
                        (U64(a[base + 2]) << U64(16)) |
                        (U64(a[base + 3]) << U64(24)) |
                        (U64(a[base + 4]) << U64(32)) |
                        (U64(a[base + 5]) << U64(40)) |
                        (U64(a[base + 6]) << U64(48)) |
                        (U64(a[base + 7]) << U64(56)))
    else:
        return I32(-1), U64(0)


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


@njit(uint64(uint64), cache=NUMBA_CACHE)
def _fmix64_jit(x: U64) -> U64:
    """Finalization mix (from MurmurHash3), good avalanche; JIT-safe."""
    x ^= x >> U64(33)
    x *= U64(0xff51afd7ed558ccd)
    x ^= x >> U64(33)
    x *= U64(0xc4ceb9fe1a85ec53)
    x ^= x >> U64(33)
    return x


@njit(uint64(uint8[::1]), cache=NUMBA_CACHE)
def hash_memory_segment(section_array) -> U64:
    """
    Hash the ENTIRE memory segment (all bytes) with FNV-1a 64-bit, then fmix.
    section_array: uint8[::1] NumPy array (1-D, C-contiguous).
    """
    n = len(section_array)
    if n == 0:
        return U64(0)

    h = U64(1469598103934665603)  # FNV-1a offset basis (64-bit)
    prime = U64(1099511628211)  # FNV-1a prime (64-bit)

    # Process all bytes (rely on 64-bit wraparound; no modulo)
    for i in range(n):
        h ^= U64(section_array[i])
        h *= prime

    return _fmix64_jit(h)


@njit(uint64(u8_array_list, int32), cache=NUMBA_CACHE)
def get_memory_hash(section_arrays, seg_idx: I32):
    """Compute a 64-bit hash for the given memory segment (entire buffer)."""
    segment_hash = U64(0)
    if seg_idx >= 0 and seg_idx < len(section_arrays):
        segment_hash = hash_memory_segment(section_arrays[seg_idx])
    return segment_hash


@njit(types.Tuple((uint64, int64))(
    uint64,
    uint64,
    uint64,
    int64,
    u8_array_list,
    uint64[::1]
), cache=NUMBA_CACHE)
def sbrk_jit(size: U64, current_heap_ptr: U64, next_section_start: U64,
             mem_writable: I64, section_arrays, section_starts) -> (U64, I64):
    """JIT implementation of sbrk heap allocation with optional heap growth.
    Returns (new_heap_ptr, grew_flag) where grew_flag==1 if heap buffer was extended.
    """
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
            reserve_len = np.int64(desired_len)
            new_arr = np.empty(reserve_len, dtype=U8)
            if cur_len > 0:
                new_arr[:cur_len] = heap_arr[:cur_len]
            new_arr[cur_len:reserve_len] = 0
            section_arrays[1] = new_arr
            grew_bytes = I64(growth)

    return new_heap_ptr, grew_bytes


@njit(int32(uint32, int64, boolean, int32[::1]), cache=NUMBA_CACHE)
def branch_jit(pc: U32, offset: I64, condition: bool, pc_to_inst_index) -> I32:
    """JIT implementation of branch with validation."""
    if condition:
        target_pc = pc + offset
        # Check if target PC is valid via dense map
        tpi = int(target_pc)
        if not (tpi >= 0 and tpi < len(pc_to_inst_index) and pc_to_inst_index[tpi] >= 0):
            return I32(-1)  # Invalid branch - panic

        return I32(offset)  # Valid branch
    else:
        return I32(0)  # No branch - continue


@njit(int32(uint32, int32[::1], uint32, int32[::1]), cache=NUMBA_CACHE)
def djump_jit(a: U32, jump_table, pc: U32, pc_to_inst_index) -> I32:
    """JIT implementation of djump with validation."""
    halt_value = U32((U32(0xFFFFFFFF) - U32(0xFFFF)) & U32_MASK)
    if a == halt_value:
        return I32(-1)  # Special return code for halt

    if (a == 0 or
            a > len(jump_table) * PVM_DYNAMIC_ALIGNMENT_FACTOR or
            a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0):
        return I32(-2)

    jump_idx = a // PVM_DYNAMIC_ALIGNMENT_FACTOR - 1
    if jump_idx < 0 or jump_idx >= len(jump_table):
        return I32(-2)

    target_pc = U32(jump_table[jump_idx])

    # Validate target_pc via dense map
    tpi = int(target_pc)
    if not (tpi >= 0 and tpi < len(pc_to_inst_index) and pc_to_inst_index[tpi] >= 0):
        return I32(-2)

    return I32(target_pc - pc)  # Valid skip_len


# --- Python wrapper for invoke_native ---

def invoke(
    pc_start, gas_start, inst_start, initial_skip_len,
    code, code_size,
    inst_pos_keys, inst_pos_vals, inst_arg_len_array, pc_to_inst_index,
    opcode_scheme_array, jump_table_array,
    mem_ops_read, mem_ops_write, mem_ops_bytes,
        mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count,
    heap_info, registers_in, logging,
    registers_out, state_out, heap_grew_out
):
    import numpy as np
    from numba.typed import Dict
    from numba import types

    # Ensure argument dtypes exactly match invoke_native signature (force dtype)
    pc_start_u32 = np.uint32(pc_start)
    gas_start_i64 = np.int64(gas_start)
    inst_start_u32 = np.uint32(inst_start)
    initial_skip_len_u32 = np.uint32(initial_skip_len)
    code_size_u32 = np.uint32(code_size)

    # Ensure code is uint8[::1] C-contiguous
    if not (isinstance(code, np.ndarray) and code.dtype == np.uint8 and code.flags['C_CONTIGUOUS']):
        code = np.asarray(code, dtype=np.uint8, order='C')

    # Dense index structures must be int32[::1] C-contiguous
    if not (isinstance(inst_pos_keys, np.ndarray) and inst_pos_keys.dtype == np.int32 and inst_pos_keys.flags['C_CONTIGUOUS']):
        inst_pos_keys = np.asarray(inst_pos_keys, dtype=np.int32, order='C')
    if not (isinstance(inst_pos_vals, np.ndarray) and inst_pos_vals.dtype == np.int32 and inst_pos_vals.flags['C_CONTIGUOUS']):
        inst_pos_vals = np.asarray(inst_pos_vals, dtype=np.int32, order='C')
    if not (isinstance(inst_arg_len_array, np.ndarray) and inst_arg_len_array.dtype == np.int32 and inst_arg_len_array.flags['C_CONTIGUOUS']):
        inst_arg_len_array = np.asarray(inst_arg_len_array, dtype=np.int32, order='C')
    if not (isinstance(pc_to_inst_index, np.ndarray) and pc_to_inst_index.dtype == np.int32 and pc_to_inst_index.flags['C_CONTIGUOUS']):
        pc_to_inst_index = np.asarray(pc_to_inst_index, dtype=np.int32, order='C')
    if not (isinstance(opcode_scheme_array, np.ndarray) and opcode_scheme_array.dtype == np.int32 and opcode_scheme_array.flags['C_CONTIGUOUS']):
        opcode_scheme_array = np.asarray(opcode_scheme_array, dtype=np.int32, order='C')
    if not (isinstance(jump_table_array, np.ndarray) and jump_table_array.dtype == np.int32 and jump_table_array.flags['C_CONTIGUOUS']):
        jump_table_array = np.asarray(jump_table_array, dtype=np.int32, order='C')

    # mem_ops_* must be int64[::1] (force cast)
    mem_ops_read  = np.asarray(mem_ops_read,  dtype=np.int64, order='C')
    mem_ops_write = np.asarray(mem_ops_write, dtype=np.int64, order='C')
    mem_ops_bytes = np.asarray(mem_ops_bytes, dtype=np.int64, order='C')

    # section bounds must be uint64[::1]
    mem_section_starts = np.asarray(mem_section_starts, dtype=np.uint64, order='C')
    mem_section_ends   = np.asarray(mem_section_ends,   dtype=np.uint64, order='C')

    # registers and heap_info must be uint64[::1]
    registers_in = np.asarray(registers_in, dtype=np.uint64, order='C')
    heap_info    = np.asarray(heap_info,    dtype=np.uint64, order='C')

    # outputs: registers_out:uint64[::1], state_out:int64[::1], heap_grew_out:int64[::1]
    registers_out = np.asarray(registers_out, dtype=np.uint64, order='C')
    state_out     = np.asarray(state_out,     dtype=np.int64,  order='C')
    heap_grew_out = np.asarray(heap_grew_out, dtype=np.int64,  order='C')

    # Ensure logging dict is a typed Dict[int64, unicode]
    if isinstance(logging, dict):
        _typed_logging = Dict.empty(key_type=types.int64, value_type=types.unicode_type)
        logging = _typed_logging

    error_code = invoke_native_jit(
        np.uint32(pc_start_u32),       # uint32
        np.int64(gas_start_i64),       # int64
        np.uint32(inst_start_u32),     # uint32
        np.uint32(initial_skip_len_u32),# uint32

        code,                          # uint8[::1]
        np.uint32(code_size_u32),      # uint32
        inst_pos_keys,                 # int32[::1]
        inst_pos_vals,                 # int32[::1]
        inst_arg_len_array,            # int32[::1]
        pc_to_inst_index,              # int32[::1]
        opcode_scheme_array,           # int32[::1]
        jump_table_array,              # int32[::1]

        mem_ops_read,                  # int64[::1]
        mem_ops_write,                 # int64[::1]
        mem_ops_bytes,                 # int64[::1]

        mem_section_starts,            # uint64[::1]
        mem_section_ends,              # uint64[::1]
        section_arrays,                # List[uint8[:]]
        acl_array,                     # int32[::1]

        heap_info,                     # uint64[::1]
        registers_in,                  # uint64[::1]
        logging,                       # Dict[int64, unicode]

        registers_out,                 # uint64[::1]
        state_out,                     # int64[::1]
        heap_grew_out,                 # int64[::1]
    )
    return error_code


@njit(cache=NUMBA_CACHE)
def log(
        opcode_names,
        local_state,
        regs,
        reg1=None,
        reg2=None,
        reg3=None,
        imm1=None,
        imm2=None,
        off1=None,
        off2=None,
        context="",
        mem=None,
        mem_starts=None,
        mem_ends=None):

    inst_nr = int(local_state[0])
    opcode = int(local_state[1])
    pc = int(local_state[2])
    gas = int(local_state[3])
    start_time = float(local_state[4])
    """
    JIT-compatible logging function for instruction execution tracing.
    Matches the format used in the normal interpreter for consistency.
    """
    if len(opcode_names) == 0:
        return

    #name = opcode_names.get(np.int64(opcode), "UNKNOWN")
    opcode_key = np.int64(opcode)
    if opcode_key in opcode_names:
        name = opcode_names[opcode_key]
    else:
        name = "UNKNOWN"

    mem_info = ""
    # if mem is not None and len(mem) >= 2:
    #     if mem_starts is not None and mem_ends is not None:
    #         # Compute effective lengths based on section bounds so hash reflects sbrk changes
    #         heap_len = int(mem_ends[1] - mem_starts[1])
    #         if heap_len < 0:
    #             heap_len = 0
    #         if heap_len > len(mem[1]):
    #             heap_len = len(mem[1])
    #         heap_hash = hash_memory_segment(mem[1][:heap_len])
    #     else:
    #         heap_hash = hash_memory_segment(mem[1])
    #     mem_info += f"heap_hash:{heap_hash}"
    # if mem is not None and len(mem) >= 3:
    #     if mem_starts is not None and mem_ends is not None:
    #         stack_len = int(mem_ends[2] - mem_starts[2])
    #         if stack_len < 0:
    #             stack_len = 0
    #         if stack_len > len(mem[2]):
    #             stack_len = len(mem[2])
    #         stack_hash = hash_memory_segment(mem[2][:stack_len])
    #     else:
    #         stack_hash = hash_memory_segment(mem[2])
    #     mem_info += f" stack_hash:{stack_hash}"

    # print("inst=",inst_nr, "op=",name, "pc=",pc, "gas=",gas,
    #       "r1=",reg1, "r2=",reg2, "r3=",reg3,
    #       "imm1=",imm1, "imm2=",imm2, "off1=",off1, "off2=",off2, context, mem_info)

    # Format opcode name with fixed width (22 chars)
    name_str = name
    name_pad = 22 - len(name_str)
    if name_pad > 0:
        name_str = name_str + (" " * name_pad)

    # Format registers with fixed width (21 chars) for even spacing.
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

    # Fixed width for inst_nr and pc (4 chars each, right-aligned)
    inst_str = str(inst_nr)
    if len(inst_str) < 4:
        inst_str = (" " * (4 - len(inst_str))) + inst_str

    pc_str = str(pc)
    if len(pc_str) < 4:
        pc_str = (" " * (4 - len(pc_str))) + pc_str

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
    print(inst_str, pc_str, name_str, regs_str, mem_info)


@njit(int32(
    uint32,          # pc
    int64,           # gas
    uint32,          # inst_nr
    uint32,          # skip_len

    uint8[::1],      # code
    uint32,          # code_size
    int32[::1],      # inst_pos_keys
    int32[::1],      # inst_pos_vals
    int32[::1],      # inst_arg_len_array
    int32[::1],      # pc_to_inst_index
    int32[::1],      # opcode_scheme_array (len 256)
    int32[::1],      # jump_table_array

    int64[::1],      # mem_ops_read
    int64[::1],      # mem_ops_write
    int64[::1],      # mem_ops_bytes

    uint64[::1],     # mem_section_starts
    uint64[::1],     # mem_section_ends
    u8_array_list,   # section_arrays : List[uint8[:]]
    int32[::1],      # acl_array
    int32[::1],      # acl_extra_starts
    int32[::1],      # acl_extra_lengths

    uint64[::1],     # heap_info (len 3)
    uint64[::1],     # reg (len 13)
    types.DictType(int64, types.unicode_type),  # opcode_names

    uint64[::1],     # registers_out
    int64[::1],      # state_out
    int64[::1],      # heap_grew_out
), cache=NUMBA_CACHE)
def invoke_native_jit(
        pc_start, gas_start, inst_start, initial_skip_len,
        code, code_size,
        inst_pos_keys, inst_pos_vals, inst_arg_len, pc_to_inst_index,
        opcode_scheme, jump_table,
        mem_ops_read, mem_ops_write, mem_ops_bytes,
        mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count,
        heap_info,  # [current_heap_end, next_section_start, mem_writable_value]
        registers_in,
        logging,
        registers_out,
        state_out,
        heap_grew_out
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
    skip_len = I64(initial_skip_len)
    inst_nr = U32(inst_start)

    # Copy registers
    reg = registers_in.copy()

    # #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # if logging:
    #     print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    #     return -1
    # else:
    #     print("LOGGING" + str(len(logging)))
    #TODO: adv logging, refactor logg naar lognes
    # logg = True
    # timing_enabled = True
    logg = False
    timing_enabled = False

    if len(acl_extra_start) > 0:
        acl_extra_start[0] = 0
    if len(acl_extra_count) > 0:
        acl_extra_count[0] = 0

    # Main execution loop
    while status == EXIT_RESUME and gas > 0:
        # Calculate next PC but don't update yet
        start_time = 0.0
        # if logg and timing_enabled:
        #     with objmode(t0='float64'):
        #         t0 = _pytime.perf_counter()
        #     start_time = t0
        next_pc = U32(pc + skip_len)

        if next_pc >= code_size:
            status = EXIT_PANIC
            break

        # Find instruction index at next PC (O(1) via dense lookup)
        inst_index = -1
        npi = int(next_pc)
        if npi >= 0 and npi < len(pc_to_inst_index):
            inst_index = pc_to_inst_index[npi]

        # TODO: deze check ook backporten??? en gebruik die helper functie!
        if inst_index < 0:
            # write outputs directly and return trap
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            state_out[STATE_STATUS] = I64(status)
            state_out[STATE_PC] = I64(next_pc)
            state_out[STATE_GAS] = I64(gas)
            state_out[STATE_INST_NR] = I64(inst_nr)
            state_out[STATE_EXIT_VALUE] = I64(exit_value)
            state_out[STATE_SKIP_LEN] = I64(skip_len)
            state_out[STATE_ERROR] = I64(ERROR_PANIC_TRAP)
            return ERROR_PANIC_TRAP

        # Now we know we can proceed, so update state
        gas -= 1
        pc = next_pc
        inst_nr += 1

        # Fetch opcode and decode
        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = inst_arg_len[inst_index] + 1
        # Local state tuple for logging: (inst_nr, opcode, pc, gas, start_time)
        if logg:
            local_state = (int(inst_nr), int(opcode), int(pc), int(gas), float(start_time))

        # Calculate memory hashes for debugging (heap=index 1, stack=index 2)
        # heap_hash, stack_hash = get_memory_hashes(section_arrays, I32(1), I32(2))
        # mem_hash_tuple = (heap_hash, stack_hash)

        # GP-0.6.7-section:A.5.1
        if inst_type == inst_none:  # InstructionType.none
            if opcode == op_trap:
                if logg: log(logging, local_state, reg, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)
            elif opcode == op_fallthrough:
                if logg: log(logging, local_state, reg, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                pass
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.2
        elif inst_type == inst_imm:  # InstructionType.imm
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_X_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_ecalli:
                # Set exit value; wrapper will advance PC using skip_len_out
                exit_value = I64(v_x)
                if logg: log(logging, local_state, reg, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_HOST_HALT,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_NONE)
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.3
        elif inst_type == inst_reg_ext_imm:  # InstructionType.reg_ext_imm
            r_a = min(12, code[pc + 1] % 16)
            v_x = read_uint_jit(code, pc + 2, 8)

            if opcode == op_load_imm_64:
                reg[r_a] = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.4
        elif inst_type == inst_imm_imm:
            l_x = min(4, code[pc + 1] % 8)
            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), np.uint8(l_y))

            if opcode == op_store_imm_u8:
                if mem_write_jit(v_x, U64(v_y) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    __s1, __v1 = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, imm1=v_x, imm2=v_y, context="u'_vx: " + str(__v1),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            elif opcode == op_store_imm_u16:
                if mem_write_jit(v_x, U64(v_y) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    __s2, __v2 = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, imm1=v_x, imm2=v_y, context="u'_vx: " + str(__v2),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            elif opcode == op_store_imm_u32:
                if mem_write_jit(v_x, U64(v_y) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    __s4, __v4 = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, imm1=v_x, imm2=v_y, context="u'_vx: " + str(__v4),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            elif opcode == op_store_imm_u64:
                if mem_write_jit(v_x, v_y, U8(8), mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    __s8, __v8 = mem_read_jit(v_x, U8(8), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, imm1=v_x, imm2=v_y, context="u'_vx: " + str(__v8),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.5
        elif inst_type == inst_offset:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == op_jump:
                skip_len = v_x
                if logg: log(logging, local_state, reg, off1=v_x, context="skip_len: " + str(v_x),
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.6
        elif inst_type == inst_reg_imm:
            r_a = min(12, code[pc + 1] % 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))

            if opcode == op_jump_ind:
                jump_target = U32(((U64(reg[r_a]) + U64(v_x)) & U32_MASK)) #!!!!!!!!!!!!!!mogegijk anders? 128bit wraparound?
                djump_result = djump_jit(jump_target, jump_table, pc, pc_to_inst_index)
                if djump_result == I32(-1):
                    skip_len = I64(0)
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_HALT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_NONE)
                elif djump_result == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_DJUMP)
                else:
                    skip_len = djump_result
                    if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x,
                                    context="skip_len: " + str(djump_result), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_imm:
                reg[r_a] = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_u8:
                status_read, loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT,
                                                 pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_i8:
                status_read, loaded_value = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(1))
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_u16:
                status_read, loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value

            elif opcode == op_load_i16:
                status_read, loaded_value = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(2))
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_u32:
                status_read, loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_i32:
                status_read, loaded_value = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_X_jit(loaded_value, U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_u64:
                status_read, loaded_value = mem_read_jit(v_x, U8(8), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_u8:
                if mem_write_jit(v_x, U64(reg[r_a]) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    _rs1, _rv1 = mem_read_jit(v_x, U8(1), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, reg1=r_a, imm1=v_x, context="u'_vx: " + str(_rv1),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_u16:
                if mem_write_jit(v_x, U64(reg[r_a]) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    _rs2, _rv2 = mem_read_jit(v_x, U8(2), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, reg1=r_a, imm1=v_x, context="u'_vx: " + str(_rv2),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_u32:
                if mem_write_jit(v_x, U64(reg[r_a]) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    _rs4, _rv4 = mem_read_jit(v_x, U8(4), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, reg1=r_a, imm1=v_x, context="u'_vx: " + str(_rv4),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_u64:
                if mem_write_jit(v_x, reg[r_a], U8(8), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg:
                    _rs8, _rv8 = mem_read_jit(v_x, U8(8), mem_section_starts, mem_section_ends, section_arrays,
                                              acl_array, acl_extra_start, acl_extra_count)
                    log(logging, local_state, reg, reg1=r_a, imm1=v_x, context="u'_vx: " + str(_rv8),
                        mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                if mem_write_jit(store_addr, U64(v_y) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends,
                                 section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, imm2=v_y,
                                context="u'_vx: " + str(
                                    mem_read_jit(store_addr, U8(1), mem_section_starts, mem_section_ends,
                                                section_arrays, acl_array, acl_extra_start, acl_extra_count)), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_imm_ind_u16:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr, U64(v_y) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends,
                                 section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, imm2=v_y,
                                context="u'_vx: " + str(
                                    mem_read_jit(store_addr, U8(2), mem_section_starts, mem_section_ends,
                                                 section_arrays, acl_array, acl_extra_start, acl_extra_count)), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_imm_ind_u32:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr, U64(v_y) & U32_MASK, U8(4), mem_section_starts, mem_section_ends,
                                 section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, imm2=v_y,
                                context="u'_vx: " + str(
                                    mem_read_jit(store_addr, U8(4), mem_section_starts, mem_section_ends,
                                                 section_arrays, acl_array, acl_extra_start, acl_extra_count)), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_imm_ind_u64:
                store_addr = (U64(w_a) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr, v_y, U8(8), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, imm2=v_y,
                                context="u'_vx: " + str(
                                    mem_read_jit(store_addr, U8(8), mem_section_starts, mem_section_ends,
                                                 section_arrays, acl_array, acl_extra_start, acl_extra_count)), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_eq_imm:
                branch_result = branch_jit(pc, v_y, w_a == v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a == v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_ne_imm:
                branch_result = branch_jit(pc, v_y, w_a != v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a != v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_lt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a < v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a < v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_le_u_imm:
                branch_result = branch_jit(pc, v_y, w_a <= v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a <= v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_ge_u_imm:
                branch_result = branch_jit(pc, v_y, w_a >= v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a >= v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_gt_u_imm:
                branch_result = branch_jit(pc, v_y, w_a > v_x, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a > v_x:
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_lt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) < pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) < pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_le_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) <= pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) <= pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_ge_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) >= pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) >= pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_branch_gt_s_imm:
                branch_result = branch_jit(pc, v_y, pvm_Z_jit(w_a, 8) > pvm_Z_jit(v_x, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) > pvm_Z_jit(v_x, 8):
                    skip_len = v_y
                if logg: log(logging, local_state, reg, reg1=r_a, imm1=v_x, off1=v_y,
                                mem=section_arrays)

            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC,
                                             pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

        # GP-0.6.7-section:A.5.9
        elif inst_type == inst_reg_reg:

            r_d = min(12, code[pc + 1] % 16)
            r_a = min(12, code[pc + 1] // 16)

            if opcode == op_move_reg:
                reg[r_d] = reg[r_a]
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_sbrk:
                size = reg[r_a]
                current_heap_ptr = heap_info[0]
                next_section_start = heap_info[1]
                mem_writable_value = I64(heap_info[2])

                new_heap_ptr, grew_bytes = sbrk_jit(size, current_heap_ptr, next_section_start,
                                                    mem_writable_value, section_arrays, mem_section_starts)
                reg[r_d] = new_heap_ptr

                if new_heap_ptr != U64(0):
                    heap_info[0] = new_heap_ptr
                    mem_section_ends[1] = new_heap_ptr
                    if grew_bytes > I64(0):
                        heap_grew_out[0] += grew_bytes
                        start_page = int(current_heap_ptr >> PVM_PAGE_SHIFT)
                        pages = int((int(grew_bytes) + PVM_PAGE_SIZE - 1) >> PVM_PAGE_SHIFT)

                        existing_start = int(acl_extra_start[0])
                        existing_count = int(acl_extra_count[0])
                        if existing_count == 0:
                            acl_extra_start[0] = start_page
                            acl_extra_count[0] = pages
                        else:
                            new_start = existing_start
                            new_end = existing_start + existing_count
                            if start_page < new_start:
                                new_start = start_page
                            candidate_end = start_page + pages
                            if candidate_end > new_end:
                                new_end = candidate_end
                            acl_extra_start[0] = new_start
                            acl_extra_count[0] = new_end - new_start

                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_count_set_bits_64:
                # TODO: !!!!!!!!!!!!!!!!!!!!!!!!!!!helper function: bit counting (np.bitwise_count not available in numba)
                val = reg[r_a]
                count = U64(0)
                for _ in range(64):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_count_set_bits_32:
                # TODO: !!!!!!!!!!!!!!!!!!!!helper function: bit counting (np.bitwise_count not available in numba)
                val = U32(U64(reg[r_a]) & U32_MASK)
                count = U64(0)
                for _ in range(32):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_leading_zero_bits_64:
                reg[r_d] = count_leading_zeroes_jit(reg[r_a], U8(64))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_leading_zero_bits_32:
                reg[r_d] = count_leading_zeroes_jit(U64(reg[r_a]) & U32_MASK, U8(32))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_trailing_zero_bits_64:
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a], U8(64))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_trailing_zero_bits_32:
                reg[r_d] = count_trailing_zeroes_jit(U64(reg[r_a]) & U32_MASK, U8(32))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_sign_extend_8:
                # todo: !!!!!!!!!!!!!!!!!!!reg[r_d] = pvm_X_jit(reg[r_a], U8(1))
                reg[r_d] = pvm_Z_inv_jit(pvm_Z_jit(U64(reg[r_a]) & U64(0xFF), 1), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_sign_extend_16:
                # todo: !!!!!!!!!!!!!!!reg[r_d] = pvm_X_jit(reg[r_a], U8(2))
                reg[r_d] = pvm_Z_inv_jit(pvm_Z_jit(U64(reg[r_a]) & U64(0xFFFF), 2), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_zero_extend_16:
                # reg[r_d] = reg[r_a] & U64(0xFFFF)
                reg[r_d] = U64(reg[r_a]) & U64(0xFFFF)
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_reverse_bytes:
                reg[r_d] = reverse_bytes_jit(reg[r_a])
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                if mem_write_jit(store_addr, U64(w_a) & U64(0xFF), U8(1), mem_section_starts, mem_section_ends,
                                 section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a % (2 ** 8)) + " w_b: " + str(w_b), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_ind_u16:
                store_addr =(U64(w_b) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr, U64(w_a) & U64(0xFFFF), U8(2), mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(U64(w_a) & U64(0xFFFF)) + " w_b: " + str(w_b), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_ind_u32:
                store_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr,  U64(w_a) & U32_MASK, U8(4), mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(U64(w_a) & U32_MASK) + " w_b: " + str(w_b), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_store_ind_u64:
                store_addr =  (U64(w_b) + U64(v_x)) & U64_MASK
                if mem_write_jit(store_addr, w_a, U8(8), mem_section_starts, mem_section_ends, section_arrays,
                                 acl_array, acl_extra_start, acl_extra_count) < 0:
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_load_ind_u8:
                load_addr =  (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(1), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_i8:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(1), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 1), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_u16:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(2), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_i16:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(2), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 2), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_u32:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(4), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_i32:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(4), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = pvm_Z_inv_jit(pvm_Z_jit(loaded_value, 4), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_load_ind_u64:
                load_addr = (U64(w_b) + U64(v_x)) & U64_MASK
                status_read, loaded_value = mem_read_jit(load_addr, U8(8), mem_section_starts, mem_section_ends,
                                                         section_arrays, acl_array, acl_extra_start, acl_extra_count)
                if status_read != I32(0):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PAGE_FAULT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_MEMORY_FAULT)
                reg[r_a] = loaded_value
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_a: " + str(w_a) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_add_imm_32:
                #TODO!!!!!!!!!!!!!!!!!!
                wb_vx_32 = (U64(w_b) + U64(v_x)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(wb_vx_32), np.uint8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays, mem_starts=mem_section_starts, mem_ends=mem_section_ends)

            elif opcode == op_and_imm:
                reg[r_a] = w_b & v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_xor_imm:
                reg[r_a] = w_b ^ v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_or_imm:
                reg[r_a] = w_b | v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_mul_imm_32:
                # TODO!!!!!!!!!!!!!!!!!!
                prod32 = (U64(w_b) * U64(v_x)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(prod32), np.uint8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_set_lt_u_imm:
                reg[r_a] = U64(1) if w_b < v_x else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_set_lt_s_imm:
                reg[r_a] = U64(1) if pvm_Z_jit(w_b, 8) < pvm_Z_jit(v_x, 8) else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_l_imm_32:
                sh = U64(v_x) & U64(31)
                reg[r_a] = pvm_X_jit(U32((U64(w_b) << sh) & U32_MASK), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_r_imm_32:
                # TODO!!!!!!!!!!?
                reg[r_a] = pvm_X_jit(U32(w_b) >> U32(U32(v_x) & U32(31)), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shar_r_imm_32:
                reg[r_a] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(w_b), 4)) >> I64(U32(v_x) & U32(31)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_neg_add_imm_32:
                diff32 = (U64(v_x) - U64(w_b)) & U32_MASK
                reg[r_a] = pvm_X_jit(U32(diff32), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_set_gt_u_imm:
                reg[r_a] = U64(1) if w_b > v_x else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_set_gt_s_imm:
                reg[r_a] = U64(1) if pvm_Z_jit(w_b, 8) > pvm_Z_jit(v_x, 8) else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_l_imm_alt_32:
                sh = U64(w_b) & U64(31)
                reg[r_a] = pvm_X_jit(U32((U64(v_x) << sh) & U32_MASK), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_r_imm_alt_32:
                reg[r_a] = pvm_X_jit(U32(v_x) >> U32(U32(w_b) & U32(31)), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shar_r_imm_alt_32:
                reg[r_a] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(v_x), 4)) >> I64(U32(w_b) & U32(31)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_cmov_iz_imm:
                if w_b == 0:
                    reg[r_a] = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_cmov_nz_imm:
                if w_b != 0:
                    reg[r_a] = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_add_imm_64:
                reg[r_a] = (U64(w_b) + U64(v_x)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_mul_imm_64:
                reg[r_a] = (U64(w_b) * U64(v_x)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_l_imm_64:
                # TODO!!!!!!!!!!!!!!!!!!
                sh = U64(v_x) & U64(63)
                reg[r_a] = (U64(w_b) << sh) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_r_imm_64:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_a] = U64(w_b) >> U64(U64(v_x) & U64(63))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shar_r_imm_64:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_a] = pvm_Z_inv_jit(I64(pvm_Z_jit(w_b, 8)) >> I64(U64(v_x) & U64(63)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_neg_add_imm_64:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_a] = (U64(v_x) - U64(w_b)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_l_imm_alt_64:
                # TODO!!!!!!!!!!!!!!!!!!
                sh = U64(w_b) & U64(63)
                reg[r_a] = (U64(v_x) << sh) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shlo_r_imm_alt_64:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_a] = v_x >> U64(w_b & U64(63))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_shar_r_imm_alt_64:
                reg[r_a] = pvm_Z_inv_jit(I64(pvm_Z_jit(v_x, 8)) >> I64(U64(w_b) & U64(63)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_rot_r_64_imm:
                reg[r_a] = rori64_jit(w_b, v_x)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_rot_r_64_imm_alt:
                reg[r_a] = rori64_jit(v_x, w_b)
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_rot_r_32_imm:
                reg[r_a] = pvm_X_jit(rori32_jit(U32(w_b), U32(v_x)), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            elif opcode == op_rot_r_32_imm_alt:
                reg[r_a] = pvm_X_jit(rori32_jit(U32(v_x), U32(w_b)), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x,
                                context="w'_a: " + str(reg[r_a]) + " w_b: " + str(w_b), mem=section_arrays)

            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a == w_b:
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            elif opcode == op_branch_ne:
                branch_result = branch_jit(pc, v_x, w_a != w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a != w_b:
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            elif opcode == op_branch_lt_u:
                branch_result = branch_jit(pc, v_x, w_a < w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a < w_b:
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            elif opcode == op_branch_lt_s:
                branch_result = branch_jit(pc, v_x, pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8):
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            elif opcode == op_branch_ge_u:
                branch_result = branch_jit(pc, v_x, w_a >= w_b, pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif w_a >= w_b:
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            elif opcode == op_branch_ge_s:
                branch_result = branch_jit(pc, v_x, pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8), pc_to_inst_index)
                if branch_result == I32(-1):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_BRANCH)
                elif pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8):
                    skip_len = v_x
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, off1=v_x,
                                context="skip_len: " + str(skip_len), mem=section_arrays)

            else:
                # Invalid opcode
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_HALT, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_NONE)
                elif djump_result == I32(-2):
                    return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                                 exit_value, skip_len, ERROR_PANIC_INVALID_DJUMP)
                else:
                    skip_len = djump_result
                if logg: log(logging, local_state, reg, reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y,
                                context="skip_len: " + str(skip_len), mem=section_arrays)
            else:
                if logg: log(logging, local_state, reg, context="error: unknown opcode",
                                mem=section_arrays)
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

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
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_sub_32:
                # TODO!!!!!!!!!!!!!!!!!!
                wa_minus_wb_32 = (U64(w_a) - U64(w_b)) & U32_MASK
                reg[r_d] = pvm_X_jit(U32(wa_minus_wb_32), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_mul_32:
                # TODO!!!!!!!!!!!!!!!!!!
                prod32 = (U64(w_a) * U64(w_b)) & U32_MASK
                reg[r_d] = pvm_X_jit(U32(prod32), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_div_u_32:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = pvm_X_jit(U32(w_a) // U32(w_b), U8(4))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_div_s_32:
                # TODO!!!!!!!!!!!!!!!!!!
                a_signed = I32(pvm_Z_jit((U64(w_a) & U32_MASK), 4))
                b_signed = I32(pvm_Z_jit((U64(w_b) & U32_MASK), 4))

                if b_signed == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                elif a_signed == I32(-2 ** 31) and b_signed == I32(-1):
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_rtz_div_jit(I64(a_signed), I64(b_signed)), U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rem_u_32:
                wb32 = U64(w_b) & U32_MASK
                if wb32 == 0:
                    reg[r_d] = pvm_X_jit(U32(U64(w_a) & U32_MASK), U8(4))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    wa32 = U64(w_a) & U32_MASK
                    reg[r_d] = pvm_X_jit(U32(wa32 % wb32), U8(4))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rem_s_32:
                a_signed = pvm_Z_jit((U64(w_a) & U32_MASK), 4)
                b_signed = pvm_Z_jit((U64(w_b) & U32_MASK), 4)

                if b_signed == 0:
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                elif a_signed == I64(-2 ** 31) and b_signed == I64(-1):
                    reg[r_d] = U64(0)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_smod_jit(a_signed, b_signed), U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shlo_l_32:
                sh = U64(w_b) & U64(31)
                reg[r_d] = pvm_X_jit(U32((U64(w_a) << sh) & U32_MASK), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shlo_r_32:
                reg[r_d] = pvm_X_jit(U32(w_a) >> U32(U32(w_b) & U32(31)), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shar_r_32:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_d] = pvm_Z_inv_jit(I32(pvm_Z_jit(U32(w_a), 4)) >> I64(U32(w_b) & U32(31)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_add_64:
                reg[r_d] =(U64(w_a) + U64(w_b)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_sub_64:
                # TODO!!!!!!!!!!!!!!!!!!
                reg[r_d] = (U64(w_a) - U64(w_b)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_mul_64:
                reg[r_d] = (U64(w_a) * U64(w_b)) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_div_u_64:
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = w_a // w_b
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_div_s_64:
                # TODO!!!!!!!!!!!!!!!!!!
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                elif pvm_Z_jit(w_a, 8) == I64(-9223372036854775808) and pvm_Z_jit(w_b, 8) == I64(-1):
                    reg[r_d] = w_a  # Overflow case
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_rtz_div_jit(pvm_Z_jit(w_a, 8), pvm_Z_jit(w_b, 8)), U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rem_u_64:
                if w_b == 0:
                    reg[r_d] = w_a
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = w_a % w_b
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rem_s_64:
                a_signed = pvm_Z_jit(w_a, 8)
                b_signed = pvm_Z_jit(w_b, 8)
                if b_signed == 0:
                    reg[r_d] = pvm_Z_inv_jit(a_signed, U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                elif a_signed == I64(-9223372036854775808) and b_signed == I64(-1):
                    reg[r_d] = U64(0)
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)
                else:
                    reg[r_d] = pvm_Z_inv_jit(pvm_smod_jit(a_signed, b_signed), U8(8))
                    if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                    context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shlo_l_64:
                sh = U64(w_b) & U64(63)
                reg[r_d] = (U64(w_a) << sh) & U64_MASK
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shlo_r_64:
                reg[r_d] = U64(w_a) >> U64(U64(w_b) & U64(63))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_shar_r_64:
                reg[r_d] = pvm_Z_inv_jit(I64(pvm_Z_jit(w_a, 8)) >> I64(U64(w_b) & U64(63)), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_and:
                reg[r_d] = w_a & w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_xor:
                reg[r_d] = w_a ^ w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_or:
                reg[r_d] = w_a | w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_mul_upper_s_s:
                # TODO!!!!!!!!!!!!!!!!!!
                hi, lo = imul64wide_jit(I64(w_a), I64(w_b))
                reg[r_d] = pvm_Z_inv_jit(I64(hi), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_mul_upper_u_u:
                # TODO!!!!!!!!!!!!!!!!!!
                hi, lo = umul64wide_jit(w_a, w_b)
                reg[r_d] = hi
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_mul_upper_s_u:
                # TODO!!!!!!!!!!!!!!!!!!
                hi, lo = smul_u64wide_jit(I64(w_a), w_b)
                reg[r_d] = pvm_Z_inv_jit(I64(hi), U8(8))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_set_lt_u:
                reg[r_d] = U64(1) if w_a < w_b else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_set_lt_s:
                reg[r_d] = U64(1) if pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8) else U64(0)
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_cmov_iz:
                if w_b == 0:
                    reg[r_d] = w_a
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_cmov_nz:
                if w_b != 0:
                    reg[r_d] = w_a
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rot_l_64:
                reg[r_d] = roli64_jit(w_a, U64(w_b) & U64(63))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rot_l_32:
                reg[r_d] = pvm_X_jit(roli32_jit(U32(w_a), U32(U32(w_b) & U32(31))), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rot_r_64:
                reg[r_d] = rori64_jit(w_a, U64(w_b) & U64(63))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_rot_r_32:
                reg[r_d] = pvm_X_jit(rori32_jit(U32(w_a), U32(U32(w_b) & U32(31))), U8(4))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_and_inv:
                reg[r_d] = w_a & U64(~w_b)
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_or_inv:
                reg[r_d] = w_a | U64(~w_b)
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_xnor:
                reg[r_d] = U64(~(w_a ^ w_b))
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_max:
                reg[r_d] = w_a if pvm_Z_jit(w_a, 8) >= pvm_Z_jit(w_b, 8) else w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_max_u:
                reg[r_d] = w_a if w_a >= w_b else w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_min:
                reg[r_d] = w_a if pvm_Z_jit(w_a, 8) <= pvm_Z_jit(w_b, 8) else w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            elif opcode == op_min_u:
                reg[r_d] = w_a if w_a <= w_b else w_b
                if logg: log(logging, local_state, reg, reg1=r_d, reg2=r_a, reg3=r_d,
                                context="w'_d: " + str(reg[r_d]), mem=section_arrays)

            else:
                return sync_state_and_return(reg, registers_out, state_out, EXIT_PANIC, pc, gas, inst_nr,
                                             exit_value, skip_len, ERROR_PANIC_TRAP)

    # Copy output state
    for i in range(len(reg)):
        registers_out[i] = reg[i]
    state_out[STATE_STATUS] = I64(status)
    state_out[STATE_PC] = I64(pc)
    state_out[STATE_GAS] = I64(gas)
    state_out[STATE_INST_NR] = I64(inst_nr)
    state_out[STATE_EXIT_VALUE] = I64(exit_value)
    state_out[STATE_SKIP_LEN] = I64(skip_len)
    state_out[STATE_ERROR] = I64(ERROR_NONE)

    return ERROR_NONE


class PVMInterpreter(PVMInterpreterBase):
    """
    Pure JIT-optimized PVM interpreter using Numba compilation only.
    No fallback to Python interpreter.
    """
    ttt = -1
    tttt = 0

    def __init__(self, program: PVMProgram, logger=None):
        """Initialize the interpreter with a program."""
        super().__init__(program, logger)
        self._prepare_jit_data()
        self._jit_mem_cache_dirty = True
        self._jit_section_starts_cache = None
        self._jit_section_ends_cache = None
        self._jit_section_arrays_cache = None
        self._jit_acl_array_cache = None

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
        Build (or reuse) JIT-ready section references.
        Returns: section_starts, section_ends, section_arrays, acl_array
        """
        if (not self._jit_mem_cache_dirty and
                self._jit_section_arrays_cache is not None and
                self._jit_section_starts_cache is not None and
                self._jit_section_ends_cache is not None and
                self._jit_acl_array_cache is not None):
            return (self._jit_section_starts_cache,
                    self._jit_section_ends_cache,
                    self._jit_section_arrays_cache,
                    self._jit_acl_array_cache)

        starts = []
        ends = []
        arrays = List.empty_list(types.uint8[::1])

        acl_array = self._build_acl_array()

        for i, section in enumerate(self.mem_sections):
            if section is None:
                continue
            start_addr = self.mem_section_starts[i]
            end_addr = self.mem_section_ends[i]
            buf = _ensure_uint8_array(section)
            # Keep Python-side reference updated so both views share storage
            self.mem_sections[i] = buf

            starts.append(np.uint64(start_addr))
            ends.append(np.uint64(end_addr))
            arrays.append(buf)

        self._jit_section_starts_cache = np.asarray(starts, dtype=np.uint64)
        self._jit_section_ends_cache = np.asarray(ends, dtype=np.uint64)
        self._jit_section_arrays_cache = arrays
        self._jit_acl_array_cache = acl_array
        self._jit_mem_cache_dirty = False

        return (self._jit_section_starts_cache,
                self._jit_section_ends_cache,
                self._jit_section_arrays_cache,
                self._jit_acl_array_cache)

    def _build_acl_array(self) -> np.ndarray:
        # Estimate required number of pages from current sections and ACL map
        max_page = 0
        ends = getattr(self, 'mem_section_ends', None)
        if ends is not None and len(ends) > 0:
            max_end = max(int(x) for x in ends)
            max_page = max(max_page, int((max_end + PVM_PAGE_SIZE - 1) >> PVM_PAGE_SHIFT))

        starts = getattr(self, 'mem_section_starts', None)
        if starts is not None and len(starts) > 2:
            next_section_start = int(starts[2])
            if next_section_start > 0:
                max_page = max(max_page, int((next_section_start + PVM_PAGE_SIZE - 1) >> PVM_PAGE_SHIFT))

        if self.mem_acl:
            max_page = max(max_page, max(self.mem_acl.keys()) + 1)

        if max_page == 0:
            max_page = 1

        if self.mem_acl:
            arr = np.full(max_page, MEM_INACCESSIBLE, dtype=np.int32)
            for page, perm in self.mem_acl.items():
                if 0 <= page < len(arr):
                    arr[page] = int(perm)
        else:
            arr = np.full(max_page, MEM_WRITABLE, dtype=np.int32)

        return arr

    def invoke(self, pc: int, gas: int):
        """
        Pure JIT invoke that uses only Numba compilation.
        No fallback to Python interpreter.
        """
        self.pc = pc
        self.gas = gas

        jump_table_array = np.array(self.jump_table, dtype=np.int32)

        # Prepare heap info (for sbrk)
        current_heap_end = self.mem_section_ends[1] if len(self.mem_section_ends) > 1 else 0
        heap_info = np.array([
            current_heap_end,  # current heap end
            self.mem_section_starts[2] if len(self.mem_section_starts) > 2 else 0xFFFFFFFF,  # next section start
            MEM_WRITABLE  # writable permission value
        ], dtype=np.uint64)

        # Prepare memory arrays for JIT
        mem_section_starts, mem_section_ends, section_arrays, acl_array = self._prepare_memory_for_jit()

        acl_extra_start = np.array([0], dtype=np.int32)
        acl_extra_count = np.array([0], dtype=np.int32)

        registers_out = np.zeros(13, dtype=np.uint64)
        # state_out holds: [status, pc, gas, inst_nr, exit_value, skip_len, error_code]
        state_out = np.array([0, 0, 0, 0, 0, 0, 0], dtype=np.int64)
        heap_grew_out = np.array([0], dtype=np.int64)

        opcode_names = Dict.empty(
            key_type=types.int64,
            value_type=types.unicode_type,
        )
        # if self.log:
        #     for _k, _v in OpcodeNames.items():
        #         opcode_names[int(_k)] = _v

        # Convert mem_ops arrays to int64 for JIT compatibility
        mem_ops_read_int64 = np.asarray(self.mem_ops_read, dtype=np.int64, order='C')
        mem_ops_write_int64 = np.asarray(self.mem_ops_write, dtype=np.int64, order='C')
        mem_ops_bytes_int64 = np.asarray(self.mem_ops_bytes, dtype=np.int64, order='C')

        # Call JIT-compiled function
        error_code = invoke_native_jit(
            np.uint32(self.pc), np.int64(self.gas), np.uint32(self.inst_nr), np.uint32(int(self.skip_len)),
            self.code, np.uint32(self.code_size),
            self.inst_pos_keys, self.inst_pos_vals, self.inst_arg_len_array, self.pc_to_inst_index,
            self.opcode_scheme_array, jump_table_array,
            mem_ops_read_int64, mem_ops_write_int64, mem_ops_bytes_int64,
            mem_section_starts, mem_section_ends, section_arrays, acl_array, acl_extra_start, acl_extra_count,
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
        growth_bytes = int(heap_grew_out[0])
        if growth_bytes > 0 and section_arrays is not None:
            # Adopt the grown buffer from the JIT without copying
            self.mem_sections[1] = section_arrays[1]
            self._jit_mem_cache_dirty = True
        elif self.mem_sections and self.mem_sections[1] is not None:
            current_len = len(self.mem_sections[1])
            desired_len = int(self.mem_section_ends[1] - self.mem_section_starts[1])
            if desired_len > current_len:
                growth = desired_len - current_len
                self.mem_sections[1] = np.concatenate((self.mem_sections[1], np.zeros(growth, dtype=np.uint8)))
                self._jit_mem_cache_dirty = True

        new_heap_end = int(heap_info[0])
        extra_start_page = int(acl_extra_start[0])
        extra_page_count = int(acl_extra_count[0])

        if growth_bytes > 0 and extra_page_count > 0:
            if hasattr(self, 'mem_acl') and self.mem_acl is not None:
                start_page = extra_start_page
                end_page = start_page + extra_page_count + 1
                for page in range(start_page, end_page):
                    self.mem_acl[page] = MEM_WRITABLE

        self._sync_memory()
