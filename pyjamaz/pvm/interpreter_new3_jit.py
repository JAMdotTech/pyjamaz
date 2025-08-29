
"""
JIT-optimized PVM interpreter with Numba-compiled invoke_native function.
"""

import numpy as np
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


# Pure numerical functions - can be JIT compiled
@njit
def rori64(x, shift_amount):
    """JIT-compiled rotate right for 64-bit integers."""
    return np.uint64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit
def roli64(x, shift_amount):
    """JIT-compiled rotate left for 64-bit integers."""
    return np.uint64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


@njit
def rori32(x, shift_amount):
    """JIT-compiled rotate right for 32-bit integers."""
    return np.uint32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


@njit
def roli32(x, shift_amount):
    """JIT-compiled rotate left for 32-bit integers."""
    return np.uint32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


@njit
def pvm_smod(a: np.int64, b: np.int64) -> np.int64:
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
def riscv_div(x: np.int64, y: np.int64) -> np.int64:
    """JIT-compiled integer division."""
    return x // y


@njit
def pvm_rtz_div(a: np.int64, b: np.int64) -> np.int64:
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
def count_trailing_zeroes(value: np.uint64, max_bits: np.int32) -> np.int32:
    """JIT-compiled count trailing zeroes."""
    if value == 0:
        return max_bits
    # Find the position of the least significant bit
    count = np.int32(0)
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


@njit
def count_leading_zeroes(value: np.uint64, max_bits: np.int32) -> np.int32:
    """JIT-compiled count leading zeroes."""
    # Simple bit-by-bit scanning approach that Numba can compile
    if max_bits == 64:
        v = value
    else:
        v = value & ((np.uint64(1) << max_bits) - np.uint64(1))

    if v == 0:
        return max_bits

    # Count leading zeros by shifting
    count = np.int32(0)
    test_bit = np.uint64(1) << np.uint64(max_bits - 1)

    for i in range(max_bits):
        if v & test_bit:
            break
        count = count + np.int32(1)
        test_bit = test_bit >> np.uint64(1)

    return count


@njit
def pvm_X_jit(x, n):
    """JIT-compiled sign extension."""
    x = int(x)
    n = int(n)

    if n == 1:
        masked = x & 0xFF
        if masked & 0x80:
            return np.uint64(masked | 0xFFFFFFFFFFFFFF00)
        return np.uint64(masked)
    elif n == 2:
        masked = x & 0xFFFF
        if masked & 0x8000:
            return np.uint64(masked | 0xFFFFFFFFFFFF0000)
        return np.uint64(masked)
    elif n == 3:
        masked = x & 0xFFFFFF
        if masked & 0x800000:
            return np.uint64(masked | 0xFFFFFFFFFF000000)
        return np.uint64(masked)
    elif n == 4:
        masked = x & 0xFFFFFFFF
        if masked & 0x80000000:
            return np.uint64(masked | 0xFFFFFFFF00000000)
        return np.uint64(masked)
    elif n == 5:
        masked = x & 0xFFFFFFFFFF
        if masked & 0x8000000000:
            return np.uint64(masked | 0xFFFFFF0000000000)
        return np.uint64(masked)
    elif n == 6:
        masked = x & 0xFFFFFFFFFFFF
        if masked & 0x800000000000:
            return np.uint64(masked | 0xFFFF000000000000)
        return np.uint64(masked)
    elif n == 7:
        masked = x & 0xFFFFFFFFFFFFFF
        if masked & 0x80000000000000:
            return np.uint64(masked | 0xFF00000000000000)
        return np.uint64(masked)
    elif n == 8:
        return np.uint64(x & 0xFFFFFFFFFFFFFFFF)
    else:
        return np.uint64(x)


@njit
def pvm_Z_jit(a, n):
    """JIT-compiled transform unsigned to signed."""
    n = int(n)
    a = int(a)

    if n == 1:
        boundary = 1 << 7
        if a < boundary:
            return a
        return a - (1 << 8)
    elif n == 2:
        boundary = 1 << 15
        if a < boundary:
            return a
        return a - (1 << 16)
    elif n == 4:
        boundary = 1 << 31
        if a < boundary:
            return a
        return a - (1 << 32)
    elif n == 8:
        # For n=8, use numpy casting
        return np.int64(np.uint64(a))
    else:
        shift = (n << 3) - 1
        boundary = 1 << shift
        if a < boundary:
            return a
        return a - (1 << (shift + 1))


@njit
def count_leading_zeroes_jit(value, max_bits=64):
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


@njit
def count_trailing_zeroes_jit(value, max_bits=64):
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
def reverse_bytes_jit(x):
    """JIT-compiled reverse bytes."""
    result = np.uint64(0)
    for i in range(8):
        byte = np.uint64((x >> np.uint64(i * 8)) & np.uint64(0xFF))
        result |= np.uint64(byte << np.uint64((7 - i) * 8))
    return result


@njit
def read_uint_jit(code, addr, length):
    """JIT-compiled version of read_uint for bytecode reading."""
    if length == 0:
        return np.uint64(0)
    elif length == 1:
        return np.uint64(code[addr])
    elif length == 2:
        return np.uint64(code[addr] | (code[addr + 1] << 8))
    elif length == 3:
        return np.uint64(code[addr] | (code[addr + 1] << 8) | (code[addr + 2] << 16))
    elif length == 4:
        return np.uint64(code[addr] | (code[addr + 1] << 8) |
                         (code[addr + 2] << 16) | (code[addr + 3] << 24))
    elif length == 8:
        result = np.uint64(0)
        for i in range(8):
            result |= np.uint64(code[addr + i]) << np.uint64(i * 8)
        return result
    else:
        return np.uint64(0)


@njit
def invoke_native(
        pc_start, gas_start,
        code, code_size,
        inst_pos_keys, inst_pos_vals, inst_arg_len,
        opcode_scheme,
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
    pc = np.uint32(pc_start)
    gas = np.int64(gas_start)
    status = EXIT_RESUME
    exit_value = np.int64(0)
    skip_len = 0
    inst_nr = np.uint32(0)

    # Copy registers
    reg = registers_in.copy()

    # Main execution loop
    while status == EXIT_RESUME and gas > 0:
        # Calculate next PC but don't update yet
        next_pc = np.uint32(pc + skip_len)
        
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

            if opcode == 51:  # load_imm
                reg[r_a] = v_x
            elif opcode == 52:  # load_u8
                # For now, fall back for memory operations
                # Memory operations are complex and safer in Python
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
            elif opcode == 56:  # load_u32  
                # For now, fall back for memory operations
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
            elif opcode == 59:  # store_u8
                # For now, fall back for memory operations
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
            elif opcode == 61:  # store_u32
                # For now, fall back for memory operations
                for i in range(len(reg)):
                    registers_out[i] = reg[i]
                status_out[0] = status
                exit_value_out[0] = exit_value
                pc_out[0] = pc  # PC already points to current instruction
                gas_out[0] = gas + 1  # Return gas before decrement  
                inst_nr_out[0] = inst_nr - 1  # Return inst_nr before increment
                return ERROR_INVALID_OPCODE
            elif opcode == 90:  # add_imm
                reg[r_a] = (reg[r_a] + v_x) & np.uint64(0xFFFFFFFFFFFFFFFF)
            elif opcode == 91:  # add_imm_32
                reg[r_a] = pvm_X_jit((reg[r_a] + v_x) % (2**32), np.uint8(4))
            elif opcode == 92:  # sub_imm  
                reg[r_a] = (reg[r_a] + np.uint64(0xFFFFFFFFFFFFFFFF) - v_x + np.uint64(1)) & np.uint64(0xFFFFFFFFFFFFFFFF)
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
            elif opcode == 102:  # count_set_bits_64
                # Manual bit counting (np.bitwise_count not available in numba)
                val = reg[r_a]
                count = np.uint64(0)
                for _ in range(64):
                    count += val & 1
                    val >>= 1
                reg[r_d] = count
            elif opcode == 104:  # leading_zero_bits_64
                reg[r_d] = count_leading_zeroes_jit(reg[r_a])
            elif opcode == 106:  # trailing_zero_bits_64
                reg[r_d] = count_trailing_zeroes_jit(reg[r_a])
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
                    reg[r_a] = w_b >> np.uint64(v_x_clamped)
                else:
                    # Arithmetic right shift for negative numbers
                    sign_bits = np.uint64(0xFFFFFFFFFFFFFFFF) << np.uint64(64 - v_x_clamped)
                    reg[r_a] = (w_b >> np.uint64(v_x_clamped)) | sign_bits
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
            elif opcode == 220:  # rot_l_64
                reg[r_d] = roli64(w_a, w_b % 64)
            elif opcode == 222:  # rot_r_64
                reg[r_d] = rori64(w_a, w_b % 64)
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
            error_code = invoke_native(
                self.pc, self.gas,
                self.code, self.code_size,
                self.inst_pos_keys, self.inst_pos_vals, self.inst_arg_len_array,
                self.opcode_scheme_array,
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
                            
                        # Use single-step mode with enough gas to execute one instruction
                        super().invoke(self.pc, 2, single_step=True)
                        
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