import traceback
import typing

import numpy as np
from array import array
from typing import List, Dict

from pyjamaz.pvm.exceptions import PVMMemoryError, PanicError
from pyjamaz.pvm.types import page_size
from .memory_section import (
    set_range_acl,
    check_acl,
    acl_bits,
    acl_bitmap_idx,
    acl_page_idx,
    ACL_PAGES_PER_BITMAP,
)

from .defs import read_uint, write_uint, u64, u32, i64, u8
from .opcodes import _opcode_lut

from pyjamaz.pvm.constants import (
    ExitReason,
    MemOps,
    OpcodeNames,
    OpcodeScheme,
    Opcode,
    TERMINATION_OPCODES,
    ExitCondition,
    PVM_PAGE_SIZE, MEM_I, MEM_R, MEM_W,
)
from pyjamaz.pvm.types import PVMProgram
from .memory import PVMMemory
#from pyjamaz.pvm.gas_model import GasModel
from pyjamaz.pvm.basic_block import detect_basic_blocks, get_block_start
from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR



class PVMInterpreter:
    __slots__ = (
        'name', 'reg', 'prev_reg', 'inst_nr', 'pc', 'opcode', 'skip_len', 'gas',
        'code', 'code_size',  'code_length', 'jump_table', 'inst_bitmask', 'inst_pos',
        'inst_arg_len', 'mv_inst_arg_len', 'mem', 'status', 'exit_value',
        'mem_ops_bytes', 'mem_sections', 'mem_section_access', 'mem_section_acl',
        'mem_section_starts', 'mem_section_ends', 'mem_section_size',
        '_mem_addr', 'ROM_ADDR', 'ROM_END', 'HEAP_ADDR', 'HEAP_END',
        'STACK_ADDR', 'STACK_END', 'ARG_ADDR', 'ARG_END',
        'mem_inaccesible', 'mem_readable', 'mem_writable', 'mv_code',
        'mv_sections', 'log', 'opcodes', 'program',

        'gas_model', 'basic_block_gas', 'basic_block_starts_set', 'basic_block_starts_sorted', 'current_block_start',
    )

    @staticmethod
    def alloc_memory(
        rom_start: int,
        rom_size: int,
        rom_contents: bytes,
        heap_start: int,
        heap_size: int,
        heap_contents: bytes,
        stack_start: int,
        stack_size: int,
        argument_start: int,
        argument_size: int,
        argument_contents: bytes,
    ) -> PVMMemory:
        from .memory_section import MemorySection

        mem = PVMMemory(
            rom=MemorySection(address=rom_start, size=rom_size, contents=rom_contents, acl=MEM_R),
            heap=MemorySection(address=heap_start, size=heap_size, contents=heap_contents, acl=MEM_W),
            stack=MemorySection(address=stack_start, size=stack_size, contents=bytes(stack_size), acl=MEM_W),
            arguments=MemorySection(address=argument_start, size=argument_size, contents=argument_contents, acl=MEM_R),
        )

        mem.heap_base = heap_start
        mem.heap_ptr = heap_start + heap_size
        mem.stack_base = stack_start
        return mem

    def __init__(self, program: PVMProgram, logger=None):
        self.name = program.name
        self.program = program
        self.reg = [u64(0)] * 13
        self.prev_reg = [u64(0)] * 13
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
        self.basic_block_starts_set = set()
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
            #from pyjamaz.pvm.debug_logger import PVMDebugLog
            from pyjamaz.pvm.formatted_logger import PVMFormattedLog
            logger_cls = PVMFormattedLog
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
        self.inst_arg_len = array("B")

        inst_nr = 0
        inst_bitmask = self.inst_bitmask
        inst_bitmask_idx = 1

        # Note: In the exceptional case we only have 1 instruction (trap or fallthrough), we add it manually and be done
        if len(inst_bitmask) == 1:
            self.inst_arg_len.append(0)
            self.mv_inst_arg_len = memoryview(self.inst_arg_len)
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

            # GP-0.7.2-eq:A.20 (l)
            self.inst_arg_len.append(inst_args)
            inst_nr += 1
            # Only add to inst_pos if this position has an opcode in the bitmask
            if inst_bitmask_idx - 1 < len(inst_bitmask) and inst_bitmask[inst_bitmask_idx - 1]:
                self.inst_pos[inst_bitmask_idx - 1] = inst_nr

        self.mv_inst_arg_len = memoryview(self.inst_arg_len)


    def branch(self, b:int, C:bool):
        """
        #GP-0.7.2-eq:A.17
        """
        if C:
            target_pc = self.pc + b
            if target_pc not in self.basic_block_starts_set:
                #self.status = ExitCondition.panic.value
                raise PanicError(f"Invalid branch instruction: C={C} b={b} target_pc={target_pc}")
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
        self.mv_inst_arg_len = None
        # Note: must append before recreating memoryview
        self.inst_pos[self.code_length] = len(self.inst_arg_len)
        self.inst_arg_len.append(0)
        self.mv_inst_arg_len = memoryview(self.inst_arg_len)

        # Initialize gas model
        # self.gas_model = GasModel(
        #     code=self.code,
        #     inst_pos=self.inst_pos,
        #     inst_arg_len=self.inst_arg_len,
        #     opcode_scheme=OpcodeScheme,
        #     opcode_enum=Opcode,
        #     mem_model="L2HIT",
        #     jump_table=self.jump_table,
        # )
        self._calculate_basic_block_gas()


    def _calculate_basic_block_gas(self):
        """
        GP-0.7.2-section:A.3 - Calculate gas costs for all basic blocks.
        Uses the shared detect_basic_blocks function from basic_block module.
        """
        # if not self.gas_model:
        #     return

        # Detect all basic block starts using the shared function
        basic_block_starts = detect_basic_blocks(
            code=self.code,
            code_length=self.code_length,
            inst_pos=self.inst_pos,
            inst_arg_len=self.inst_arg_len,
        )

        self.basic_block_starts_set = set(basic_block_starts)
        # Store sorted block starts for O(log n) lookup via binary search
        self.basic_block_starts_sorted = sorted(basic_block_starts)

        # Calculate the gas per block
        self.basic_block_gas = {}
        block_starts = self.basic_block_starts_sorted
        code_size = int(self.code_size)

        for idx, start in enumerate(block_starts):
            block_end = block_starts[idx + 1] if idx + 1 < len(block_starts) else code_size

            instruction_count = 0
            pc = start
            while pc < block_end:
                inst_index = self.inst_pos.get(pc)
                if inst_index is None:
                    raise Exception("huh")
                instruction_count += 1
                if self.code[pc] in TERMINATION_OPCODES:
                    #print(f"BASIC BLOCK: {pc}={instruction_count}")
                    break
                pc += self.inst_arg_len[inst_index] + 1

            self.basic_block_gas[start] = instruction_count

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
        # Store memory sections as shared memoryviews with their boundaries.
        self.ROM_ADDR = 0xFFFFFFFF
        self.ROM_END = -1
        self.HEAP_ADDR = 0xFFFFFFFF
        self.HEAP_END = -1
        self.STACK_ADDR = 0xFFFFFFFF
        self.STACK_END = -1
        self.ARG_ADDR = 0xFFFFFFFF
        self.ARG_END = -1

        mem_section_starts = []
        mem_section_ends = []  # This will use paged_tail, not size
        mem_section_size = []
        mem_section_access = []
        mem_section_acl = []
        mem_sections = []
        mv_sections = [None, None, None, None]

        self.mv_code = memoryview(self.code)

        # Access the actual memory sections (rom, heap, stack, args)
        for idx, section in enumerate([memory._rom, memory._heap, memory._stack, memory._args]):

            if section:
                section_view = memory.view(section.address, section.size)
                section.contents = section_view

                section_end = int(section.paged_tail)
                if idx == 1:
                    # Keep the CPYTHON heap break aligned with canonical memory semantics.
                    section_end = int(memory.heap_ptr)

                if idx == 0:
                    self.ROM_ADDR = int(section.address)
                    self.ROM_END = section_end
                if idx == 1:
                    self.HEAP_ADDR = int(section.address)
                    self.HEAP_END = section_end
                if idx == 2:
                    self.STACK_ADDR = int(section.address)
                    self.STACK_END = section_end
                if idx == 3:
                    self.ARG_ADDR = int(section.address)
                    self.ARG_END = section_end

                mem_section_access.append(section.acl)
                mem_section_acl.append(section.acl_bitmap)
                mem_sections.append(section_view)
                mem_section_starts.append(section.address)
                mem_section_ends.append(section_end)
                mem_section_size.append(section.size)
                mv_sections[idx] = section_view
            else:
                mem_section_access.append(None)
                mem_section_acl.append(None)
                mem_sections.append(None)
                mem_section_starts.append(0)
                mem_section_ends.append(0)
                mem_section_size.append(0)
                mv_sections[idx] = None

        self.mem_section_access = mem_section_access
        self.mem_section_acl = mem_section_acl
        self.mem_sections = mem_sections
        self.mem_section_starts = mem_section_starts
        self.mem_section_ends = mem_section_ends
        self.mem_section_size = mem_section_size
        self.mv_sections = mv_sections


    def _sync_memory(self):
        """Sync memory state back to original PVMMemory and MemorySection objects after execution"""
        if self.mem_sections and self.mem_section_starts[1]:
            if self.mem._heap:
                self.mem._heap.contents = self.mem_sections[1]
                self.mem._heap.size = len(self.mem_sections[1])
                self.mem._heap.paged_tail = self.mem_section_ends[1]
                self.mem._heap.acl_bitmap = self.mem_section_acl[1]
            self.mem.heap_ptr = self.mem_section_ends[1]
        self.mem._mem_addr = self._mem_addr


    def _sbrk(self, size):
        heap = self.mem_sections[1]
        if heap is None:
            return 0

        cur_size = len(heap)

        if size == 0:
            return self.mem_section_ends[1]

        current_heap_ptr = self.mem_section_ends[1]
        new_heap_ptr = current_heap_ptr + size
        stack_start = self.mem_section_starts[2]
        if stack_start and new_heap_ptr >= stack_start:
            return 0

        next_page_boundary = page_size(current_heap_ptr)
        new_heap_end = page_size(new_heap_ptr)
        growth = new_heap_end - next_page_boundary
        self.log and self.log.sbrk(current_heap_ptr, next_page_boundary, growth, new_heap_ptr > next_page_boundary)

        if new_heap_ptr > next_page_boundary:
            # Only grow when we exceed pre-allocated heap mem
            heap_start = self.mem_section_starts[1]
            new_size = new_heap_end - heap_start
            if new_size > cur_size:
                # Keep heap storage as a shared zero-copy view into canonical mmap memory.
                self.mem_sections[1] = self.mem.view(heap_start, new_size)
                self.mv_sections[1] = self.mem_sections[1]
                self.mem_section_size[1] = new_size
                if self.mem._heap:
                    self.mem._heap.contents = self.mem_sections[1]
                    self.mem._heap.size = new_size

                # Note: when using bitmaps, we only need to allocate a new bitmap when we allocate new pages
                # Create ACL of new pages
                prev_page_count = cur_size // PVM_PAGE_SIZE
                new_page_count = new_size // PVM_PAGE_SIZE
                bitmap_count = len(self.mem_section_acl[1]) if self.mem_section_acl[1] is not None else 0
                # note: ceil div: -(-a // b)
                bitmaps_required = -(-new_page_count // ACL_PAGES_PER_BITMAP)

                if bitmaps_required > bitmap_count:
                    extended = np.zeros(bitmaps_required, dtype=np.uint64)
                    if bitmap_count > 0:
                        extended[:bitmap_count] = self.mem_section_acl[1]
                    self.mem_section_acl[1] = extended
                    if self.mem._heap:
                        self.mem._heap.acl_bitmap = extended
                    self.log and self.log.acl(bitmap_count, bitmaps_required, bitmaps_required - bitmap_count)

                if new_page_count > prev_page_count:
                    pages_to_enable = new_page_count - prev_page_count
                    if self.mem_section_acl[1] is not None and len(self.mem_section_acl[1]):
                        set_range_acl(self.mem_section_acl[1], prev_page_count, pages_to_enable, self.mem_writable)

                    abs_start_page = (heap_start // PVM_PAGE_SIZE) + prev_page_count
                    self.mem.change_acl(abs_start_page, pages_to_enable, self.mem_writable)

        self.mem_section_ends[1] = new_heap_ptr
        self.HEAP_END = new_heap_ptr
        if self.mem._heap:
            self.mem._heap.paged_tail = new_heap_ptr
        self.mem.heap_ptr = new_heap_ptr
        return new_heap_ptr


    def find_err_page(self, acl_bitmap, section_offset: int, length: int, required_acl: int) -> int:
        # Note: CPYTHON implements its own memory operations to be inlinded
        if length <= 0:
            return -1

        last_offset = section_offset + length - 1
        start_page = section_offset // PVM_PAGE_SIZE
        end_page = last_offset // PVM_PAGE_SIZE
        required_bits = acl_bits(required_acl)

        for page in range(start_page, end_page + 1):
            bitmap_idx = acl_bitmap_idx(page)
            bitmap = int(acl_bitmap[bitmap_idx]) if bitmap_idx < len(acl_bitmap) else 0
            shift = acl_page_idx(page)
            bits = (bitmap >> shift) & 0b11
            if (bits & required_bits) != required_bits:
                return page

        return -1


    def mem_write(self, opcode, addr, value):
        """Write to memory based on opcode"""
        addr = u32(addr)
        bytes_to_write = self.mem_ops_bytes[opcode]

        try:
            self.mem.write_int(addr, value, bytes_to_write)
        finally:
            self._mem_addr = self.mem._mem_addr


    def mem_read(self, opcode, addr):
        """Read from memory based on opcode"""
        addr = u32(addr)
        bytes_to_read = self.mem_ops_bytes[opcode]

        try:
            return self.mem.read_int(addr, bytes_to_read)
        finally:
            self._mem_addr = self.mem._mem_addr

    #
    # def mem_write(self, opcode, addr, value):
    #     if opcode not in MemOps:
    #         raise Exception(f"Invalid memory operation: {opcode}")
    #
    #     if not MemOps[opcode]["write"]:
    #         raise Exception(f"Not a valid memory write operation: {opcode}")
    #
    #     bytes_to_write = MemOps[opcode]["bytes"]
    #     self.mem.write_int(addr % self.mem.SIZE, value, bytes_to_write)
    #
    #
    # def mem_read(self, opcode, addr):
    #     if opcode not in MemOps:
    #         raise Exception(f"Invalid memory operation: {opcode}")
    #
    #     if not MemOps[opcode]["read"]:
    #         raise Exception(f"Not a valid memory read operation: {opcode}")
    #
    #     bytes_to_read = MemOps[opcode]["bytes"]
    #     return self.mem.read_int(addr % self.mem.SIZE, bytes_to_read)


    #GP-0.7.2-section:A.18
    def djump(self, a: int):
        if a == 2 ** 32 - 2 ** 16:
            self.status = ExitReason.halt.value
            return 0
        if a == 0 or a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0:
            raise PanicError(f"Invalid djump operation: a={a}")

        jump_table_index = a // PVM_DYNAMIC_ALIGNMENT_FACTOR - 1
        if jump_table_index < 0 or jump_table_index >= len(self.jump_table):
            raise PanicError(f"Invalid djump operation: a={a}")

        destination = self.jump_table[jump_table_index]
        if destination not in self.basic_block_starts_set:
            raise PanicError(f"Invalid djump operation: a={a} destination={destination}")

        return destination - self.pc


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

        # Note:
        # Reset per-run execution state so invoking multiple times continues execution
        # from the provided pc/gas rather than a prior exit status.
        if self.status == ExitReason.page_fault.value:
            # Re-execute the faulting instruction after the caller adjusted memory.
            self.skip_len = 0
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

        if log:
            log.pvm_counters()
            log.pvm_header()
            log_exc = log.exc

        while status == exit_resume:

            # prev_gas = gas_local
            # prev_pc = pc_local
            # self.prev_reg[:] = self.reg
            # prev_skip_len = skip_len
            # prev_inst_nr = inst_nr

            if gas_local <= 0:
                status = exit_oom
                self.exit_value = None
                break

            gas_local -= 1
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
                #log_exc and log_exc(traceback.format_exc())
                status = exit_page_fault
                fault_addr = self._mem_addr
                if fault_addr is not None and fault_addr >= 0:
                    fault_addr = fault_addr - (fault_addr % PVM_PAGE_SIZE)
                self.exit_value = fault_addr
                skip_len = 0  # Note: we shouldnt skip on resume and reexecute the faulting instruction

                # gas_local = self.gas
                # pc_local = self.pc
                # skip_len = self.skip_len
                # inst_nr = self.inst_nr

                # gas_local = prev_gas
                # pc_local = prev_pc
                # skip_len = prev_skip_len
                # inst_nr = prev_inst_nr
                # self.reg = self.prev_reg
                break

            except PanicError:
                log_exc and log_exc(traceback.format_exc())
                status = exit_panic

                gas_local = self.gas
                pc_local = self.pc
                skip_len = self.skip_len
                inst_nr = self.inst_nr

                # gas_local = prev_gas
                # pc_local = prev_pc
                # skip_len = prev_skip_len
                # inst_nr = prev_inst_nr
                # self.reg = self.prev_reg
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

        self._sync_memory()
