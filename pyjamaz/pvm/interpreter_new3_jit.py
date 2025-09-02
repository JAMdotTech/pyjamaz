
"""
JIT-optimized PVM interpreter with Numba-compiled invoke_native function.
"""

import numpy as np
import numpy.typing as npt

from numba import njit

from .interpreter_new3 import PVMInterpreter as PVMInterpreterBase
from .types_new import PVMProgram
from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
from .constants_new import ExitReason, OpcodeScheme


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
def djump_jit(a: U32, jump_table, pc: U32, inst_pos_keys) -> I32:
    """JIT implementation of djump with validation."""
    halt_value = U32(2**32 - 2**16)
    if a == halt_value:
        return I32(-1)  # Special return code for halt
    
    # Check various invalid conditions
    if (a == 0 or 
        a >= len(jump_table) * 4 or  # PVM_DYNAMIC_ALIGNMENT_FACTOR = 4
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
            return ERROR_INVALID_OPCODE
        
        # Now we know we can proceed, so update state
        gas -= 1
        pc = next_pc
        inst_nr += 1

        # Fetch opcode and decode
        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = inst_arg_len[inst_index] + 1
        
        
        # Handle trap instruction immediately  
        if opcode == 0:  # trap - should always panic
            status = EXIT_PANIC
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            status_out[0] = status
            pc_out[0] = pc
            gas_out[0] = gas
            inst_nr_out[0] = inst_nr
            return ERROR_PANIC_TRAP

        # Process instructions by type
        # Type 0: InstructionType.none
        if inst_type == 0:
            if opcode == 0:  # trap
                status = EXIT_PANIC
                # Copy registers before returning
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
                inst_nr_out[0] = inst_nr
                return ERROR_PANIC_TRAP
            elif opcode == 1:  # fallthrough
                pass
            else:
                status = EXIT_PANIC
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
                return ERROR_INVALID_OPCODE

        # Type 1: InstructionType.imm
        elif inst_type == 1:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_X_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == 10:  # ecalli
                status = EXIT_HOST_HALT
                exit_value = v_x
            else:
                status = EXIT_PANIC
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
                return ERROR_INVALID_OPCODE

        # Type 2: InstructionType.reg_ext_imm
        elif inst_type == 2:
            r_a = min(12, code[pc + 1] % 16)
            v_x = read_uint_jit(code, pc + 2, 8)

            if opcode == 20:  # load_imm_64
                reg[r_a] = v_x
            else:
                status = EXIT_PANIC
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
                return ERROR_INVALID_OPCODE

        # Type 3: InstructionType.imm_imm
        elif inst_type == 3:
            l_x = min(4, code[pc + 1] % 8)
            l_y = min(4, max(0, inst_arg_len[inst_index] - l_x - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            v_y = pvm_X_jit(read_uint_jit(code, pc + 2 + l_x, l_y), np.uint8(l_y))
            
            # All type 3 opcodes are memory stores - fall back to Python for safety
            # Memory operations are complex and safer in Python
            for i in range(len(reg)):
                registers_out[i] = reg[i]
            status_out[0] = status
            exit_value_out[0] = exit_value
            pc_out[0] = pc  # PC already points to current instruction
            gas_out[0] = gas + 1  # Return gas before decrement  
            inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
            return ERROR_INVALID_OPCODE

        # Type 4: InstructionType.offset
        elif inst_type == 4:
            l_x = min(4, inst_arg_len[inst_index])
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 1, l_x), l_x)

            if opcode == 40:  # jump
                skip_len = v_x
            else:
                status = EXIT_PANIC
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
                return ERROR_INVALID_OPCODE

        # Type 5: InstructionType.reg_imm
        elif inst_type == 5:
            r_a = min(12, code[pc + 1] % 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))

            if opcode == 50:  # jump_ind
                jump_target = U32(reg[r_a] + v_x) % (2**32)
                djump_result = djump_jit(jump_target, jump_table, pc, inst_pos_keys)
                if djump_result == I32(-1):
                    status = EXIT_HALT
                elif djump_result == I32(-2):
                    status = EXIT_PANIC
                    for i in range(len(reg)):
                        registers_out[i] = reg[i]
                    status_out[0] = status
                    pc_out[0] = pc
                    gas_out[0] = gas
                    inst_nr_out[0] = inst_nr
                    return ERROR_PANIC_INVALID_DJUMP
                else:
                    skip_len = djump_result
            elif opcode == 51:  # load_imm
                reg[r_a] = v_x
            elif opcode == 52:  # load_u8
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 53:  # load_i8  
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 54:  # load_u16
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 55:  # load_i16
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 56:  # load_u32  
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 57:  # load_i32
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 58:  # load_u64
                # Memory load - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 59:  # store_u8
                # Memory store - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 60:  # store_u16
                # Memory store - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 61:  # store_u32
                # Memory store - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 62:  # store_u64
                # Memory store - fall back for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 90:  # add_imm
                reg[r_a] = (reg[r_a] + v_x) & U64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 91:  # add_imm_32
                reg[r_a] = pvm_X_jit((reg[r_a] + v_x) % (2**32), U8(4))
            elif opcode == 92:  # sub_imm  
                reg[r_a] = (reg[r_a] + U64(0xFFFFFFFFFFFFFFFF) - v_x + U64(1)) & U64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 93:  # and_imm
                reg[r_a] = reg[r_a] & v_x
            elif opcode == 94:  # xor_imm
                reg[r_a] = reg[r_a] ^ v_x
            elif opcode == 95:  # or_imm
                reg[r_a] = reg[r_a] | v_x
            elif opcode == 96:  # mul_imm
                reg[r_a] = (reg[r_a] * v_x) & U64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 97:  # set_lt_u_imm
                reg[r_a] = U64(1) if reg[r_a] < v_x else U64(0)
            elif opcode == 98:  # set_lt_s_imm
                reg[r_a] = U64(1) if pvm_Z_jit(reg[r_a], 8) < pvm_Z_jit(v_x, 8) else U64(0)
            elif opcode == 99:  # shlo_l_imm
                if v_x < 64:
                    reg[r_a] = (reg[r_a] << v_x) & U64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_a] = U64(0)
            # Note: Many more opcodes would need to be implemented here
            # For now, return error for unimplemented
            else:
                # Fall back to Python for complex operations - copy state first
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE

        # Type 8: InstructionType.reg_reg
        elif inst_type == 8:
            r_d = min(12, code[pc + 1] % 16)
            r_a = min(12, code[pc + 1] // 16)

            if opcode == 100:  # move_reg
                reg[r_d] = reg[r_a]
            elif opcode == 101:  # sbrk
                # Heap allocation - fall back to Python for now
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc
                gas_out[0] = gas + 1
                inst_nr_out[0] = inst_nr - 1
                return ERROR_INVALID_OPCODE
            elif opcode == 102:  # count_set_bits_64
                # Manual bit counting (np.bitwise_count not available in numba)
                val = reg[r_a]
                count = U64(0)
                for _ in range(64):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
            elif opcode == 103:  # count_set_bits_32
                val = U32(reg[r_a] % (2**32))
                count = U64(0)
                for _ in range(32):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
            elif opcode == 104:  # leading_zero_bits_64
                reg[r_d] = count_leading_zeroes_jit(reg[r_a])
            elif opcode == 105:  # leading_zero_bits_32
                reg[r_d] = count_leading_zeroes_jit(reg[r_a] % (2**32), 32)
            elif opcode == 106:  # trailing_zero_bits_64
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a])
            elif opcode == 107:  # trailing_zero_bits_32
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a] % (2**32), 32)
            elif opcode == 108:  # sign_extend_8
                reg[r_d] = pvm_X_jit(reg[r_a], U8(1))
            elif opcode == 109:  # sign_extend_16
                reg[r_d] = pvm_X_jit(reg[r_a], U8(2))
            elif opcode == 110:  # zero_extend_16
                reg[r_d] = reg[r_a] & U64(0xFFFF)
            elif opcode == 111:  # reverse_bytes
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
                return ERROR_INVALID_OPCODE

        # Type 9: InstructionType.reg_reg_imm
        elif inst_type == 9:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_X_jit(read_uint_jit(code, pc + 2, l_x), np.uint8(l_x))
            
            w_a = reg[r_a]
            w_b = reg[r_b]
            
            if opcode == 130:  # load_ind_u64
                # Memory operation - fall back to Python
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
            elif opcode == 131:  # add_imm_32
                reg[r_a] = pvm_X_jit((w_b + v_x) % (2 ** 32), np.uint8(4))
            elif opcode == 132:  # and_imm
                reg[r_a] = w_b & v_x
            elif opcode == 133:  # xor_imm
                reg[r_a] = w_b ^ v_x
            elif opcode == 134:  # or_imm
                reg[r_a] = w_b | v_x
            elif opcode == 135:  # mul_imm_32
                reg[r_a] = pvm_X_jit((w_b * v_x) % (2 ** 32), np.uint8(4))
            elif opcode == 149:  # add_imm_64
                reg[r_a] = (w_b + v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 150:  # mul_imm_64
                reg[r_a] = (w_b * v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 151:  # shlo_l_imm_64
                if v_x < 64:
                    reg[r_a] = (w_b << v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_a] = np.uint64(0)
            elif opcode == 152:  # shlo_r_imm_64
                if v_x < 64:
                    reg[r_a] = w_b >> v_x
                else:
                    reg[r_a] = np.uint64(0)
            elif opcode == 153:  # shar_r_imm_64
                v_x_clamped = min(v_x, 63)
                w_b_signed = pvm_Z_jit(w_b, 8)
                if w_b_signed >= 0:
                    reg[r_a] = w_b >> U64(v_x_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - v_x_clamped)
                    reg[r_a] = (w_b >> U64(v_x_clamped)) | sign_bits
            elif opcode == 154:  # neg_add_imm_64
                reg[r_a] = U64(v_x) + U64(-w_b)
            elif opcode == 155:  # shlo_l_imm_alt_64
                if w_b < 64:
                    reg[r_a] = (v_x << w_b) & U64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_a] = U64(0)
            elif opcode == 156:  # shlo_r_imm_alt_64
                if w_b < 64:
                    reg[r_a] = v_x >> w_b
                else:
                    reg[r_a] = U64(0)
            elif opcode == 157:  # shar_r_imm_alt_64
                w_b_clamped = min(w_b, 63)
                v_x_signed = pvm_Z_jit(v_x, 8)
                if v_x_signed >= 0:
                    reg[r_a] = v_x >> U64(w_b_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - w_b_clamped)
                    reg[r_a] = (v_x >> U64(w_b_clamped)) | sign_bits
            else:
                # Fall back for unimplemented - copy state first
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
        
        # Type 10: InstructionType.reg_reg_offset
        elif inst_type == 10:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            l_x = min(4, max(0, inst_arg_len[inst_index] - 1))
            v_x = pvm_Z_jit(read_uint_jit(code, pc + 2, l_x), l_x)
            
            if opcode == 170:  # branch_eq
                if reg[r_a] == reg[r_b]:
                    skip_len = v_x
            elif opcode == 171:  # branch_ne
                if reg[r_a] != reg[r_b]:
                    skip_len = v_x
            elif opcode == 172:  # branch_less_unsigned
                if reg[r_a] < reg[r_b]:
                    skip_len = v_x
            elif opcode == 173:  # branch_less_signed
                a_signed = pvm_Z_jit(reg[r_a], 8)
                b_signed = pvm_Z_jit(reg[r_b], 8)
                if a_signed < b_signed:
                    skip_len = v_x
            elif opcode == 174:  # branch_greater_or_equal_unsigned
                if reg[r_a] >= reg[r_b]:
                    skip_len = v_x
            elif opcode == 175:  # branch_greater_or_equal_signed
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
                return ERROR_INVALID_OPCODE
        
        # Type 12: InstructionType.reg_reg_reg
        elif inst_type == 12:
            r_a = min(12, code[pc + 1] % 16)
            r_b = min(12, code[pc + 1] // 16)
            r_d = min(12, code[pc + 2])

            w_a = reg[r_a]
            w_b = reg[r_b]

            if opcode == 190:  # add_32
                reg[r_d] = pvm_X_jit((w_a + w_b) % (2 ** 32), np.uint8(4))
            elif opcode == 191:  # sub_32
                reg[r_d] = pvm_X_jit((w_a + 2 ** 32 - (w_b % 2 ** 32)) % 2 ** 32, np.uint8(4))
            elif opcode == 192:  # mul_32
                reg[r_d] = pvm_X_jit((w_a * w_b) % (2 ** 32), np.uint8(4))
            elif opcode == 200:  # add_64
                reg[r_d] = (w_a + w_b) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 201:  # sub_64
                # Perform modular subtraction without overflow
                if w_a >= w_b:
                    reg[r_d] = w_a - w_b
                else:
                    reg[r_d] = np.uint64(0xFFFFFFFFFFFFFFFF) - (w_b - w_a) + np.uint64(1)
            elif opcode == 202:  # mul_64
                reg[r_d] = (w_a * w_b) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 210:  # _and
                reg[r_d] = w_a & w_b
            elif opcode == 211:  # xor
                reg[r_d] = w_a ^ w_b
            elif opcode == 212:  # _or
                reg[r_d] = w_a | w_b
            elif opcode == 203:  # div_u_32
                if (w_b % (2**32)) == 0:
                    reg[r_d] = U64(0xFFFFFFFF)  # Division by zero
                else:
                    reg[r_d] = pvm_X_jit(U64(w_a % (2**32)) // U64(w_b % (2**32)), U8(4))
            elif opcode == 204:  # div_u_64
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)  # Division by zero
                else:
                    reg[r_d] = w_a // w_b
            elif opcode == 205:  # div_s_32
                # Signed 32-bit division
                a_signed = pvm_Z_jit(w_a % (2**32), 4)
                b_signed = pvm_Z_jit(w_b % (2**32), 4)
                if b_signed == 0:
                    reg[r_d] = pvm_X_jit(U64(0xFFFFFFFF), U8(4))
                else:
                    result = riscv_div_jit(a_signed, b_signed)
                    reg[r_d] = pvm_X_jit(pvm_Z_inv_jit(result, U8(4)), U8(4))
            elif opcode == 206:  # div_s_64
                if w_b == 0:
                    reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                else:
                    reg[r_d] = pvm_Z_inv_jit(riscv_div_jit(pvm_Z_jit(w_a, 8), pvm_Z_jit(w_b, 8)), U8(8))
            elif opcode == 207:  # rem_u_32
                if (w_b % (2**32)) == 0:
                    reg[r_d] = pvm_X_jit(w_a % (2**32), U8(4))
                else:
                    reg[r_d] = pvm_X_jit((w_a % (2**32)) % (w_b % (2**32)), U8(4))
            elif opcode == 208:  # shlo_r_64
                if w_b < 64:
                    reg[r_d] = w_a >> (w_b % 64)
                else:
                    reg[r_d] = U64(0)
            elif opcode == 209:  # shar_r_64  
                w_b_clamped = min(w_b % 64, 63)
                w_a_signed = pvm_Z_jit(w_a, 8)
                if w_a_signed >= 0:
                    reg[r_d] = w_a >> U64(w_b_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = U64(0xFFFFFFFFFFFFFFFF) << U64(64 - w_b_clamped)
                    reg[r_d] = (w_a >> U64(w_b_clamped)) | sign_bits
            elif opcode == 210:  # _and
                reg[r_d] = w_a & w_b
            elif opcode == 211:  # xor
                reg[r_d] = w_a ^ w_b
            elif opcode == 212:  # _or
                reg[r_d] = w_a | w_b
            elif opcode == 216:  # set_lt_u
                reg[r_d] = U64(1) if w_a < w_b else U64(0)
            elif opcode == 217:  # set_lt_s
                reg[r_d] = U64(1) if pvm_Z_jit(w_a, 8) < pvm_Z_jit(w_b, 8) else U64(0)
            elif opcode == 220:  # rot_l_64
                reg[r_d] = roli64_jit(w_a, w_b % 64)
            elif opcode == 222:  # rot_r_64
                reg[r_d] = rori64_jit(w_a, w_b % 64)
            elif opcode == 223:  # nand
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
                return ERROR_INVALID_OPCODE
        elif inst_type == 255: #TODO!!!!!!!!!!!!HUH?>????????
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
            return ERROR_INVALID_OPCODE

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
    JIT-optimized PVM interpreter that uses Numba for the core execution loop.
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

    def invoke(self, pc: int, gas: int):
        """
        Enhanced invoke that uses JIT compilation for the hot path.
        Falls back to Python for complex operations.
        """
        self.pc = pc
        self.gas = gas

        # Try to execute with JIT-compiled function
        consecutive_fallbacks = 0
        while self.status == ExitReason.resume.value and self.gas > 0:
            # if self.inst_nr >= 7 and self.inst_nr <= 10:
            #     print(f"DEBUG[{self.inst_nr}]: Loop iteration starting with PC={self.pc}, gas={self.gas}")
            # Prepare output arrays
            registers_out = np.zeros(13, dtype=np.uint64)
            status_out = np.array([0], dtype=np.int32)
            exit_value_out = np.array([0], dtype=np.int64)
            pc_out = np.array([0], dtype=np.uint32)
            gas_out = np.array([0], dtype=np.int64)
            inst_nr_out = np.array([0], dtype=np.uint32)

            # Call JIT-compiled function
            jump_table_array = np.array(self.jump_table, dtype=np.int32)
            error_code = invoke_native(
                self.pc, self.gas,
                self.code, self.code_size,
                self.inst_pos_keys, self.inst_pos_vals, self.inst_arg_len_array,
                self.opcode_scheme_array, jump_table_array,
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
            
            
            # Debug check for invalid PC
            # if self.pc == 31:
            #     print(f"DEBUG: JIT returned PC=31! old_pc={old_pc}, error_code={error_code}")
            #     print(f"  inst_nr: {self.inst_nr} -> {self.inst_nr + inst_nr_out[0]}")
                
            self.gas = gas_out[0]
            self.inst_nr += inst_nr_out[0]
            
            # Validate PC after JIT execution (disabled for now)
            # if self.pc not in self.inst_pos and self.pc != 0 and self.gas > 0:
            #     # PC is invalid - this might be a JIT bug
            #     print(f"WARNING: JIT returned invalid PC={self.pc} (from {old_pc}), error_code={error_code}")
            # if self.inst_nr >= 7 and self.inst_nr <= 10:
            #     print(f"DEBUG[{self.inst_nr}]: After JIT, PC={self.pc}, gas={self.gas}, error={error_code}")

            # Handle errors
            if error_code == ERROR_PANIC_TRAP:
                self.status = ExitReason.panic.value
                break  # Exit the main loop
            elif error_code == ERROR_PANIC_INVALID_PC:
                self.status = ExitReason.panic.value
                break  # Exit the main loop
            elif error_code == ERROR_PANIC_INVALID_DJUMP:
                self.status = ExitReason.panic.value
                break  # Exit the main loop
            elif error_code == ERROR_INVALID_OPCODE:
                # Fall back to Python implementation for this instruction
                consecutive_fallbacks += 1
                if consecutive_fallbacks > 100:
                    raise PanicError(f"Too many consecutive fallbacks at PC={self.pc}")
                    
                if self.gas > 0 and self.status == ExitReason.resume.value:
                    # Execute one instruction with parent implementation
                    saved_gas = self.gas
                    saved_pc = self.pc
                    saved_inst_nr = self.inst_nr
                    
                    # Debug output
                    # print(f"DEBUG: Falling back at PC={self.pc}, gas={saved_gas}")

                    try:
                        # DEBUG: Check what PC we're passing to Python  
                        if self.pc not in self.inst_pos and self.pc != 0:
                            print(f"WARNING: About to invoke Python with invalid PC={self.pc}!")
                            print(f"  This will cause KeyError!")
                            # Find what would be the correct next PC
                            valid_pcs = sorted(self.inst_pos.keys())
                            prev_pc = None
                            for vpc in valid_pcs:
                                if vpc < self.pc:
                                    prev_pc = vpc
                                elif vpc > self.pc:
                                    print(f"  Previous valid PC was {prev_pc}")
                                    print(f"  Next valid PC is {vpc}")
                                    break
                        
                        # Execute exactly one instruction using Python's new single-step mode
                        old_pc = self.pc
                        old_inst_nr = self.inst_nr
                        
                        # Debug before invoking Python
                        debug_fallback = False  # Set to True to enable debug output
                        if debug_fallback:
                            print(f"DEBUG: Fallback at PC={self.pc}, inst_nr={self.inst_nr}")
                            
                        # Use enough gas to execute one instruction
                        super().invoke(self.pc, 2)
                        
                        # Debug after invoking Python
                        if debug_fallback:
                            print(f"DEBUG: After fallback PC={old_pc} -> {self.pc}")
                        
                        # Check that we executed exactly one instruction
                        insts_executed = self.inst_nr - old_inst_nr
                        
                        if insts_executed == 0:
                            # No instruction executed - this shouldn't happen with gas=2
                            print(f"WARNING: No instruction executed at PC={old_pc}")
                            self.gas = saved_gas  # No gas used
                        elif insts_executed == 1:
                            # Perfect, executed exactly one
                            self.gas = saved_gas - 1
                        else:
                            # Should not happen with single_step=True
                            print(f"WARNING: Single-step mode executed {insts_executed} instructions from PC={old_pc}")
                            self.gas = saved_gas - insts_executed
                            
                        # print(f"DEBUG: After Python fallback, PC={self.pc}")
                    except PanicError as e:
                        # Handle panic from Python execution
                        self.status = ExitReason.panic.value
                        # Don't restore state - keep the PC where the panic occurred
                        break  # Exit the main loop
                    except Exception as e:
                        # Restore state on other errors
                        self.pc = saved_pc
                        self.inst_nr = saved_inst_nr 
                        self.gas = saved_gas
                        raise
            elif error_code != ERROR_NONE:
                # Other errors
                self.status = ExitReason.panic.value
                raise PanicError(f"JIT execution error: {error_code}")
            else:
                # JIT executed successfully, reset fallback counter
                consecutive_fallbacks = 0

            # If JIT completed successfully or status changed, we're done
            if self.status != ExitReason.resume.value:
                break