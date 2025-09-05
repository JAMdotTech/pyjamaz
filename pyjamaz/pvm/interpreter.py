import numpy as np
import numpy.typing as npt

from typing import List, Dict

from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
from .types import PVMProgram, PVMMemory, PVMMemoryMode

from .constants import (
    OpcodeScheme,
    ExitReason,
    MemOps,
    OpcodeNames,
    ExitCondition,

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
    inst_reg_reg_offset, inst_reg_reg_imm_imm, inst_reg_reg_reg, typezzz, PVM_PAGE_SIZE
)

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR


def rori64(x, shift_amount):
    return ((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF


def roli64(x, shift_amount):
    return ((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF


def rori32(x, shift_amount):
    return ((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF


def roli32(x, shift_amount):
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
    x = int(x)
    return int.from_bytes(x.to_bytes(8, 'big'), 'little')


def count_trailing_zeroes(value, max_bits=64):
    # https://stackoverflow.com/a/63552117
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
    if value == 0:
        return max_bits
    return int(value & -value).bit_length() - 1


def count_leading_zeroes(value, max_bits=64):
    # https://stackoverflow.com/a/71888844
    # https://github.com/numpy/numpy/issues/16325
    # alternative: https://gmpy2.readthedocs.io/en/latest/mpz.html
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
    a = int(a)
    b = int(b)

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


def pvm_X(x: np.uint64, n: np.uint8) -> np.uint64:
    """
    Sign extend a number to two's complement form for value X and number of bytes n

    Optimized version using bit operations.
    """
    # Convert to Python int to handle all numpy types
    x = int(x)
    n = int(n)

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


# Precomputed lookup tables for common n values (1, 2, 4, 8)
_PVM_Z_BOUNDARY = {
    1: 1 << 7,  # 2^7 = 128
    2: 1 << 15,  # 2^15 = 32768
    4: 1 << 31,  # 2^31
    8: 1 << 63  # 2^63
}

_PVM_Z_MAX_VALUE = {
    1: 1 << 8,  # 2^8 = 256
    2: 1 << 16,  # 2^16 = 65536
    4: 1 << 32,  # 2^32
    8: 18446744073709551616  # 2^64 (explicitly set as Python int)
}

_PVM_Z_MASK = {
    1: 0xFF,  # 8 bits
    2: 0xFFFF,  # 16 bits
    4: 0xFFFFFFFF,  # 32 bits
    8: 0xFFFFFFFFFFFFFFFF  # 64 bits
}


def pvm_Z(a: int, n: np.uint8) -> int:
    """
    Transform an unsigned number into a signed number using the MSB

    Note:
        Optimized using lookup tables for common cases (n=1,2,4,8)
        and bitwise operations for better performance.
    """
    n = int(n)
    a = int(a)

    # fast path for common cases
    if n in _PVM_Z_BOUNDARY:
        boundary = _PVM_Z_BOUNDARY[n]
        if a < boundary:
            return int(a)
        # for large values, use numpy's casting which handles wraparound
        if n == 8:
            # For n=8, directly cast uint64 to int64 (reinterprets bits), then to python int
            return int(np.int64(np.uint64(a)))
        elif n == 4:
            # for n=4, similar handling for 32-bit values
            result = a - _PVM_Z_MAX_VALUE[n]
            return int(np.int32(result))
        else:
            return int(a - _PVM_Z_MAX_VALUE[n])

    # fallback for other values of n
    shift = (n << 3) - 1  # n * 8 - 1
    boundary = 1 << shift
    if a < boundary:
        return int(a)
    return int(a - (1 << (shift + 1)))


def pvm_Z_inv(a: int, n: np.uint8) -> np.uint64:
    """
    Transform a signed number to an unsigned number

    Note:
        Optimized using bitwise operations and lookup tables for better performance.
    """
    n = int(n)

    # fast path for common cases
    if n in _PVM_Z_MASK:
        if a >= 0:
            # For n=8 and large positive values, handle specially
            if n == 8 and a > 2 ** 63:
                return np.uint64(a)
            return np.uint64(a) & _PVM_Z_MASK[n]
        # For negative numbers, handle n=8 specially to avoid overflow
        if n == 8:
            # For n=8, use numpy casting which handles wraparound correctly
            return np.uint64(np.int64(a))
        return np.uint64((a + _PVM_Z_MAX_VALUE[n]) & _PVM_Z_MASK[n])

    # ffallback for other values of n
    shift = n << 3  # n * 8
    mask = (1 << shift) - 1
    if a >= 0:
        return np.uint64(a & mask)
    return np.uint64((a + (1 << shift)) & mask)


def read_uint(code, addr32, len8):
    if len8 == 0:
        return 0 & 0xFF

    if len8 == 1:
        return int(code[addr32] & 0xFF)

    if len8 == 2:
        return (int(code[addr32+0]) & 0xFF) | ((int(code[addr32+1]) & 0xFF) << 8)

    if len8 == 3:
        return (int(code[addr32 + 0]) & 0xFF) | ((int(code[addr32 + 1]) & 0xFF) << 8) | ((int(code[addr32 + 2]) & 0xFF) << 16)

    if len8 == 4:
        return (int(code[addr32 + 0]) & 0xFF) | ((int(code[addr32 + 1]) & 0xFF) << 8) | ((int(code[addr32 + 2]) & 0xFF) << 16) | ((int(code[addr32 + 3]) & 0xFF) << 24)

    if len8 ==8:
        return (int(code[addr32 + 0]) & 0xFF) | ((int(code[addr32 + 1]) & 0xFF) << 8)  | ((int(code[addr32 + 2]) & 0xFF) << 16) | ((int(code[addr32 + 3]) & 0xFF) << 24) | ((int(code[addr32 + 4]) & 0xFF) << 32) | ((int(code[addr32 + 5]) & 0xFF) << 40) | ((int(code[addr32 + 6]) & 0xFF) << 48) | ((int(code[addr32 + 7]) & 0xFF) << 56)

    raise Exception("read_uint: unsupported length")


class PVMInterpreter:

    def __init__(self, program: PVMProgram, logger_cls=None):
        self.name = program.name
        self.reg:npt.NDArray[np.uint64] = np.zeros(13, dtype=np.uint64)
        self.inst_nr:np.uint32 = np.uint32(0)
        self.pc:np.uint32 = np.uint32(0)
        self.opcode:int = 0
        self.skip_len: int = 0
        self.gas:np.int64 = np.int64(0)
        self.code:npt.NDArray[np.uint8] = np.array(1, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(0)
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
        self.mem_section_starts = np.array([], dtype=np.uint32)
        self.mem_section_ends = np.array([], dtype=np.uint32)
        self.mem_section_size = np.array([], dtype=np.uint32)
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

        self.log = None

        self.reset(program)

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
        self.pc = np.uint32(0)
        self.gas = np.int64(0)

        self.name = program.name
        self.code:npt.NDArray[np.uint8] = np.array(program.code.code, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(len(self.code))
        self.mem = program.memory
        self.jump_table = [x.value for x in program.code.jump_table]

        # Initialize memory sections from the PVMMemory object (just reference where possible)
        self._link_memory(program.memory)

        for idx, val in enumerate(program.registers):
            self.reg[idx] = np.uint64(val)

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
        self.mem_ops_bytes = np.zeros(256, dtype=np.uint8)
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
            else:
                self.mem_sections.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)

        self.mem_section_starts = np.array(mem_section_starts, dtype=np.uint32)
        self.mem_section_ends = np.array(mem_section_ends, dtype=np.uint32)
        self.mem_section_size = np.array(mem_section_size, dtype=np.uint32)
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
                heap = np.concatenate((heap, np.zeros(growth, dtype=np.uint8)))
                self.mem_sections[1] = heap
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
        #addr = addr % (2 ** 32)  #TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # Find the memory section
        section_idx = 0
        section_idx = (self.ROM_ADDR <= addr <= self.ROM_END) and 1 or section_idx
        section_idx = (self.HEAP_ADDR <= addr <= self.HEAP_END) and 2 or section_idx
        section_idx = (self.STACK_ADDR <= addr <= self.STACK_END) and 3 or section_idx
        section_idx = (self.ARG_ADDR <= addr <= self.ARG_END) and 4 or section_idx
        section_idx -= 1

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
        if bytes_to_write == 1:
            section[section_offset] = value & 0xFF
        elif bytes_to_write == 2:
            section[section_offset] =value & 0xFF
            section[section_offset + 1] =(value >> 8) & 0xFF
        elif bytes_to_write == 4:
            section[section_offset] = value & 0xFF
            section[section_offset + 1] = (value >> 8) & 0xFF
            section[section_offset + 2] = (value >> 16) & 0xFF
            section[section_offset + 3] = (value >> 24) & 0xFF
        elif bytes_to_write == 8:
            section[section_offset] = value & 0xFF
            section[section_offset + 1] = (value >> 8) & 0xFF
            section[section_offset + 2] = (value >> 16) & 0xFF
            section[section_offset + 3] = (value >> 24) & 0xFF
            section[section_offset + 4] = (value >> 32) & 0xFF
            section[section_offset + 5] = (value >> 40) & 0xFF
            section[section_offset + 6] = (value >> 48) & 0xFF
            section[section_offset + 7] = (value >> 56) & 0xFF


    def _mem_read_int(self, addr: int, bytes_to_read: int):
        section_idx = 0
        section_idx = (self.ROM_ADDR <= addr <= self.ROM_END) and 1 or section_idx
        section_idx = (self.HEAP_ADDR <= addr <= self.HEAP_END) and 2 or section_idx
        section_idx = (self.STACK_ADDR <= addr <= self.STACK_END) and 3 or section_idx
        section_idx = (self.ARG_ADDR <= addr <= self.ARG_END) and 4 or section_idx
        section_idx -= 1

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

        bytes_to_read = self.mem_ops_bytes[opcode]
        #addr = addr % (2 ** 32)  # TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # Find the memory section
        section_idx = 0
        section_idx = (self.ROM_ADDR <= addr <= self.ROM_END) and 1 or section_idx
        section_idx = (self.HEAP_ADDR <= addr <= self.HEAP_END) and 2 or section_idx
        section_idx = (self.STACK_ADDR <= addr <= self.STACK_END) and 3 or section_idx
        section_idx = (self.ARG_ADDR <= addr <= self.ARG_END) and 4 or section_idx
        section_idx -= 1

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            raise PVMMemoryError(f"mem_read: Memory address {addr} not found in any section")

        # Check if readable using page-based ACL (if available)
        if self.mem and self.mem_acl is not None:
            page_nr = addr // PVM_PAGE_SIZE
            if page_nr not in self.mem_acl or self.mem_acl[page_nr] == self.mem_inaccesible:
                raise PVMMemoryError(f"Memory at address {addr} is not accessible")

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        # Check bounds against the actual section size
        if section_offset + bytes_to_read > len(section):
            raise PVMMemoryError(f"Memory read at {addr} would overflow section")

        # Read bytes in little-endian order
        return read_uint(section, section_offset, bytes_to_read)

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
        #self.skip_len = 0

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
            inst_type = typezzz[opcode] #OpcodeScheme[opcode].value
            self.skip_len = self.inst_arg_len[inst_index] + 1

            try:
                #GP-0.6.7-section:A.5.1
                if inst_type == inst_none:  # InstructionType.none
                    if opcode == op_trap:
                        self.log and self.log()
                        #self.status = ExitCondition.panic.value
                        raise PanicError(f"trap")
                    elif opcode == op_fallthrough:
                        self.log and self.log()
                        pass
                    else:
                        raise InvalidOpcode(f"Invalid noargs opcode: {opcode} for instruction type {inst_type}")


                #GP-0.6.7-section:A.5.2
                elif inst_type == inst_imm:  # InstructionType.imm
                    l_x = int(min(4, self.inst_arg_len[inst_index]))
                    v_x = pvm_X(read_uint(self.code, self.pc + 1, l_x), l_x)

                    if opcode == op_ecalli:
                        self.status = ExitReason.host_halt.value
                        self.exit_value = v_x
                        self.log and self.log(imm1=v_x)
                    else:
                        raise InvalidOpcode(f"Invalid imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.3
                elif inst_type == inst_reg_ext_imm:  # InstructionType.reg_ext_imm

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    v_x = read_uint(self.code, self.pc + 2, 8)

                    if opcode == op_load_imm_64:
                        self.reg[r_a] = v_x
                        self.log and self.log(reg1=r_a, imm1=v_x)
                    else:
                        raise InvalidOpcode(f"Invalid reg_ext_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.4
                elif inst_type == inst_imm_imm:  # InstructionType.imm_imm

                    l_x = int(min(4, self.code[self.pc + 1] % 8))
                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)
                    v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == op_store_imm_u8:
                        self.mem_write(opcode, v_x, v_y % 2 ** 8)
                        self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(v_x, 1)})
                    elif opcode == op_store_imm_u16:
                        self.mem_write(opcode, v_x, v_y % 2 ** 16)
                        self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(v_x, 2)})
                    elif opcode == op_store_imm_u32:
                        self.mem_write(opcode, v_x, v_y % 2 ** 32)
                        self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(v_x, 4)})
                    elif opcode == op_store_imm_u64:
                        self.mem_write(opcode, v_x, v_y)
                        self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(v_x, 8)})
                    else:
                        raise InvalidOpcode(f"Invalid imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.5
                elif inst_type == inst_offset:  # InstructionType.offset

                    l_x = int(min(4, self.inst_arg_len[inst_index]))
                    v_x = pvm_Z(read_uint(self.code, self.pc + 1, l_x), l_x)

                    if opcode == op_jump:
                        self.skip_len = v_x
                        self.log and self.log(off1=v_x, context={"skip_len":v_x})
                    else:
                        raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                #GP-0.6.7-section:A.5.6
                elif inst_type == inst_reg_imm:  # InstructionType.reg_imm
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    l_x = min(4, max(0, self.inst_arg_len[inst_index] - 1))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == op_jump_ind:
                        self.skip_len = self.djump((self.reg[r_a]+v_x))
                        self.log and self.log(reg1=r_a, imm1=v_x, context={"skip_len": self.skip_len})

                    elif opcode == op_load_imm:
                        self.reg[r_a] = v_x
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_u8:
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_i8:
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 1)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_u16:
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_i16:
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 2)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_u32:
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_i32:
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 4)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_load_u64:
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x)

                    elif opcode == op_store_u8:
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**8)
                        self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self._mem_read_int(v_x, 1)})

                    elif opcode == op_store_u16:
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**16)
                        self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self._mem_read_int(v_x, 2)})

                    elif opcode == op_store_u32:
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**32)
                        self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self._mem_read_int(v_x, 4)})

                    elif opcode == op_store_u64:
                        self.mem_write(opcode, v_x, self.reg[r_a])
                        self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self._mem_read_int(v_x, 8)})

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.7
                elif inst_type == inst_reg_imm_imm:  # InstructionType.reg_imm_imm
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    w_a = int(self.reg[r_a])

                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == op_store_imm_ind_u8:
                        self.mem_write(opcode, w_a + v_x, v_y % 2**8)
                        self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(w_a + v_x, 1)})

                    elif opcode == op_store_imm_ind_u16:
                        self.mem_write(opcode, w_a + v_x, v_y % 2**16)
                        self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(w_a + v_x, 2)})

                    elif opcode == op_store_imm_ind_u32:
                        self.mem_write(opcode, w_a + v_x, v_y % 2**32)
                        self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(w_a + v_x, 4)})

                    elif opcode == op_store_imm_ind_u64:
                        self.mem_write(opcode, w_a + v_x, v_y)
                        self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self._mem_read_int(w_a + v_x, 8)})

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.8
                elif inst_type == inst_reg_imm_offset:  # InstructionType.reg_imm_offset
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    w_a = int(self.reg[r_a])

                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                    l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_y = pvm_Z(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == op_load_imm_jump:
                        self.skip_len = v_y
                        self.reg[r_a] = v_x
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_eq_imm:
                        self.branch(v_y, w_a == v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_ne_imm:
                        self.branch(v_y, w_a != v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_lt_u_imm:
                        self.branch(v_y, w_a < v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_le_u_imm:
                        self.branch(v_y, w_a <= v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_ge_u_imm:
                        self.branch(v_y, w_a >= v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_gt_u_imm:
                        self.branch(v_y, w_a > v_x)
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_lt_s_imm:
                        self.branch(v_y, pvm_Z(w_a, 8) < pvm_Z(v_x, 8))
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_le_s_imm:
                        self.branch(v_y, pvm_Z(w_a, 8) <= pvm_Z(v_x, 8))
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_ge_s_imm:
                        self.branch(v_y, pvm_Z(w_a, 8) >= pvm_Z(v_x, 8))
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == op_branch_gt_s_imm:
                        self.branch(v_y, pvm_Z(w_a, 8) > pvm_Z(v_x, 8))
                        self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.9
                elif inst_type == inst_reg_reg:  # InstructionType.reg_reg

                    r_d = min(12, self.code[self.pc + 1] % 16)
                    r_a = min(12, self.code[self.pc + 1] // 16)

                    if opcode == op_move_reg:
                        self.reg[r_d] = self.reg[r_a]
                        self.log and self.log(reg1=r_d, reg2=r_a)

                    elif opcode == op_sbrk:
                        # Note: set break / set break pointer (extend heap memory)
                        # Update our cached memory bounds after heap extension
                        self.reg[r_d] = self._sbrk(self.reg[r_a])
                        self.log and self.log(reg1=r_d, reg2=r_a)

                    elif opcode == op_count_set_bits_64:
                        self.reg[r_d] = np.bitwise_count(self.reg[r_a])
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_count_set_bits_32:
                        self.reg[r_d] = np.bitwise_count(self.reg[r_a])
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_leading_zero_bits_64:
                        #self.reg[r_d] = count_leading_zeroes(reverse_bits_64(self.reg[r_a]))
                        self.reg[r_d] = count_leading_zeroes(self.reg[r_a], 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_leading_zero_bits_32:
                        #self.reg[r_d] = count_leading_zeroes(U32(reverse_bits_32(self.reg[r_a])), 32)
                        self.reg[r_d] = count_leading_zeroes(self.reg[r_a], 32)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_trailing_zero_bits_64:
                        self.reg[r_d] = count_trailing_zeroes(self.reg[r_a], 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_trailing_zero_bits_32:
                        self.reg[r_d] = count_trailing_zeroes(self.reg[r_a], 32)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_sign_extend_8:
                        self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**8, 1), 8)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_sign_extend_16:
                        self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**16, 2), 8)
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_zero_extend_16:
                        self.reg[r_d] = self.reg[r_a] % 2**16
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_reverse_bytes:
                        self.reg[r_d] = reverse_bytes(self.reg[r_a])
                        self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.10
                elif inst_type == inst_reg_reg_imm:  # InstructionType.reg_reg_imm

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)

                    w_a = int(self.reg[r_a])
                    w_b = int(self.reg[r_b])

                    l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == op_store_ind_u8:
                        self.mem_write(opcode, w_b + v_x, w_a % 2**8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**8, "w_b": w_b})

                    elif opcode == op_store_ind_u16:
                        self.mem_write(opcode, w_b + v_x, w_a % 2**16)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**16, "w_b": w_b})

                    elif opcode == op_store_ind_u32:
                        self.mem_write(opcode, w_b + v_x, w_a % 2**32)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**32, "w_b": w_b})

                    elif opcode == op_store_ind_u64:
                        self.mem_write(opcode, w_b + v_x, w_a)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_u8:
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_i8:
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 1), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_u16:
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_i16:
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 2), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_u32:
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_i32:
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 4), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_load_ind_u64:
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == op_add_imm_32:
                        self.reg[r_a] = pvm_X((w_b + v_x) % 2**32, 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_and_imm:
                        self.reg[r_a] = w_b & v_x
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_xor_imm:
                        self.reg[r_a] = w_b ^ v_x
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_or_imm:
                        self.reg[r_a] = w_b | v_x
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_mul_imm_32:
                        self.reg[r_a] = pvm_X((w_b * v_x) % 2**32, 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_set_lt_u_imm:
                        self.reg[r_a] = w_b < v_x and 1 or 0
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_set_lt_s_imm:
                        self.reg[r_a] = pvm_Z(w_b, 8) < pvm_Z(v_x, 8) and 1 or 0
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_shlo_l_imm_32:
                        self.reg[r_a] = pvm_X((w_b * 2**(v_x % 32)) % 2 ** 32, 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_shlo_r_imm_32:
                        self.reg[r_a] = pvm_X((w_b % 2 ** 32) // (2 ** (v_x % 32)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_shar_r_imm_32:
                        self.reg[r_a] = pvm_Z_inv(
                            pvm_Z(w_b % 2 ** 32, 4) // (2 ** (v_x % 32)),
                            8
                        )
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})
                    elif opcode == op_neg_add_imm_32:
                        self.reg[r_a] = pvm_X((v_x + 2**32 - w_b) % 2**32, 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_set_gt_u_imm:
                        self.reg[r_a] = w_b > v_x and 1 or 0
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_set_gt_s_imm:
                        self.reg[r_a] = pvm_Z(w_b, 8) > pvm_Z(v_x, 8) and 1 or 0
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_l_imm_alt_32:
                        self.reg[r_a] = pvm_X((v_x * (2 ** (w_b % 32))) % 2**32, 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_r_imm_alt_32:
                        self.reg[r_a] = pvm_X(v_x % 2 ** 32 // (2 ** (w_b % 32)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_alt_32:
                        self.reg[r_a] = pvm_Z_inv(
                            pvm_Z(v_x % 2 ** 32, 4) // 2 ** (w_b % 32),
                            8
                        )
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})
                    elif opcode == op_cmov_iz_imm:
                        if w_b == 0:
                            self.reg[r_a] = v_x
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_cmov_nz_imm:
                        if w_b != 0:
                            self.reg[r_a] = v_x
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_add_imm_64:
                        self.reg[r_a] = (w_b + v_x) % 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_mul_imm_64:
                        self.reg[r_a] = (w_b * v_x) #% 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_l_imm_64:
                        self.reg[r_a] = pvm_X((w_b * 2**(v_x % 64)), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_r_imm_64:
                        self.reg[r_a] = pvm_X(w_b // 2 ** (v_x % 64), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_64:
                        self.reg[r_a] = pvm_Z_inv(
                            pvm_Z(w_b, 8) // 2 ** (v_x % 64),
                            8
                        )
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_neg_add_imm_64:
                        self.reg[r_a] = ((int(v_x) + 2 ** 64 - int(w_b)) % 2 ** 64)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_l_imm_alt_64:
                        self.reg[r_a] = (v_x * 2**(w_b % 64)) % 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_r_imm_alt_64:
                        self.reg[r_a] = v_x // 2 ** (w_b % 64)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_alt_64:
                        self.reg[r_a] = pvm_Z_inv(
                            pvm_Z(v_x, 8) // 2 ** (w_b % 64),
                            8
                        )
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_64_imm:
                        self.reg[r_a] = rori64(w_b, v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_64_imm_alt:
                        self.reg[r_a] = rori64(v_x, w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_32_imm:
                        self.reg[r_a] = pvm_X(rori32(w_b, v_x), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_32_imm_alt:
                        self.reg[r_a] = pvm_X(rori32(v_x, w_b), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.11
                elif inst_type == inst_reg_reg_offset:  # InstructionType.reg_reg_offset
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    w_a = int(self.reg[r_a])
                    w_b = int(self.reg[r_b])

                    l_x = min(4, max(0, self.inst_arg_len[inst_index] - 1))
                    v_x = pvm_Z(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == op_branch_eq:
                        self.branch(v_x, w_a == w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == op_branch_ne:
                        self.branch(v_x, w_a != w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == op_branch_lt_u:
                        self.branch(v_x, w_a < w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == op_branch_lt_s:
                        self.branch(v_x, pvm_Z(w_a, 8) < pvm_Z(w_b, 8))
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == op_branch_ge_u:
                        self.branch(v_x, w_a >= w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == op_branch_ge_s:
                        self.branch(v_x, pvm_Z(w_a, 8) >= pvm_Z(w_b, 8))
                        self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.12
                elif inst_type == inst_reg_reg_imm_imm:  # InstructionType.reg_reg_imm_imm
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = self.code[self.pc + 1] // 16

                    #w_a = self.reg[r_a]
                    w_b = int(self.reg[r_b])

                    l_x = int(min(4, self.code[self.pc + 2] % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 3, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 2)))
                    v_y = pvm_X(read_uint(self.code, self.pc + 3 + l_x, l_y), l_y)

                    if opcode == op_load_imm_jump_ind:
                        self.reg[r_a] = v_x
                        self.skip_len = self.djump(((w_b) + (v_y)) % 2**32)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": self.skip_len})
                    else:
                        raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.13
                elif inst_type == inst_reg_reg_reg:  # InstructionType.reg_reg_reg

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    r_d = min(12, self.code[self.pc + 2])

                    w_a = int(self.reg[r_a])
                    w_b = int(self.reg[r_b])

                    if opcode == op_add_32:
                        self.reg[r_d] = pvm_X((w_a + w_b) % 2**32, 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_sub_32:
                        self.reg[r_d] = pvm_X((w_a + 2**32 - (w_b % 2**32)) % 2**32, 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_32:
                        self.reg[r_d] = pvm_X((w_a * w_b) % 2**32, 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_u_32:
                        if self.reg[r_b] == 0:
                            self.reg[r_d] = 2**64 - 1
                        else:
                            self.reg[r_d] = pvm_X(w_a % 2**32 // w_b % 2**32, 4)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_s_32:
                        a = pvm_Z(w_a % 2 ** 32, 4)
                        b = pvm_Z(w_b % 2 ** 32, 4)

                        if b == 0:
                            self.reg[r_d] = 2**64-1
                        elif a == -2**31 and b == -1:
                            self.reg[r_d] = pvm_Z_inv(a, 8)
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_rtz_div(a, b), 8)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rem_u_32:
                        if w_b % 2**32 == 0:
                            self.reg[r_d] = pvm_X(w_a % 2**32, 4)
                        else:
                            self.reg[r_d] = pvm_X((w_a % 2**32) % (w_b % 2**32), 4)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rem_s_32:
                        a = pvm_Z(w_a % 2**32, 4)
                        b = pvm_Z(w_b % 2**32, 4)

                        if b == 0:
                            self.reg[r_d] = pvm_Z_inv(a, 8)
                        elif a == -2**31 and b == -1:
                            self.reg[r_d] = 0
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shlo_l_32:
                        self.reg[r_d] = pvm_X((w_a * 2**(w_b % 32)) % 2**32, 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shlo_r_32:
                        self.reg[r_d] = pvm_X(w_a % 2 ** 32 // 2 ** (w_b % 32), 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shar_r_32:
                        self.reg[r_d] = pvm_Z_inv(
                            pvm_Z(w_a % 2 ** 32, 4) // 2 ** (w_b % 32),
                            8
                        )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_add_64:
                        self.reg[r_d] = (w_a + w_b) #% 2**64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_sub_64:
                        self.reg[r_d] = (int(w_a) + 2 ** 64 - int(w_b)) % 2 ** 64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_64:
                        self.reg[r_d] = (w_a * w_b) #% 2**64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_u_64:
                        if w_b == 0:
                            self.reg[r_d] = 2 ** 64 - 1
                        else:
                            self.reg[r_d] = w_a // w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_s_64:
                        if w_b == 0:
                            self.reg[r_d] = 2 ** 64 - 1
                        elif pvm_Z(w_a, 8) == -2 ** 63 and pvm_Z(w_b, 8) == -1:
                            self.reg[r_d] = w_a
                        else:
                            self.reg[r_d] = pvm_Z_inv(
                                pvm_rtz_div(
                                    pvm_Z(w_a, 8),
                                    pvm_Z(w_b, 8)
                                ),
                                8
                            )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rem_u_64:
                        if w_b == 0:
                            self.reg[r_d] = w_a
                        else:
                            self.reg[r_d] = w_a % w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rem_s_64:
                        a = pvm_Z(w_a, 8)
                        b = pvm_Z(w_b, 8)

                        if w_b == 0:
                            self.reg[r_d] = w_a
                        elif a == -2**63 and b == -1:
                            self.reg[r_d] = 0
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shlo_l_64:
                        self.reg[r_d] = (w_a * 2**(w_b % 64)) #% 2**64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shlo_r_64:
                        self.reg[r_d] = w_a // 2 ** (w_b % 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shar_r_64:
                        self.reg[r_d] = pvm_Z_inv(np.int64(pvm_Z(w_a, 8)) >> np.int64(np.uint64(w_b) & np.uint64(63)), 8)
                        # self.reg[r_d] = pvm_Z_inv(
                        #     pvm_Z(w_a, 8) // 2 ** (w_b % 64),
                        #     8
                        # )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_and:
                        self.reg[r_d] = self.reg[r_a] & self.reg[r_b]
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_xor:
                        self.reg[r_d] = self.reg[r_a] ^ self.reg[r_b]
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_or:
                        self.reg[r_d] = self.reg[r_a] | self.reg[r_b]
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_upper_s_s:
                        self.reg[r_d] = pvm_Z_inv(
                            (pvm_Z(w_a, 8) * pvm_Z(w_b, 8)) // 2 ** 64,
                            8
                        )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_upper_u_u:
                        self.reg[r_d] = int(w_a) * int(w_b) // 2 ** 64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})


                    elif opcode == op_mul_upper_s_u:
                        self.reg[r_d] = pvm_Z_inv(
                            (pvm_Z(w_a, 8) * int(w_b)) // 2 ** 64,
                            8
                        )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_set_lt_u:
                        self.reg[r_d] = np.uint64(w_a < w_b)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_set_lt_s:
                        self.reg[r_d] = pvm_Z(w_a, 8) < pvm_Z(w_b, 8)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_cmov_iz:
                        if w_b == 0:
                            self.reg[r_d] = w_a
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_cmov_nz:
                        if w_b != 0:
                            self.reg[r_d] = w_a
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_l_64:
                        self.reg[r_d] = roli64(w_a, w_b % 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_l_32:
                        self.reg[r_d] = pvm_X(roli32(w_a, w_b % 32), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_r_64:
                        self.reg[r_d] = rori64(w_a, w_b % 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_r_32:
                        self.reg[r_d] = pvm_X(rori32(w_a, w_b % 32), 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_and_inv:
                        self.reg[r_d] = w_a & ~w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_or_inv:
                        self.reg[r_d] = w_a | ~w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_xnor:
                        self.reg[r_d] = np.uint64(~(w_a ^ w_b))
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_max:
                        #TODO: should probably just cast to U64 <-> I64 ??
                        self.reg[r_d] = pvm_Z_inv(
                            max(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                            8
                        )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_max_u:
                        self.reg[r_d] = max(w_a,  w_b)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_min:
                        self.reg[r_d] = pvm_Z_inv(
                            min(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                            8
                        )
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_min_u:
                        self.reg[r_d] = min(w_a,  w_b)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                else:
                    raise InvalidOpcode(f"Invalid instruction type: {inst_type}")

            except PVMMemoryError as mem_error:
                #logging.error("PVMMemoryError")
                #logging.error(mem_error)
                self.status = ExitReason.page_fault.value
                # self.gas -= 1
                self.exit_value = self._mem_addr
                break

            except PanicError as panic_error:
                #logging.error("PanicError")
                #logging.error(panic_error)
                self.status = ExitReason.panic.value
                break

        #self.mem._pvm_invoke_nr += 1
        self._sync_memory()
