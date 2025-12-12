import traceback
import typing

import numpy as np
from array import array
from typing import List, Dict

from pyjamaz.pvm.exceptions import PVMMemoryError, PanicError
from pyjamaz.pvm.memory_section_abstract import page_size
from .memory_section import set_range_acl, check_acl, ACL_PAGES_PER_BITMAP

from .defs import read_uint, write_uint, u64, u32, i64, u8
from .opcodes import _opcode_lut

from pyjamaz.pvm.constants import (
    ExitReason,
    MemOps,
    OpcodeNames,
    OpcodeScheme,
    Opcode,
    ExitCondition,
    PVM_PAGE_SIZE, MEM_I, MEM_R, MEM_W,
)
from pyjamaz.pvm.types import PVMProgram
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.pvm.gas_model import GasModel
from pyjamaz.pvm.basic_block import detect_basic_blocks, get_block_start
from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR


class PVMInterpreter:
    __slots__ = (
        'name', 'reg', 'inst_nr', 'pc', 'opcode', 'skip_len', 'gas',
        'code', 'code_size', 'code_length', 'jump_table', 'inst_bitmask', 'inst_pos',
        'inst_arg_len', 'mv_inst_arg_len', 'mem', 'status', 'exit_value',
        'mem_ops_bytes', 'mem_sections', 'mem_section_access', 'mem_section_acl',
        'mem_section_starts', 'mem_section_ends', 'mem_section_size',
        '_mem_addr', 'ROM_ADDR', 'ROM_END', 'HEAP_ADDR', 'HEAP_END',
        'STACK_ADDR', 'STACK_END', 'ARG_ADDR', 'ARG_END',
        'mem_inaccesible', 'mem_readable', 'mem_writable', 'mv_code',
        'mv_sections', 'log', 'opcodes', 'program',

        'gas_model', 'basic_block_gas', 'basic_block_starts_sorted', 'current_block_start',
    )

    def __init__(self, program: PVMProgram, logger=None):
        self.name = program.name
        self.program = program
        self.reg = [u64(0)] * 13
        self.inst_nr = u32(0)
        self.pc = u32(0)
        self.opcode:int = 0
        self.skip_len: int = 0
        self.gas = i64(0)
        self.code = None
        self.code_size = u64(0)
        self.code_length = 0
        self.jump_table = []

        # Gas model attributes
        self.basic_block_gas = {}
        self.basic_block_starts_sorted = []
        self.current_block_start = None
        self.gas_model = None

        self.inst_bitmask: List[bool] = []
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []
        self.mv_inst_arg_len: memoryview = None

        self.mem:PVMMemory = None
        self.status:int = ExitReason.resume.value
        self.exit_value:int = None

        # Initialize memory sections storage
        self._init_mem_ops_lookup()

        # Initialize memory sections storage
        self.mem_sections = []
        self.mem_section_access = []
        self.mem_section_acl = []
        self.mem_section_starts = []
        self.mem_section_ends = []
        self.mem_section_size = []

        self._mem_addr: int = -1

        self.ROM_ADDR = 0xFFFFFFFF
        self.ROM_END = -1
        self.HEAP_ADDR = 0xFFFFFFFF
        self.HEAP_END = -1
        self.STACK_ADDR = 0xFFFFFFFF
        self.STACK_END = -1
        self.ARG_ADDR = 0xFFFFFFFF
        self.ARG_END = -1

        self.mem_inaccesible = MEM_I
        self.mem_readable = MEM_R
        self.mem_writable = MEM_W

        self.mv_code = None
        self.mv_sections = [None, None, None, None]

        self.log = None
        #self.op_time = 0

        self.reset(program)
        self.opcodes = _opcode_lut()

        if logger:
            from pyjamaz.pvm.debug_logger import PVMDebugLog
            logger_cls = PVMDebugLog
            self.log = logger_cls(pvm=self)
            self.log._pvm = self
            self.log._pvm_id = self.name
            for opcode_name in OpcodeNames.values():
                if opcode_name not in self.log.log_opcodes:
                    self.log.log_opcodes[opcode_name] = 0


    def create_instruction_lookup(self):
        """
        Create lookups for byte_pos -> instruction_nr and instruction_nr->instruction_length
        Note: Does NOT create memoryview - caller must do so after any additional appends.
        """
        self.inst_pos = {0: 0}
        self.inst_arg_len = array("B")

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
            # Only add to inst_pos if this position has an opcode in the bitmask
            if inst_bitmask_idx - 1 < len(inst_bitmask) and inst_bitmask[inst_bitmask_idx - 1]:
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
        self.pc = u32(0)
        self.gas = i64(0)

        self.name = program.name
        # GP-0.7.2:A.4 - Store original code and add synthetic trap
        self.code = bytearray(program.code.code)
        self.code_length = len(self.code)  # Original length BEFORE synthetic trap
        self.code.append(Opcode.trap.value)  # Synthetic trap at end
        self.code_size = u64(len(self.code))
        self.mem = program.memory
        self.jump_table = [x.value for x in program.code.jump_table]

        # Initialize memory sections from the PVMMemory object (just reference where possible)
        self._link_memory(program.memory)

        for idx, val in enumerate(program.registers):
            self.reg[idx] = u64(val)

        self.status = ExitReason.resume.value

        self.inst_bitmask: List[bool] = program.code.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []
        self.mv_inst_arg_len = None

        self.create_instruction_lookup()

        # GP-0.7.2:A.4 - Update inst_pos for synthetic trap position
        # Note: must append before recreating memoryview
        self.inst_pos[self.code_length] = len(self.inst_arg_len)
        self.inst_arg_len.append(0)
        self.mv_inst_arg_len = memoryview(self.inst_arg_len)

        # Initialize gas model
        self.gas_model = GasModel(
            code=self.code,
            inst_pos=self.inst_pos,
            inst_arg_len=self.inst_arg_len,
            opcode_scheme=OpcodeScheme,
            opcode_enum=Opcode,
            mem_model="L2HIT",
            jump_table=self.jump_table,
        )
        self._calculate_basic_block_gas()


    def _calculate_basic_block_gas(self):
        """
        GP-0.7.2-section:A.3 - Calculate gas costs for all basic blocks.
        Uses the shared detect_basic_blocks function from basic_block module.
        """
        if not self.gas_model:
            return

        # Detect all basic block starts using the shared function
        basic_block_starts = detect_basic_blocks(
            code=self.code,
            code_length=self.code_length,
            inst_pos=self.inst_pos,
            inst_arg_len=self.inst_arg_len,
        )

        # Store sorted block starts for O(log n) lookup via binary search
        self.basic_block_starts_sorted = sorted(basic_block_starts)

        # Calculate the gas per block
        self.basic_block_gas = {}
        for start in self.basic_block_starts_sorted:
            self.basic_block_gas[start] = self.gas_model.compute_block_gas_cost(start)

    def get_block_start(self, pc: int) -> int:
        """Find the basic block that contains the given PC using binary search."""
        return get_block_start(self.basic_block_starts_sorted, pc)

    #TODO: registers_as_int
    def get_registers(self):
        return [int(x) for x in self.reg]


    def _init_mem_ops_lookup(self):
        """Initialize memory operation lookups as numpy arrays for fast access"""
        # Create lookup arrays for memory operations
        self.mem_ops_bytes = [u8(0)] * 256

        # Populate the lookup arrays from MemOps
        for opcode, ops in MemOps.items():
            self.mem_ops_bytes[opcode] = u8(ops["bytes"])


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

                self.mem_section_access.append(section.acl)
                self.mem_section_acl.append(section.acl_bitmap)
                self.mem_sections.append(section.contents)
                mem_section_starts.append(section.address)
                mem_section_ends.append(section.paged_tail)
                mem_section_size.append(section.size)
                self.mv_sections[idx] = memoryview(section.contents)
            else:
                self.mem_section_access.append(None)
                self.mem_section_acl.append(None)
                self.mem_sections.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)
                self.mv_sections[idx] = None

        self.mem_section_starts = mem_section_starts
        self.mem_section_ends = mem_section_ends
        self.mem_section_size = mem_section_size


    def _sync_memory(self):
        """Sync memory state back to original PVMMemory and MemorySection objects after execution"""
        if self.mem_sections and self.mem_section_starts[1]:
            if self.mem._heap:
                self.mem._heap.contents = self.mem_sections[1]
                self.mem._heap.size = len(self.mem_sections[1])
                self.mem._heap.paged_tail = self.mem_section_ends[1]
                self.mem._heap.acl_bitmap = self.mem_section_acl[1]
            self.mem._mem_addr = self._mem_addr


    def _sbrk(self, size):
        heap = self.mem_sections[1]
        cur_size = len(heap)

        if size == 0:
            return self.mem_section_ends[1]

        current_heap_ptr = self.mem_section_ends[1]
        new_heap_ptr = current_heap_ptr + size
        if new_heap_ptr >= self.mem_section_starts[2]:
            return 0

        next_page_boundary = page_size(current_heap_ptr)
        new_heap_end = page_size(new_heap_ptr)
        growth = new_heap_end - next_page_boundary
        self.log and self.log.sbrk(current_heap_ptr, next_page_boundary, growth, new_heap_ptr > next_page_boundary)

        if new_heap_ptr > next_page_boundary:
            # Only grow when we exceed pre-allocated heap mem
            if new_heap_end - self.mem_section_starts[1] > cur_size:
                # Calculate the total new size based on page boundaries
                new_size = cur_size + growth
                new_buf = bytearray(new_size)
                new_buf[:cur_size] = heap
                self.mem_sections[1] = new_buf
                self.mv_sections[1] = memoryview(self.mem_sections[1])

                # Note: when using bitmaps, we only need to allocate a new bitmap when we allocate new pages
                # Create ACL of new pages
                prev_page_count = cur_size // PVM_PAGE_SIZE
                new_page_count = new_size // PVM_PAGE_SIZE
                bitmap_count = len(self.mem_section_acl[1])
                # note: ceil div: -(-a // b)
                bitmaps_required = -(-new_page_count // ACL_PAGES_PER_BITMAP)

                if bitmaps_required > bitmap_count:
                    extended = np.zeros(bitmaps_required, dtype=np.uint64)
                    if bitmap_count > 0:
                        extended[:bitmap_count] = self.mem_section_acl[1]
                    self.mem_section_acl[1] = extended
                    self.log and self.log.acl(bitmap_count, bitmaps_required, bitmaps_required - bitmap_count)

                if new_page_count > prev_page_count and len(self.mem_section_acl[1]):
                    pages_to_enable = new_page_count - prev_page_count
                    set_range_acl(self.mem_section_acl[1], prev_page_count, pages_to_enable, self.mem_writable)

        self.mem_section_ends[1] = new_heap_ptr
        self.HEAP_END = new_heap_ptr
        return new_heap_ptr


    def mem_write(self, opcode, addr, value):
        """Write to memory based on opcode"""
        bytes_to_write = self.mem_ops_bytes[opcode]

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        # Find the memory section
        section_idx = -1
        if self.HEAP_ADDR <= addr <= self.HEAP_END: section_idx = 1
        elif self.STACK_ADDR <= addr <= self.STACK_END: section_idx = 2
        elif self.ROM_ADDR <= addr <= self.ROM_END: section_idx = 0
        elif self.ARG_ADDR <= addr <= self.ARG_END: section_idx = 3

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            # Fall back to PVMMemory for dynamically mapped sections
            try:
                self.mem.write_int(addr, value, bytes_to_write)
            finally:
                # Capture the memory address even when an exception is raised (e.g., for page fault address)
                self._mem_addr = self.mem._mem_addr
            return

        section = self.mem_sections[section_idx]
        section_offset = addr - self.mem_section_starts[section_idx]

        if self.mem_section_access[section_idx] is not None and self.mem_section_access[section_idx] < MEM_W:
            raise PVMMemoryError(f"Memory at address {addr} is not writable")

        # Check bounds against the actual section size (not paged_tail)
        # The section might be larger than paged_tail if it has been extended
        if section_offset + bytes_to_write > (self.mem_section_ends[section_idx]-self.mem_section_starts[section_idx]): #len(section):
            raise PVMMemoryError(f"Memory write at {addr} would overflow section")

        # Apply modulus for values less than 8 bytes
        if bytes_to_write < 8:
            value = value % (2 ** (bytes_to_write * 8))

        # Write bytes in little-endian order
        return write_uint(section, section_offset, bytes_to_write, value)


    def mem_read(self, opcode, addr):
        """Read from memory based on opcode"""
        bytes_to_read = self.mem_ops_bytes[opcode]

        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        section_idx = -1
        if self.HEAP_ADDR <= addr <= self.HEAP_END: section_idx = 1
        elif self.STACK_ADDR <= addr <= self.STACK_END: section_idx = 2
        elif self.ROM_ADDR <= addr <= self.ROM_END: section_idx = 0
        elif self.ARG_ADDR <= addr <= self.ARG_END: section_idx = 3

        if section_idx == -1 or self.mem_sections[section_idx] is None:
            # Fall back to PVMMemory for dynamically mapped sections
            try:
                result = self.mem.read_int(addr, bytes_to_read)
                return result
            finally:
                # Capture the memory address even when an exception is raised (e.g., for page fault address)
                self._mem_addr = self.mem._mem_addr

        section_offset = addr - self.mem_section_starts[section_idx]

        if section_offset + bytes_to_read > (self.mem_section_ends[section_idx]-self.mem_section_starts[section_idx]): #len(section):
            raise PVMMemoryError(f"Memory read at {addr} would overflow section")

        if self.mem_section_access[section_idx] is not None and self.mem_section_access[section_idx] < MEM_R:
            raise PVMMemoryError(f"Memory at address {addr} is not writable")

        return read_uint(self.mv_sections[section_idx], section_offset, bytes_to_read)


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
        self.skip_len = self.mv_inst_arg_len[inst_index] + 1


    def invoke(
        self,
        pc: int,
        gas: int
    ):
        self.pc = pc
        self.gas = gas

        # Reset per-run execution state so invoking multiple times continues execution
        # from the provided pc/gas rather than a prior exit status.
        # Track if we're resuming from page-fault to skip gas charge on first iteration
        skip_first_block_charge = False
        if self.status == ExitReason.page_fault.value:
            # Re-execute the faulting instruction after the caller adjusted memory.
            self.skip_len = 0
            skip_first_block_charge = True
        self.status = ExitReason.resume.value

        # Note: we cache attribute lookups and globals to locals for the pvm hot loop
        log = self.log
        code = self.code
        code_size = self.code_size
        inst_pos = self.inst_pos
        mv_inst_arg_len = self.mv_inst_arg_len
        op_funcs = self.opcodes
        exit_resume = ExitReason.resume.value
        exit_oom = ExitReason.out_of_gas.value
        exit_panic = ExitReason.panic.value
        exit_page_fault = ExitReason.page_fault.value
        log_exc = None
        pc_local = pc
        gas_local = gas
        status = self.status
        skip_len = self.skip_len
        inst_nr = self.inst_nr

        # Gas model: cache block lookup data
        basic_block_starts_sorted = self.basic_block_starts_sorted
        basic_block_gas = self.basic_block_gas
        current_block_start = self.current_block_start

        if log:
            log.pvm_counters()
            log.pvm_header()
            log_exc = log.exc

        while status == exit_resume:

            pc_local += skip_len
            inst_nr += 1

            if pc_local >= code_size:
                status = exit_panic
                self.exit_value = None
                break

            try:
                inst_index = inst_pos[pc_local]
            except KeyError:
                status = exit_panic
                self.exit_value = None
                break

            # Gas model: find containing basic block and charge gas
            # GP-0.7.2-section:A.3 - Charge when entering a block at its start
            if basic_block_starts_sorted:
                block_start = get_block_start(basic_block_starts_sorted, pc_local)

                if block_start is not None:
                    charge_block = False
                    if current_block_start is None:
                        # First instruction - charge for initial block
                        charge_block = True
                    elif pc_local == block_start:
                        if current_block_start != block_start:
                            # PC is at the start of a NEW block - charge for entering new block
                            charge_block = True
                        elif not skip_first_block_charge:
                            # Back at start of same block via backward branch - charge for re-entry
                            charge_block = True

                    if charge_block:
                        block_cost = basic_block_gas[block_start]
                        if gas_local < block_cost:
                            status = exit_oom
                            self.exit_value = None
                            break
                        gas_local -= block_cost

                    current_block_start = block_start

            # Clear page-fault flag after first iteration (must be outside gas model check)
            skip_first_block_charge = False

            opcode = code[pc_local]
            skip_len = mv_inst_arg_len[inst_index] + 1

            self.opcode = opcode
            self.skip_len = skip_len
            self.pc = pc_local
            self.inst_nr = inst_nr
            self.gas = gas_local
            self.status = status

            try:
                op_funcs[opcode](self)
            except PVMMemoryError:
                log_exc and log_exc(traceback.format_exc())
                status = exit_page_fault
                self.exit_value = self._mem_addr
                skip_len = 0  # Don't skip on resume - re-execute the faulting instruction
                break
            except PanicError:
                log_exc and log_exc(traceback.format_exc())
                status = exit_panic
                break

            gas_local = self.gas
            pc_local = self.pc
            skip_len = self.skip_len
            inst_nr = self.inst_nr
            status = self.status

        self.pc = pc_local
        self.gas = gas_local
        self.status = status
        self.skip_len = skip_len
        self.inst_nr = inst_nr
        self.current_block_start = current_block_start

        self._sync_memory()
