import logging

import numpy as np
import numpy.typing as npt

from typing import List, Dict

from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
#from .memory_debug import get_memory_hash
from .types_new import PVMProgram, PVMMemory, PVMMemoryMode

from .constants_new import (
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
    inst_reg_reg_offset, inst_reg_reg_imm_imm, inst_reg_reg_reg, inst_undefined
)

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR, PVM_PAGE_SIZE


U8 = np.uint8
U16 = np.uint16
U32 = np.uint32
U64 = np.uint64
I8 = np.int8
I16 = np.int16
I32 = np.int32
I64 = np.int64

# --- 64x64 -> 128 helpers to ditch Pythons int() boxing

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


def smul_u64wide(a: I64, b: U64):
    """Signed * Unsigned -> (hi, lo), two's-complement."""
    ua = U64(a)
    hi, lo = umul64wide(ua, b)
    if a < 0:
        hi = U64(hi - b)
    return U64(hi), U64(lo)


def rori64(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate right for 64-bit integers."""
    return U64(((x >> shift_amount) | (x << (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def roli64(x: U64, shift_amount: U64) -> U64:
    """JIT-compiled rotate left for 64-bit integers."""
    return U64(((x << shift_amount) | (x >> (64 - shift_amount))) & 0xFFFFFFFFFFFFFFFF)


def rori32(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate right for 32-bit integers."""
    return U32(((x >> shift_amount) | (x << (32 - shift_amount))) & 0xFFFFFFFF)


def roli32(x: U32, shift_amount: U32) -> U32:
    """JIT-compiled rotate left for 32-bit integers."""
    return U32(((x << shift_amount) | (x >> (32 - shift_amount))) & 0xFFFFFFFF)


def pvm_smod(a: I64, b: I64) -> I64:
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


def pvm_rtz_div(a: I64, b: I64) -> I64:
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


def pvm_X(x: U64, n: U64) -> U64:
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


def pvm_Z(a: U64, n: U64) -> I64:
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
def count_leading_zeroes(value: U64, max_bits=64):
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
def count_trailing_zeroes(value: U64, max_bits=64):
    """JIT-compiled count trailing zeroes."""
    if value == 0:
        return max_bits

    count = 0
    temp = value
    while (temp & 1) == 0:
        count += 1
        temp >>= 1
    return count


def reverse_bytes(x: U64) -> U64:
    """JIT-compiled reverse bytes."""
    result = U64(0)
    for i in range(8):
        byte = U64((x >> U64(i * 8)) & U64(0xFF))
        result |= U64(byte << U64((7 - i) * 8))
    return result


def read_uint(code: npt.NDArray[U8], addr:U32, length:U8) -> U64:
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


def pvm_Z_inv(a: I64, n: U8) -> U64:
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

        # Initialize memory operation lookups
        self._init_mem_ops_lookup()

        # Initialize memory sections storage
        self.mem_sections = []
        self.mem_section_starts = np.array([], dtype=U32)
        self.mem_section_ends = np.array([], dtype=U32)
        self.mem_section_size = np.array([], dtype=U32)
        """
        TODO: for jit version, use from numba.typed import Dict and copy back after invoke
        d = Dict.empty(
            key_type=types.int64,
            value_type=types.int64,
        )
        """
        self.mem_acl: Dict[int, int] = {}

        self._mem_addr: int = -1

        self.mem_inaccesible = PVMMemoryMode.inaccesible
        self.mem_readable = PVMMemoryMode.readable
        self.mem_writable = PVMMemoryMode.writable

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
        return [U64(x) for x in self.reg]


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

        # Access the actual memory sections (rom, heap, stack, args)
        for section in [memory._rom, memory._heap, memory._stack, memory._args]:
            if section:
                self.mem_sections.append(section.contents)
                mem_section_starts.append(section.address)
                mem_section_ends.append(section.paged_tail)
                mem_section_size.append(section.size)
            else:
                self.mem_sections.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)

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
                #logging.critical(f"EXTENDING HEAP: {heap.size}")

            # Create ACL of new pages
            next_page_nr = current_heap_ptr // PVM_PAGE_SIZE
            pages = growth // PVM_PAGE_SIZE + 1
            for page_nr in range(pages):
                self.mem_acl[next_page_nr + page_nr] = self.mem_writable

            #logging.critical(f"????: {heap.size} - {pages} - {next_page_nr}")

        self.mem_section_ends[1] = new_heap_ptr
        return new_heap_ptr


    def find_memory_section(self, addr):
        """Find which memory section an address belongs to"""
        addr = addr % (2**32)  # Wrap address to q32-bit

        # Only check for invalid addresses if not found in any section
        # GP-0.6.2-eq:A.7 - addresses below 2^16 are invalid
        if addr < 2**16:
            raise PanicError("Invalid memory access")

        # TODO: unroll and sort on most accessed memory segments first!
        # Find the section containing this address
        # Note: using <= for upper bound (not <) to match original implementation
        for i in range(len(self.mem_sections)):
            if self.mem_section_starts[i] <= addr <= self.mem_section_ends[i]:
                return i

        return -1  # Not found


    def mem_write(self, opcode, addr, value):
        """Write to memory based on opcode"""
        #TODO: necessary?
        if not self.mem_ops_write[opcode]:
            raise Exception(f"Opcode {opcode} is not a valid memory write operation")

        bytes_to_write = U64(self.mem_ops_bytes[opcode])
        #addr = addr % (2 ** 32)  #TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # Find the memory section
        section_idx = self.find_memory_section(addr)
        if section_idx == -1:
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
            section[section_offset] = U8(value & 0xFF)
        elif bytes_to_write == 2:
            section[section_offset] = U8(value & 0xFF)
            section[section_offset + 1] = U8((value >> 8) & 0xFF)
        elif bytes_to_write == 4:
            section[section_offset] = U8(value & 0xFF)
            section[section_offset + 1] = U8((value >> 8) & 0xFF)
            section[section_offset + 2] = U8((value >> 16) & 0xFF)
            section[section_offset + 3] = U8((value >> 24) & 0xFF)
        elif bytes_to_write == 8:
            section[section_offset] = U8(value & 0xFF)
            section[section_offset + 1] = U8((value >> 8) & 0xFF)
            section[section_offset + 2] = U8((value >> 16) & 0xFF)
            section[section_offset + 3] = U8((value >> 24) & 0xFF)
            section[section_offset + 4] = U8((value >> 32) & 0xFF)
            section[section_offset + 5] = U8((value >> 40) & 0xFF)
            section[section_offset + 6] = U8((value >> 48) & 0xFF)
            section[section_offset + 7] = U8((value >> 56) & 0xFF)
        else:
            raise PVMMemoryError(f"Invalid write length: {bytes_to_write}")


    def _mem_read_int(self, addr: int, bytes_to_read: int):
        section_idx = self.find_memory_section(addr)
        if section_idx == -1:
            raise PVMMemoryError(f"mem_read_int: Memory address {addr} not found in any section")

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        # Check bounds against the actual section size
        if section_offset + bytes_to_read > len(section):
            raise PVMMemoryError(f"mem_read_int: Memory read at {addr} would overflow section")

        # Read bytes in little-endian order
        if bytes_to_read == 1:
            return U64(section[section_offset])
        elif bytes_to_read == 2:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8))
        elif bytes_to_read == 4:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8) |
                    (U64(section[section_offset + 2]) << 16) |
                    (U64(section[section_offset + 3]) << 24))
        elif bytes_to_read == 8:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8) |
                    (U64(section[section_offset + 2]) << 16) |
                    (U64(section[section_offset + 3]) << 24) |
                    (U64(section[section_offset + 4]) << 32) |
                    (U64(section[section_offset + 5]) << 40) |
                    (U64(section[section_offset + 6]) << 48) |
                    (U64(section[section_offset + 7]) << 56))
        else:
            return -1


    def mem_read(self, opcode, addr):
        """Read from memory based on opcode"""
        # TODO: necessary?
        if not self.mem_ops_read[opcode]:
            raise Exception(f"Opcode {opcode} is not a valid memory read operation")

        bytes_to_read = U64(self.mem_ops_bytes[opcode])
        #addr = addr % (2 ** 32)  # TODO: necessary?

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # TODO: zet ook huidig section en skip als we direct zien dat we al de juiste section hebben!!!!!!
        # Find the memory section
        section_idx = self.find_memory_section(addr)
        if section_idx == -1:
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
        if bytes_to_read == 1:
            return U64(section[section_offset])
        elif bytes_to_read == 2:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8))
        elif bytes_to_read == 4:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8) |
                    (U64(section[section_offset + 2]) << 16) |
                    (U64(section[section_offset + 3]) << 24))
        elif bytes_to_read == 8:
            return (U64(section[section_offset]) |
                    (U64(section[section_offset + 1]) << 8) |
                    (U64(section[section_offset + 2]) << 16) |
                    (U64(section[section_offset + 3]) << 24) |
                    (U64(section[section_offset + 4]) << 32) |
                    (U64(section[section_offset + 5]) << 40) |
                    (U64(section[section_offset + 6]) << 48) |
                    (U64(section[section_offset + 7]) << 56))
        else:
            raise PVMMemoryError(f"Invalid read length: {bytes_to_read}")


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

        # GP-0.6.7-section:A.4 Single-Step State Transition
        while self.status == ExitReason.resume.value and self.gas > 0:

            self.gas -= 1
            self.pc = self.pc + self.skip_len
            self.inst_nr += 1

            if self.pc >= self.code_size:
                self.status = ExitReason.panic.value
                self.exit_value = None
                break

            # Check if PC is valid
            # if self.pc not in self.inst_pos:
            #     # Invalid PC - this is a panic condition
            #     self.status = ExitReason.panic.value
            #     raise PanicError(f"Invalid PC: {self.pc} is not an instruction boundary")

            inst_index = self.inst_pos[self.pc]
            self.opcode = opcode = self.code[self.pc]
            inst_type = OpcodeScheme[opcode]
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
                    l_x = U64(min(4, self.inst_arg_len[inst_index]))
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

                    l_x = U64(min(4, self.code[self.pc + 1] % 8))
                    l_y = U64(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
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

                    l_x = U64(min(4, self.inst_arg_len[inst_index]))
                    v_x = pvm_Z(read_uint(self.code, self.pc + 1, l_x), l_x)

                    if opcode == op_jump:
                        self.skip_len = v_x
                        self.log and self.log(off1=v_x)
                    else:
                        raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                #GP-0.6.7-section:A.5.6
                elif inst_type == inst_reg_imm:  # InstructionType.reg_imm
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    l_x = U64(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == op_jump_ind:
                        self.skip_len = self.djump(U32(self.reg[r_a]+v_x))
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
                    w_a = self.reg[r_a]

                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    l_x = U64(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = U64(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
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
                    w_a = self.reg[r_a]

                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                    l_x = U64(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = U64(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
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
                        self.reg[r_d] = np.bitwise_count(U32(self.reg[r_a]))
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

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = U64(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
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
                        self.reg[r_a] = pvm_X(U32(w_b) >> U32(U32(v_x) & U32(31)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == op_shar_r_imm_32:
                        self.reg[r_a] = pvm_Z_inv(I32(pvm_Z(U32(w_b), 4)) >> I64(U32(v_x) & U32(31)), 8)
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
                        self.reg[r_a] = pvm_X(U32(v_x) >> U32(U32(w_b) & U32(31)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_alt_32:
                        self.reg[r_a] = pvm_Z_inv(I32(pvm_Z(U32(v_x), 4)) >> I64(U32(w_b) & U32(31)), 8)
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
                        self.reg[r_a] = (w_b + v_x) #% 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_mul_imm_64:
                        self.reg[r_a] = (w_b * v_x) #% 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_l_imm_64:
                        self.reg[r_a] = pvm_X((w_b * 2**(v_x % 64)), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_r_imm_64:
                        self.reg[r_a] = U64(w_b) >> U64(v_x & U64(63))
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_64:
                        self.reg[r_a] = pvm_Z_inv(I64(pvm_Z(w_b, 8)) >> I64(U64(v_x) & U64(63)), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_neg_add_imm_64:
                        #huh?: self.reg[r_a] = ((int(v_x) + 2**64 - int(w_b)) % 2**64)
                        self.reg[r_a] = U64(v_x) + U64(-w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_l_imm_alt_64:
                        self.reg[r_a] = (v_x * 2**(w_b % 64)) #% 2**64
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shlo_r_imm_alt_64:
                        self.reg[r_a] = U64(v_x) >> U64(w_b & U64(63))
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_shar_r_imm_alt_64:
                        self.reg[r_a] = pvm_Z_inv(I64(pvm_Z(v_x, 8)) >> I64(U64(w_b) & U64(63)), 8)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_64_imm:
                        self.reg[r_a] = rori64(w_b, v_x)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_64_imm_alt:
                        self.reg[r_a] = rori64(v_x, w_b)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_32_imm:
                        self.reg[r_a] = pvm_X(rori32(U32(w_b), U32(v_x)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == op_rot_r_32_imm_alt:
                        self.reg[r_a] = pvm_X(rori32(U32(v_x), U32(w_b)), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.11
                elif inst_type == inst_reg_reg_offset:  # InstructionType.reg_reg_offset
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

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
                    w_b = self.reg[r_b]

                    l_x = U64(min(4, self.code[self.pc + 2] % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 3, l_x), l_x)

                    l_y = U64(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 2)))
                    v_y = pvm_X(read_uint(self.code, self.pc + 3 + l_x, l_y), l_y)

                    if opcode == op_load_imm_jump_ind:
                        self.reg[r_a] = v_x
                        self.skip_len = self.djump((U64(w_b) + U64(v_y)) % 2**32)
                        self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": self.skip_len})
                    else:
                        raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.13
                elif inst_type == inst_reg_reg_reg:  # InstructionType.reg_reg_reg

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    r_d = min(12, self.code[self.pc + 2])

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

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
                            self.reg[r_d] = pvm_X(U32(w_a) // U32(w_b), 4)

                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_s_32:
                        a = I32(pvm_Z(w_a % 2**32, 4))
                        b = I32(pvm_Z(w_b % 2**32, 4))

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
                        self.reg[r_d] = pvm_X(U32(w_a) >> U32(U32(w_b) & U32(31)), 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shar_r_32:
                        self.reg[r_d] = pvm_Z_inv(I32(pvm_Z(U32(w_a), 4)) >> I64(U32(w_b) & U32(31)), 8)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_add_64:
                        self.reg[r_d] = (w_a + w_b) #% 2**64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_sub_64:
                        #TODO:huh: self.reg[r_d] = (int(w_a) + 2**64 - int(w_b)) % 2**64
                        self.reg[r_d] = U64(w_a) + U64(-w_b)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_64:
                        self.reg[r_d] = (w_a * w_b) #% 2**64
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_u_64:
                        if w_b == 0:
                            self.reg[r_d] = U64(0xFFFFFFFFFFFFFFFF)
                        else:
                            self.reg[r_d] = U64(U64(w_a) // U64(w_b))
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_div_s_64:
                        if w_b == 0:
                            self.reg[r_d] = 2**64 - 1
                        elif pvm_Z(w_a, 8) == -2**63 and pvm_Z(w_b, 8) == -1:
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
                        self.reg[r_d] = U64(w_a) >> U64(w_b & U64(63))
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_shar_r_64:
                        self.reg[r_d] = pvm_Z_inv(I64(pvm_Z(w_a, 8)) >> I64(U64(w_b) & U64(63)), 8)
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
                        hi, _lo = imul64wide(I64(w_a), I64(w_b))
                        self.reg[r_d] = U64(hi)  # store as word (two's-complement bits)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_upper_u_u:
                        # unsigned * unsigned: just take high word of 128-bit product
                        hi, _lo = umul64wide(U64(w_a), U64(w_b))
                        self.reg[r_d] = U64(hi)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_mul_upper_s_u:
                        # signed * unsigned: use mixed helper
                        hi, _lo = smul_u64wide(I64(w_a), U64(w_b))
                        self.reg[r_d] = U64(hi)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_set_lt_u:
                        self.reg[r_d] = U64(w_a < w_b)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_set_lt_s:
                        self.reg[r_d] = I64(pvm_Z(w_a, 8) < pvm_Z(w_b,8))
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
                        self.reg[r_d] = pvm_X(roli32(U32(w_a), w_b % 32), 4)
                        self.log and self.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_r_64:
                        self.reg[r_d] = rori64(w_a, w_b % 64)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_rot_r_32:
                        self.reg[r_d] = pvm_X(rori32(U32(w_a), w_b % 32), 4)
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_and_inv:
                        self.reg[r_d] = w_a & ~w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_or_inv:
                        self.reg[r_d] = w_a | ~w_b
                        self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == op_xnor:
                        self.reg[r_d] = U64(~(w_a ^ w_b))
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
            finally:
                #self.mem._pvm_invoke_nr += 1
                self._sync_memory()
