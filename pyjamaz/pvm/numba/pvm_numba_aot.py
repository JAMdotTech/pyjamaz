"""
AOT compilation module for all Numba JIT functions in interpreter_numba.py.
This uses numba.pycc to compile all functions ahead of time.
"""

import numpy as np
import numba.types
from numba.pycc import CC

# Create the compilation unit
cc = CC('pvm_numba_aot')

# Enable verbose output to see compilation progress
cc.verbose = True

# Define type aliases for cleaner signatures
types = numba.types
u8 = types.uint8
u16 = types.uint16
u32 = types.uint32
u64 = types.uint64
i8 = types.int8
i16 = types.int16
i32 = types.int32
i64 = types.int64
f64 = types.float64

# Array types
u8_array = types.Array(u8, 1, 'C')
u64_array = types.Array(u64, 1, 'C')
i32_array = types.Array(i32, 1, 'C')

# Constants (must match interpreter_numba.py)
U64_MAX = (1 << 64) - 1
I64_MAX = (1 << 63) - 1
I64_MIN = -(1 << 63)
MEM_WRITABLE = 2

# 1. umul64wide
@cc.export('umul64wide', (u64, u64))
def umul64wide(a, b):
    """Compute (high, low) 128-bit result of a*b where a,b are U64."""
    mask32 = np.uint64((1 << 32) - 1)
    
    a_lo = a & mask32
    a_hi = a >> np.uint64(32)
    b_lo = b & mask32
    b_hi = b >> np.uint64(32)
    
    p00 = a_lo * b_lo
    p01 = a_lo * b_hi
    p10 = a_hi * b_lo
    p11 = a_hi * b_hi
    
    p00_lo = p00 & mask32
    p00_hi = p00 >> np.uint64(32)
    
    mid = p00_hi + (p01 & mask32) + (p10 & mask32)
    mid_lo = mid & mask32
    mid_hi = mid >> np.uint64(32)
    
    low = (mid_lo << np.uint64(32)) | p00_lo
    high = p11 + (p01 >> np.uint64(32)) + (p10 >> np.uint64(32)) + mid_hi
    
    return high, low

# 2. imul64wide
@cc.export('imul64wide', (i64, i64))
def imul64wide(a, b):
    """Compute 128-bit product of two I64, return Tuple[U64, U64]."""
    a_neg = a < 0
    b_neg = b < 0
    
    if a_neg:
        a = -a
    if b_neg:
        b = -b
    
    # Inline umul64wide to avoid cross-function reference issues in AOT
    ua = np.uint64(a)
    ub = np.uint64(b)
    mask32 = np.uint64((1 << 32) - 1)
    
    a_lo = ua & mask32
    a_hi = ua >> np.uint64(32)
    b_lo = ub & mask32
    b_hi = ub >> np.uint64(32)
    
    p00 = a_lo * b_lo
    p01 = a_lo * b_hi
    p10 = a_hi * b_lo
    p11 = a_hi * b_hi
    
    p00_lo = p00 & mask32
    p00_hi = p00 >> np.uint64(32)
    
    mid = p00_hi + (p01 & mask32) + (p10 & mask32)
    mid_lo = mid & mask32
    mid_hi = mid >> np.uint64(32)
    
    low = (mid_lo << np.uint64(32)) | p00_lo
    high = p11 + (p01 >> np.uint64(32)) + (p10 >> np.uint64(32)) + mid_hi
    
    if a_neg != b_neg:
        low_comp = ~low
        high_comp = ~high
        
        low_comp = low_comp + np.uint64(1)
        if low_comp == 0:
            high_comp = high_comp + np.uint64(1)
        
        high = high_comp
        low = low_comp
    
    return high, low

# 3. smul_u64wide
@cc.export('smul_u64wide', (i64, u64))
def smul_u64wide(a, b):
    """Compute 128-bit product of I64 * U64, return Tuple[U64, U64]."""
    if a >= 0:
        # Inline umul64wide
        ua = np.uint64(a)
        mask32 = np.uint64((1 << 32) - 1)
        
        a_lo = ua & mask32
        a_hi = ua >> np.uint64(32)
        b_lo = b & mask32
        b_hi = b >> np.uint64(32)
        
        p00 = a_lo * b_lo
        p01 = a_lo * b_hi
        p10 = a_hi * b_lo
        p11 = a_hi * b_hi
        
        p00_lo = p00 & mask32
        p00_hi = p00 >> np.uint64(32)
        
        mid = p00_hi + (p01 & mask32) + (p10 & mask32)
        mid_lo = mid & mask32
        mid_hi = mid >> np.uint64(32)
        
        low = (mid_lo << np.uint64(32)) | p00_lo
        high = p11 + (p01 >> np.uint64(32)) + (p10 >> np.uint64(32)) + mid_hi
        return high, low
    
    a_abs = np.uint64(-a)
    # Inline umul64wide again
    mask32 = np.uint64((1 << 32) - 1)
    
    a_lo = a_abs & mask32
    a_hi = a_abs >> np.uint64(32)
    b_lo = b & mask32
    b_hi = b >> np.uint64(32)
    
    p00 = a_lo * b_lo
    p01 = a_lo * b_hi
    p10 = a_hi * b_lo
    p11 = a_hi * b_hi
    
    p00_lo = p00 & mask32
    p00_hi = p00 >> np.uint64(32)
    
    mid = p00_hi + (p01 & mask32) + (p10 & mask32)
    mid_lo = mid & mask32
    mid_hi = mid >> np.uint64(32)
    
    low = (mid_lo << np.uint64(32)) | p00_lo
    high = p11 + (p01 >> np.uint64(32)) + (p10 >> np.uint64(32)) + mid_hi
    
    low_comp = ~low
    high_comp = ~high
    
    low_comp = low_comp + np.uint64(1)
    if low_comp == 0:
        high_comp = high_comp + np.uint64(1)
    
    return high_comp, low_comp

# 4. rori64_jit
@cc.export('rori64_jit', u64(u64, u64))
def rori64_jit(x, shift_amount):
    shift_amount = shift_amount & np.uint64(63)
    if shift_amount == 0:
        return x
    return (x >> shift_amount) | (x << (np.uint64(64) - shift_amount))

# 5. roli64_jit
@cc.export('roli64_jit', u64(u64, u64))
def roli64_jit(x, shift_amount):
    shift_amount = shift_amount & np.uint64(63)
    if shift_amount == 0:
        return x
    return (x << shift_amount) | (x >> (np.uint64(64) - shift_amount))

# 6. rori32_jit
@cc.export('rori32_jit', u32(u32, u32))
def rori32_jit(x, shift_amount):
    shift_amount = shift_amount & np.uint32(31)
    if shift_amount == 0:
        return x
    return (x >> shift_amount) | (x << (np.uint32(32) - shift_amount))

# 7. roli32_jit
@cc.export('roli32_jit', u32(u32, u32))
def roli32_jit(x, shift_amount):
    shift_amount = shift_amount & np.uint32(31)
    if shift_amount == 0:
        return x
    return (x << shift_amount) | (x >> (np.uint32(32) - shift_amount))

# 8. pvm_smod_jit
@cc.export('pvm_smod_jit', i64(i64, i64))
def pvm_smod_jit(a, b):
    """PVM signed modulo: -2^63 % -1 = 0 (special case)"""
    if b == 0:
        return np.int64(0)
    if a == np.int64(I64_MIN) and b == np.int64(-1):
        return np.int64(0)
    return a % b

# 9. pvm_rtz_div_jit
@cc.export('pvm_rtz_div_jit', i64(i64, i64))
def pvm_rtz_div_jit(a, b):
    """Division rounding toward zero."""
    if b == 0:
        return np.int64(-1)
    
    if a == np.int64(I64_MIN) and b == np.int64(-1):
        return np.int64(I64_MIN)
    
    if (a < 0) != (b < 0):
        return -(-a // b) if a < 0 else -(a // -b)
    return a // b

# 10. pvm_X_jit
@cc.export('pvm_X_jit', u64(u64, u64))
def pvm_X_jit(x, n):
    """Sign-extend x based on n-bit width."""
    n = max(np.uint64(1), min(n, np.uint64(64)))
    
    if n == 64:
        return x
    
    value_mask = (np.uint64(1) << n) - np.uint64(1)
    x = x & value_mask
    
    sign_bit = np.uint64(1) << (n - np.uint64(1))
    if x & sign_bit:
        extension_mask = np.uint64(U64_MAX) ^ value_mask
        x = x | extension_mask
    
    return x

# 11. pvm_Z_jit
@cc.export('pvm_Z_jit', i64(u64, u64))
def pvm_Z_jit(a, n):
    """Interpret n-bit value as signed integer."""
    n = max(np.uint64(1), min(n, np.uint64(8)))
    
    if n >= 8:
        return np.int64(a)
    
    bit_width = n * np.uint64(8)
    value_mask = (np.uint64(1) << bit_width) - np.uint64(1)
    a = a & value_mask
    
    sign_bit = np.uint64(1) << (bit_width - np.uint64(1))
    if a & sign_bit:
        extension_mask = np.uint64(U64_MAX) ^ value_mask
        a = a | extension_mask
    
    return np.int64(a)

# 12. count_leading_zeroes_jit
@cc.export('count_leading_zeroes_jit', u64(u64, i64))
def count_leading_zeroes_jit(value, max_bits):
    if value == 0:
        return np.uint64(max_bits)
    
    count = np.uint64(0)
    for i in range(max_bits - 1, -1, -1):
        if value & (np.uint64(1) << i):
            break
        count += np.uint64(1)
    
    return count

# 13. count_trailing_zeroes_jit
@cc.export('count_trailing_zeroes_jit', u64(u64, i64))
def count_trailing_zeroes_jit(value, max_bits):
    if value == 0:
        return np.uint64(max_bits)
    
    count = np.uint64(0)
    for i in range(max_bits):
        if value & (np.uint64(1) << i):
            break
        count += np.uint64(1)
    
    return count

# 14. reverse_bytes_jit
@cc.export('reverse_bytes_jit', u64(u64))
def reverse_bytes_jit(x):
    return ((x & np.uint64(0x00000000000000FF)) << np.uint64(56) |
            (x & np.uint64(0x000000000000FF00)) << np.uint64(40) |
            (x & np.uint64(0x0000000000FF0000)) << np.uint64(24) |
            (x & np.uint64(0x00000000FF000000)) << np.uint64(8) |
            (x & np.uint64(0x000000FF00000000)) >> np.uint64(8) |
            (x & np.uint64(0x0000FF0000000000)) >> np.uint64(24) |
            (x & np.uint64(0x00FF000000000000)) >> np.uint64(40) |
            (x & np.uint64(0xFF00000000000000)) >> np.uint64(56))

# 15. read_uint_jit
@cc.export('read_uint_jit', u64(u8_array, u32, u8))
def read_uint_jit(code, addr, length):
    """Read unsigned integer of given length from code array."""
    addr32 = addr
    
    if length == 1:
        return np.uint64(code[addr32])
    
    elif length == 2:
        b0 = np.uint64(code[addr32])
        b1 = np.uint64(code[addr32 + np.uint32(1)])
        return b0 | (b1 << np.uint64(8))
    
    elif length == 3:
        b0 = np.uint64(code[addr32])
        b1 = np.uint64(code[addr32 + np.uint32(1)])
        b2 = np.uint64(code[addr32 + np.uint32(2)])
        return b0 | (b1 << np.uint64(8)) | (b2 << np.uint64(16))
    
    elif length == 4:
        b0 = np.uint64(code[addr32])
        b1 = np.uint64(code[addr32 + np.uint32(1)])
        b2 = np.uint64(code[addr32 + np.uint32(2)])
        b3 = np.uint64(code[addr32 + np.uint32(3)])
        return b0 | (b1 << np.uint64(8)) | (b2 << np.uint64(16)) | (b3 << np.uint64(24))
    
    else:  # length >= 8
        b0 = np.uint64(code[addr32 + np.uint32(0)])
        b1 = np.uint64(code[addr32 + np.uint32(1)])
        b2 = np.uint64(code[addr32 + np.uint32(2)])
        b3 = np.uint64(code[addr32 + np.uint32(3)])
        b4 = np.uint64(code[addr32 + np.uint32(4)])
        b5 = np.uint64(code[addr32 + np.uint32(5)])
        b6 = np.uint64(code[addr32 + np.uint32(6)])
        b7 = np.uint64(code[addr32 + np.uint32(7)])
        return (b0 | (b1 << np.uint64(8)) | (b2 << np.uint64(16)) | (b3 << np.uint64(24)) |
                (b4 << np.uint64(32)) | (b5 << np.uint64(40)) | (b6 << np.uint64(48)) | (b7 << np.uint64(56)))

# 16. riscv_div_jit
@cc.export('riscv_div_jit', i64(i64, i64))
def riscv_div_jit(a, b):
    """RISC-V division semantics."""
    if b == 0:
        return np.int64(-1)
    
    if a == np.int64(I64_MIN) and b == np.int64(-1):
        return np.int64(I64_MIN)
    
    return a // b

# 17. pvm_Z_inv_jit
@cc.export('pvm_Z_inv_jit', u64(i64, u8))
def pvm_Z_inv_jit(a, n):
    """Pack signed integer into n bytes."""
    n = max(np.uint8(1), min(n, np.uint8(8)))
    
    if n >= 8:
        return np.uint64(a)
    
    bit_width = np.int32(n) * 8
    max_val = (1 << (bit_width - 1)) - 1
    min_val = -(1 << (bit_width - 1))
    
    a = max(min_val, min(a, max_val))
    
    return np.uint64(a) & ((np.uint64(1) << bit_width) - np.uint64(1))

# 18. find_memory_section_jit
@cc.export('find_memory_section_jit', i32(u64, u64_array, u64_array))
def find_memory_section_jit(addr, section_starts, section_ends):
    """Find which memory section contains the given address."""
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            return np.int32(i)
    return np.int32(-1)

# 19. _fmix64_jit
@cc.export('_fmix64_jit', u64(u64))
def _fmix64_jit(x):
    x = (x ^ (x >> np.uint64(33))) * np.uint64(0xff51afd7ed558ccd)
    x = (x ^ (x >> np.uint64(33))) * np.uint64(0xc4ceb9fe1a85ec53)
    x = x ^ (x >> np.uint64(33))
    return x

# 20. hash_memory_segment
@cc.export('hash_memory_segment', u64(u8_array))
def hash_memory_segment(section_array):
    """Simple hash function for memory segments."""
    h = np.uint64(0)
    for i in range(len(section_array)):
        h = h * np.uint64(31) + np.uint64(section_array[i])
    return h

# 21. sync_state_and_return
@cc.export('sync_state_and_return', i32(u64_array, u64_array, i32_array, i32, u32, u32, u32, u64, u32, i32))
def sync_state_and_return(reg, registers_out, state_out, exit_code, pc, gas, inst_nr, exit_value, skip_len, error_code):
    """Sync state and return from interpreter."""
    # Copy registers
    for i in range(min(len(reg), len(registers_out))):
        registers_out[i] = reg[i]
    
    # Set state values
    state_out[0] = exit_code
    state_out[1] = np.int32(pc)
    state_out[2] = np.int32(gas)
    state_out[3] = np.int32(inst_nr)
    state_out[4] = np.int32(exit_value)
    state_out[5] = np.int32(skip_len)
    
    return error_code

# 22. branch_jit
@cc.export('branch_jit', i32(u32, i64, types.boolean, i32_array))
def branch_jit(pc, offset, condition, pc_to_inst_index):
    """Compute branch target."""
    if not condition:
        return np.int32(-1)
    
    target_pc = np.int64(pc) + offset
    
    if target_pc < 0 or target_pc >= len(pc_to_inst_index):
        return np.int32(-2)
    
    target_inst = pc_to_inst_index[target_pc]
    if target_inst < 0:
        return np.int32(-2)
    
    return target_inst

if __name__ == '__main__':
    # Compile the module
    cc.compile()