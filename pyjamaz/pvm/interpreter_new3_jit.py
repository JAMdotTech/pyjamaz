# """
# JIT-optimized PVM interpreter using Numba for performance-critical utility functions.
#
# This module provides a hybrid approach where utility functions are JIT-compiled
# while the main interpreter loop remains in Python to handle complex control flow.
# """
#
# import numpy as np
# from numba import njit
# from .interpreter_new3 import PVMInterpreter as PVMInterpreterBase
# from .utils_new3 import (
#     rori64, roli64, rori32, roli32,
#     pvm_smod, riscv_div, pvm_rtz_div
# )
#
# __all__ = ['PVMInterpreter']
#
#
# # JIT-compiled utility functions
# @njit
# def pvm_X_jit(a, n):
#     """JIT-compiled transform signed to unsigned."""
#     n = int(n)
#     a = int(a)
#
#     if n == 1:
#         return (a + 128) % 256
#     elif n == 2:
#         return (a + 32768) % 65536
#     elif n == 4:
#         return (a + 2147483648) % 4294967296
#     elif n == 8:
#         if a < 0:
#             return np.uint64(18446744073709551616 + a)
#         return np.uint64(a)
#     else:
#         return np.uint64(a % (1 << (n * 8)))
#
#
# @njit
# def pvm_Z_jit(a, n):
#     """JIT-compiled transform unsigned to signed."""
#     n = int(n)
#     a = int(a)
#
#     if n == 1:
#         boundary = 1 << 7
#         if a < boundary:
#             return a
#         return a - (1 << 8)
#     elif n == 2:
#         boundary = 1 << 15
#         if a < boundary:
#             return a
#         return a - (1 << 16)
#     elif n == 4:
#         boundary = 1 << 31
#         if a < boundary:
#             return a
#         return a - (1 << 32)
#     elif n == 8:
#         boundary = 1 << 63
#         if a < boundary:
#             return a
#         return a - (1 << 64)
#     else:
#         boundary = 1 << (n * 8 - 1)
#         if a < boundary:
#             return a
#         return a - (1 << (n * 8))
#
#
# @njit
# def count_leading_zeroes_jit(x):
#     """JIT-compiled count leading zeroes."""
#     if x == 0:
#         return np.uint64(64)
#
#     count = np.uint64(0)
#     mask = np.uint64(1) << np.uint64(63)
#
#     while (x & mask) == 0:
#         count += 1
#         mask >>= 1
#
#     return count
#
#
# @njit
# def count_trailing_zeroes_jit(x):
#     """JIT-compiled count trailing zeroes."""
#     if x == 0:
#         return np.uint64(64)
#
#     count = np.uint64(0)
#     temp = x
#
#     while (temp & 1) == 0:
#         count += 1
#         temp >>= 1
#     return count
#
#
# @njit
# def reverse_bytes_jit(x):
#     """JIT-compiled reverse bytes."""
#     result = np.uint64(0)
#     for i in range(8):
#         byte = np.uint64((x >> np.uint64(i * 8)) & np.uint64(0xFF))
#         result |= np.uint64(byte << np.uint64((7 - i) * 8))
#     return result
#
#
# class PVMInterpreter(PVMInterpreterBase):
#     """
#     JIT-optimized PVM interpreter that uses Numba-compiled utility functions.
#
#     This class inherits from the base interpreter and overrides utility method
#     calls to use JIT-compiled versions for better performance.
#     """
#
#     def __init__(self, program, logger_cls=None):
#         """Initialize the interpreter with JIT-compiled utilities."""
#         super().__init__(program, logger_cls)
#
#         # Override utility functions with JIT versions in the instance
#         self._setup_jit_utilities()
#
#     def _setup_jit_utilities(self):
#         """Setup JIT-compiled utility functions for use in the interpreter."""
#         # These are imported from utils_new3.py which has JIT versions
#         # The parent class will use these automatically
#         pass
#
#     # The invoke method is inherited from parent and uses the optimized utilities
#     # from utils_new3.py which are already JIT-compiled

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
        byte = (x >> (i * 8)) & 0xFF
        result |= byte << ((7 - i) * 8)
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
        gas -= 1
        pc = np.uint32(pc + skip_len)
        inst_nr += 1

        if pc >= code_size:
            status = EXIT_PANIC
            break

        # Find instruction index
        inst_index = -1
        for i in range(len(inst_pos_keys)):
            if inst_pos_keys[i] == pc:
                inst_index = inst_pos_vals[i]
                break

        if inst_index < 0:
            status = EXIT_PANIC
            status_out[0] = status
            pc_out[0] = pc
            gas_out[0] = gas
            return ERROR_PANIC_INVALID_PC

        # Fetch opcode and decode
        opcode = code[pc]
        inst_type = opcode_scheme[opcode]
        skip_len = inst_arg_len[inst_index] + 1

        # Process instructions by type
        # Type 0: InstructionType.none
        if inst_type == 0:
            if opcode == 0:  # trap
                status = EXIT_PANIC
                status_out[0] = status
                pc_out[0] = pc
                gas_out[0] = gas
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
            # Note: Many more opcodes would need to be implemented here
            # For now, return error for unimplemented
            else:
                # Fall back to Python for complex operations
                break

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
                # Fall back for unimplemented
                break

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
                # Fall back for unimplemented
                break
        else:
            # Unsupported instruction type - fall back to Python
            break

    # Copy output state
    for i in range(len(reg)):
        registers_out[i] = reg[i]
    status_out[0] = status
    exit_value_out[0] = exit_value
    pc_out[0] = pc
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
        self.inst_pos_keys = np.array(list(self.inst_pos.keys()), dtype=np.int32)
        self.inst_pos_vals = np.array([v - 1 for v in self.inst_pos.values()], dtype=np.int32)
        self.inst_arg_len_array = np.array(self.inst_arg_len, dtype=np.int32)

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
        while self.status == ExitReason.resume.value and self.gas > 0:
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
            self.pc = pc_out[0]
            self.gas = gas_out[0]
            self.inst_nr += inst_nr_out[0]

            # Handle errors
            if error_code == ERROR_PANIC_TRAP:
                raise PanicError("trap")
            elif error_code == ERROR_PANIC_INVALID_PC:
                raise PanicError(f"Invalid PC: {self.pc}")
            elif error_code == ERROR_INVALID_OPCODE:
                # Fall back to Python implementation for this instruction
                if self.gas > 0 and self.status == ExitReason.resume.value:
                    # Execute one instruction with parent implementation
                    saved_gas = self.gas
                    self.gas = 1  # Execute just one instruction

                    try:
                        super().invoke(self.pc, 1)
                    finally:
                        # Restore gas counter
                        if self.gas == 0:
                            self.gas = saved_gas - 1
                        else:
                            self.gas = saved_gas - (1 - self.gas)
            elif error_code != ERROR_NONE:
                # Other errors
                self.status = ExitReason.panic.value
                raise PanicError(f"JIT execution error: {error_code}")

            # If JIT completed successfully or status changed, we're done
            if self.status != ExitReason.resume.value:
                break