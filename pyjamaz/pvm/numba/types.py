# import logging
#
# import numpy as np
# import numpy.typing as npt
#
# from math import ceil
# from dataclasses import dataclass, field
# from typing import List, Union, Type, T, Optional
#
# from jamcodec.base import JamBytes, JamCodecType
# from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
# from jamcodec.mixins import Serializable
# from jamcodec.types import VarInt64, Array, U8 as JU8, BitArray, UnsignedInteger, Bytes
#
# from pyjamaz import settings
# from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE
# from pyjamaz.pvm.exceptions import UIntValueError, PanicError, PVMMemoryError
# from pyjamaz.settings import DEBUG, DEBUG_PROGRAM_OVERRIDE
#
#
# MEM_I = 0  # inaccessible memory
# MEM_R = 1  # readable memory
# MEM_W = 2  # writable memory
# MEM_RW = 3  # explicit read/write memory (since we have that bit available anyway :)
#
# ACL_PAGES_PER_BITMAP = 32
# ACL_BITS_PER_PAGE = 2
# ACL_READ_BIT = 0b01
# ACL_WRITE_BIT = 0b10
#
#
# def acl_bits(perm: int) -> int:
#     if perm == MEM_I:
#         return 0
#     if perm == MEM_R:
#         return ACL_READ_BIT
#     if perm in (MEM_W, MEM_RW):
#         return ACL_READ_BIT | ACL_WRITE_BIT
#     return 0
#
#
# def acl_bitmap_idx(page: int) -> int:
#     return page // ACL_PAGES_PER_BITMAP
#
#
# def acl_page_idx(page: int) -> int:
#     return (ACL_PAGES_PER_BITMAP - 1 - (page % ACL_PAGES_PER_BITMAP)) * ACL_BITS_PER_PAGE
#
#
# class PVMMemoryMode:
#     inaccesible = MEM_I
#     readable = MEM_R
#     writable = MEM_W
#
#
# @dataclass
# class PVMCode(Serializable):
#     # GP-6.4:eq:A.2 (deblob)
#     jump_table_entry_count: int = field(metadata={'codec': VarInt64})
#     jump_table_entry_size: int = field(metadata={'codec': JU8})
#     code_length: int = field(metadata={'codec': VarInt64})
#     jump_table: List[int] = field(metadata={'codec': Array(JU8, 0)})
#     code: bytes = field(metadata={'codec': Array(JU8, 0)})
#     opcode_bitmask: List[bool] = field(metadata={'codec': BitArray(0)})
#
#     @classmethod
#     def from_jam_bytes(cls, scale_bytes: JamBytes, strict_decoding=True) -> 'PVMCode':
#         jump_table_entry_count = VarInt64.decode(scale_bytes)
#         jump_table_entry_size = JU8.decode(scale_bytes)
#         code_length = VarInt64.decode(scale_bytes)
#
#         jump_table = Array(UnsignedInteger(jump_table_entry_size * 8), jump_table_entry_count).decode(scale_bytes)
#         code = Array(JU8, code_length).decode(scale_bytes)
#         opcode_bitmask = BitArray(code_length, strict_decoding=strict_decoding).decode(scale_bytes)
#
#         return cls(
#             jump_table_entry_count=jump_table_entry_count,
#             jump_table_entry_size=jump_table_entry_size,
#             code_length=code_length,
#             jump_table=jump_table,
#             code=code,
#             opcode_bitmask=opcode_bitmask,
#         )
#
#     def to_codec_type(self) -> JamCodecType:
#         codec_def = self.to_codec_def()
#         # Change definition according to data
#         codec_def.arguments['jump_table'] = Array(
#             UnsignedInteger(self.jump_table_entry_size * 8), self.jump_table_entry_count
#         )
#         codec_def.arguments['code'] = Array(JU8, self.code_length)
#         codec_def.arguments['opcode_bitmask'] = BitArray(self.code_length)
#
#         scale_type = codec_def.new()
#         scale_type.deserialize(self)
#
#         return scale_type
#
#     @classmethod
#     def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:
#         return cls.from_jam_bytes(JamBytes(bytes(data)))
#
#     def serialize(self) -> List[int]:
#         return [b for b in self.to_jam_bytes().to_bytes()]
#
#
# @dataclass
# class MemorySection:
#     address: int    # The absolute memory address of this memory section
#     size: int # Note: The (theoretical) max size of this section
#     paged_tail: int # Note: the address of the last written index for this section
#     contents: bytearray # Bytes for this section (note: actual type depends on PVM implementation)
#     acl: Optional[np.uint64]  # Default Access Control for this section
#     acl_bitmap: npt.NDArray[np.uint64]  # Bitmask for per page ACL control
#
#     def __init__(self, address, size, contents, acl=None):
#         if not contents:
#             contents = []
#
#         # if size > settings.PVM_MAX_HEAP_SIZE:
#         #     raise PVMMemoryError(f"Memory size too large: {size} > {settings.PVM_MAX_HEAP_SIZE}")
#
#         self.acl = acl
#         self.address:int = address
#         self.size:int = PVMMemory.page_size(size)
#
#         # Note: actual implementation depends on PVM implementation
#         self.alloc_contents(contents)
#
#         paged_size = PVMMemory.page_size(len(contents))
#         self.paged_tail = address + paged_size
#
#         if acl:
#             acl_size = paged_size // PVM_PAGE_SIZE
#             self.acl_bitmap = np.array(acl_size, dtype=np.uint64)
#             self.set_range_acl(0, acl_size, acl)
#
#     def alloc_contents(self, _bytes):
#         # self.contents = np.zeros(self.size, dtype=np.uint8)
#         # if _bytes:
#         #     length = len(_bytes)
#         #     if isinstance(_bytes, (list, tuple)):
#         #         self.contents[0:length] = np.array(_bytes, dtype=np.uint8)
#         #     elif isinstance(_bytes, np.ndarray):
#         #         self.contents[0:length] = _bytes.astype(np.uint8)
#         #     else:
#         #         self.contents[0:length] = np.frombuffer(bytes(_bytes), dtype=np.uint8)
#         raise Exception("implement in pvm")
#
#     def set_content(self, content:bytes, start: int, end: int) -> int:
#         #section.contents[start:end] = np.frombuffer(content, dtype=np.uint8)  numba
#         #section.contents[start:end] = content  cpython
#         raise Exception("implement in pvm")
#
#     def read_uint(self, section: bytearray, addr: int, length: int) -> int:
#         raise Exception("implement in pvm")
#
#     def write_uint(section: bytearray, section_offset: int, bytes_to_write: int, value: int):
#         raise Exception("implement in pvm")
#
#     def contains(self, addr):
#         return self.address <= addr < self.address + self.size
#
#     def read_int(self, section_addr: int, length: int) -> int:
#         if section_addr + length > (self.paged_tail - self.address):  # len(section):
#             msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
#             logging.error(msg)
#             raise PVMMemoryError(msg)
#
#         return self.read_uint(self.contents, section_addr, length)
#
#     def write_int(self, section_addr: int, value: int, length: int):
#
#         if section_addr + length > (self.paged_tail - self.address):  # len(section):
#             msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
#             logging.error(msg)
#             raise PVMMemoryError(msg)
#
#         return self.write_uint(self.contents, section_addr, length, value)
#
#     def set_page_acl(self, page_idx: int, perm: int) -> None:
#         bitmap_idx = acl_bitmap_idx(page_idx)
#         shift = acl_page_idx(page_idx)
#         mask = np.uint64(0b11 << shift)
#         bits = np.uint64(acl_bits(perm) << shift)
#         self.acl_bitmap[bitmap_idx] = np.uint64((self.acl_bitmap[bitmap_idx] & ~mask) | bits)
#
#     def set_range_acl(self, start_page: int, nr_pages: int, acl: int) -> None:
#         if nr_pages <= 0:
#             return
#         for page in range(start_page, start_page + nr_pages):
#             self.set_page_acl(page, acl)
#
#     def check_acl(self, start_page: int, nr_pages: int, required_bits: int) -> bool:
#         if nr_pages <= 0:
#             return True
#
#         end_page = start_page + nr_pages
#         page = start_page
#
#         while page < end_page:
#             bitmap_idx = acl_bitmap_idx(page)
#             bitmap = int(self.acl_bitmap[bitmap_idx]) if bitmap_idx < len(self.acl_bitmap) else 0
#             bitmap_start = bitmap_idx * ACL_PAGES_PER_BITMAP
#             bitmap_end = bitmap_start + ACL_PAGES_PER_BITMAP
#             sub_end = min(end_page, bitmap_end)
#             while page < sub_end:
#                 shift = acl_page_idx(page)
#                 bits = (bitmap >> shift) & 0b11
#                 if (bits & required_bits) != required_bits:
#                     return False
#                 page += 1
#
#         return True
#
#
# @dataclass
# class PVMMemory:
#     sections: List[MemorySection]
#     section_offsets: List[int]
#     _rom: MemorySection
#     _heap: MemorySection
#     _stack: MemorySection
#     _args: MemorySection
#     _mem_addr: int
#     _section: MemorySection
#     _section_addr: int
#
#     SIZE:int = 2**32
#
#     @classmethod
#     def allocate(cls, rom_pages, heap_pages, stack_pages, arg_pages):
#         _rom = MemorySection(
#             address=PVM_INIT_ZONE_SIZE,
#             size=rom_pages * PVM_PAGE_SIZE,
#             contents=bytes(rom_pages * PVM_PAGE_SIZE),
#             acl=MEM_R
#         )
#         _heap = MemorySection(
#             address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(_rom.size),
#             size=heap_pages * PVM_PAGE_SIZE,
#             contents=bytes(heap_pages * PVM_PAGE_SIZE),
#             acl=MEM_W
#         )
#         _stack = MemorySection(
#             address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - stack_pages * PVM_PAGE_SIZE,
#             size=stack_pages * PVM_PAGE_SIZE,
#             contents=bytes(stack_pages * PVM_PAGE_SIZE),
#             acl=MEM_W,
#         )
#         _arguments = MemorySection(
#             address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
#             size=arg_pages * PVM_PAGE_SIZE,
#             contents=bytes(arg_pages * PVM_PAGE_SIZE),
#             acl=MEM_R
#         )
#
#         return PVMMemory(rom=_rom, heap=_heap, stack=_stack, arguments=_arguments)
#
#     def __init__(
#         self,
#         rom: MemorySection,
#         heap: MemorySection,
#         stack: MemorySection,
#         arguments: MemorySection
#     ):
#         self._rom = rom
#         self._heap = heap
#         self._stack = stack
#         self._args = arguments
#
#         self._mem_addr = None
#         self._section = None
#         self._section_addr = None
#
#         self.update_offsets()
#
#     def update_offsets(self) -> Optional[MemorySection]:
#         self.section_offsets = [p.address for p in (self._rom, self._heap, self._stack, self._args) if p]
#
#     def find_section(self, addr: int) -> Optional[MemorySection]:
#         if not self.section_offsets:
#             msg = "Memory not initialized"
#             logging.error(msg)
#             raise PVMMemoryError(msg)
#
#         #GP-0.6.2-eq:A.7
#         if addr < 2**16:
#             msg = "Invalid memory access"
#             logging.debug(msg)
#             raise PanicError(msg)
#
#         if self._heap and addr >= self._heap.address and addr <= self._heap.paged_tail:
#             return self._heap
#         elif self._stack and addr >= self._stack.address and addr <= self._stack.paged_tail:
#             return self._stack
#         elif self._rom and addr >= self._rom.address and addr <= self._rom.paged_tail:
#             return self._rom
#         elif self._args and addr >= self._args.address and addr <= self._args.paged_tail:
#             return self._args
#         else:
#             return None
#
#
#     def write_int(self, addr: int, value: int, length: int):
#         # Always store the requested memory address so we can refer it after a PVMMemoryError fx
#         self._mem_addr = addr
#
#         if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
#             section = self.find_section(addr)
#         else:
#             section = self._section
#
#         if not section:
#             raise PVMMemoryError("MemorySection not found")
#
#         if section.acl is not None:
#             start_page = (addr - section.address) // PVM_PAGE_SIZE
#             end_page = (addr - section.address + length - 1) // PVM_PAGE_SIZE
#             if not section.check_acl(start_page, end_page - start_page + 1, ACL_WRITE_BIT):
#                 raise PVMMemoryError(f"MemorySection {addr} - ({section.size} bytes) is not writable")
#
#         section_addr = (addr - section.address)  #% section.size #TODO: not sure if % necesarry?
#         self._section = section
#         self._section_addr = section_addr
#
#         # Set the mem page according to the found page for this range
#         section.write_int(section_addr, value, length)
#
#
#     def read_int(self, addr: int, length: int):
#         # Always store the requested memory address so we can refer it after a PVMMemoryError fx
#         self._mem_addr = addr
#
#         if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
#             section = self.find_section(addr)
#         else:
#             section = self._section
#
#         if not section:
#             raise PVMMemoryError("MemorySection not found")
#
#         if section.acl is not None:
#             start_page = (addr - section.address) // PVM_PAGE_SIZE
#             end_page = (addr - section.address + length - 1) // PVM_PAGE_SIZE
#             if not section.check_acl(start_page, end_page - start_page + 1, ACL_READ_BIT):
#                 raise PVMMemoryError(f"MemorySection {addr} - ({section.size} bytes) is inaccessible")
#
#         section_addr = (addr - section.address) #% section.size  #TODO: not sure if % necesarry?
#         self._section = section
#         self._section_addr = section_addr
#
#         # Set the mem page according to the found page for this range
#         return section.read_int(section_addr, length)
#
#
#     def is_accessible(self, address: int, length: int, mode: int) -> bool:
#         if length == 0:
#             return True
#
#         try:
#             section = self.find_section(address)
#         except (PanicError, PVMMemoryError):
#             section = None
#
#         if not section:
#             return False
#
#         if mode not in (MEM_R, MEM_W, MEM_RW):
#             raise PVMMemoryError(f"Invalid mode: {mode}")
#
#         start_page = (address - section.address) // PVM_PAGE_SIZE
#         end_page = (address - section.address + length - 1) // PVM_PAGE_SIZE
#         if mode == MEM_R:
#             required = ACL_READ_BIT
#         elif mode == MEM_RW:
#             required = ACL_READ_BIT | ACL_WRITE_BIT
#         else:
#             required = ACL_WRITE_BIT
#
#         if not section.check_acl(start_page, end_page - start_page + 1, required):
#             return False
#
#         local_addr = address - section.address
#         bytes_required = local_addr + length
#
#         if bytes_required > section.size:
#             return False
#
#         return True
#
#
#     def read_bytes(self, address: int, length: int, padding:int = None) -> bytes:
#         """
#         """
#         # Always store the requested memory address so we can refer it after a PVMMemoryError fx
#         self._mem_addr = address
#
#         if length == 0:
#             return bytes()
#
#         section = self.find_section(address)
#         if not section:
#             raise PVMMemoryError(f"MemorySection not found {address}")
#
#         section_addr = (address - section.address)  #% section.size  #TODO: not sure if % necesarry?
#         section_bytes = (section.size - section_addr)
#
#         if section_bytes < length:
#             raise PVMMemoryError(f"Heap overflow {length} > {section_bytes}")
#
#         if section.acl is not None:
#             start_page = (address - section.address) // PVM_PAGE_SIZE
#             end_page = (address - section.address + length - 1) // PVM_PAGE_SIZE
#             if not section.check_acl(start_page, end_page - start_page + 1, ACL_READ_BIT):
#                 raise PVMMemoryError(f"Page {start_page} at address {start_page * PVM_PAGE_SIZE} is not readable")
#
#         mem_bytes = bytes(section.contents[section_addr:section_addr+length])
#         if padding and len(mem_bytes) < padding:
#             mem_bytes.ljust(padding, b'\0')
#
#         return mem_bytes
#
#
#     def write_bytes(self, address: int, content: bytes) -> None:
#         """
#         """
#         # Always store the requested memory address so we can refer it after a PVMMemoryError fx
#         self._mem_addr = address
#
#         bytes_remaining = len(content)
#         # TODO: or raise PVMMemoryError?
#         if bytes_remaining == 0:
#             return
#
#         section = self.find_section(address)
#         if not section:
#             raise PVMMemoryError(f"MemorySection not found {address}")
#
#         if section.acl is not None:
#             start_page = (address - section.address) // PVM_PAGE_SIZE
#             end_page = (address - section.address + len(content) - 1) // PVM_PAGE_SIZE
#             if not section.check_acl(start_page, end_page - start_page + 1, ACL_WRITE_BIT):
#                 raise PVMMemoryError(f"Page {start_page} at address {start_page * PVM_PAGE_SIZE} is not writable")
#
#         section_addr = (address - section.address) #% section.size  #TODO: not sure if % necesarry?
#         section_bytes = (section.size - section_addr)
#
#         if section_bytes < len(content):
#             raise PVMMemoryError(f"Heap overflow {len(content)} > {section_bytes}")
#
#         section.set_content(content, section_addr, section_addr+len(content))
#
#
#     def zero(self, page_idx: int, nr_pages: int, acl: int):
#         mem_addr = page_idx * PVM_PAGE_SIZE
#         # TODO we assume acl should be set this way, cannot test right now
#         if not self.section_offsets and mem_addr == PVM_INIT_ZONE_SIZE:
#             if not self._rom:
#                 self._rom = MemorySection(
#                     address=PVM_INIT_ZONE_SIZE,
#                     size=nr_pages * PVM_PAGE_SIZE,
#                     contents=bytes(nr_pages * PVM_PAGE_SIZE),
#                     acl=acl
#                 )
#             section = self._rom
#         elif mem_addr == (2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(self._rom.contents)):
#             if not self._heap:
#                 self._heap = MemorySection(
#                     address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(self._rom.contents)),
#                     size=nr_pages * PVM_PAGE_SIZE,
#                     contents=bytes(nr_pages * PVM_PAGE_SIZE),
#                     acl=acl
#                 )
#             section = self._heap
#         elif self._stack is None and mem_addr >= (2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - (nr_pages * PVM_PAGE_SIZE)):
#             if not self._stack:
#                 self._stack = MemorySection(
#                     address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - (nr_pages * PVM_PAGE_SIZE),
#                     size=nr_pages * PVM_PAGE_SIZE,
#                     contents=bytes(nr_pages * PVM_PAGE_SIZE),
#                     acl=acl
#                 )
#             section = self._stack
#         else:
#             raise PVMMemoryError(f"Invalid void operation: MemorySection not found {mem_addr}")
#
#         self.update_offsets()
#         addr = page_idx * PVM_PAGE_SIZE - section.address
#         section.set_range_acl(addr // PVM_PAGE_SIZE, nr_pages, acl)
#         section.contents[addr:addr + nr_pages * PVM_PAGE_SIZE] = 0 #TODO: pvm specific?
#
#
#     def void(self, page_idx: int, nr_pages: int, acl: int):
#         mem_addr = page_idx * PVM_PAGE_SIZE
#
#         section = self.find_section(mem_addr)
#         if not section:
#             raise PVMMemoryError(f"MemorySection not found {mem_addr}")
#
#         page_nr = (mem_addr - section.address) // PVM_PAGE_SIZE
#         section.set_range_acl(page_nr, nr_pages, acl)
#         offset = mem_addr - section.address
#         section.contents[offset:offset + nr_pages * PVM_PAGE_SIZE] = 0 #TODO: pvm specific?
#
#
#     def has_inaccessible_acl(self, page_idx: int, nr_pages: int) -> bool:
#         for page in range(page_idx, page_idx + nr_pages):
#             addr = page * PVM_PAGE_SIZE
#             try:
#                 section = self.find_section(addr)
#             except (PanicError, PVMMemoryError):
#                 return True
#
#             if not section:
#                 return True
#
#             # Skip further checks if this page has no acl
#             if section.acl is None:
#                 continue
#
#             page_nr = (addr - section.address) // PVM_PAGE_SIZE
#             bitmap_idx = acl_bitmap_idx(page_nr)
#             if bitmap_idx >= len(section.acl_bitmap):
#                 return True
#
#             shift = acl_page_idx(page_nr)
#             bits = (int(section.acl_bitmap[bitmap_idx]) >> shift) & 0b11
#             if bits == MEM_I:
#                 return True
#
#         return False
#
#     @staticmethod
#     def page_size(items: int) -> int:
#         """
#         GP-0.6.2-eq:A.38 (P)
#         """
#         return PVM_PAGE_SIZE * ceil(items / PVM_PAGE_SIZE)
#
#
#     @staticmethod
#     def zone_size(items: int) -> int:
#         """
#         GP-0.6.2-eq:A.38 (Z)
#         """
#         return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)
#
#
# @dataclass
# class PVMProgram(Serializable):
#     """
#
#     """
#     # c
#     code: PVMCode
#     # ω
#     registers: List[int]
#     # µ
#     memory: PVMMemory
#
#     name: str = ''
#
#     """
#     GP-0.6.2-eq:A.40 | Initializing of memory pages
#     """
#
#     @staticmethod
#     def init_memory(
#             rom_contents: bytes,
#             heap_contents: bytes,
#             argument_contents: bytes,
#             heap_mem_pages: int,
#             stack_mem_size: int
#     ) -> PVMMemory:
#
#         _rom = MemorySection(
#             address=PVM_INIT_ZONE_SIZE,
#             size=PVMMemory.page_size(len(rom_contents)),
#             contents=rom_contents,
#             acl=MEM_R
#         )
#
#         # If PVM_MIN_HEAP_SIZE is set, we preallocate at least that size to (hopefully) prevent lots of memory allocations...
#         heap_mem_size = max(PVMMemory.page_size(settings.PVM_MIN_HEAP_SIZE), PVMMemory.page_size(len(heap_contents)) + heap_mem_pages * PVM_PAGE_SIZE)
#         _heap = MemorySection(
#             address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(rom_contents)),
#             size=heap_mem_size,
#             contents=heap_contents,
#             acl=MEM_W
#         )
#
#         _stack = MemorySection(
#             address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - PVMMemory.page_size(stack_mem_size),
#             size=PVMMemory.page_size(stack_mem_size),
#             contents=bytes(PVMMemory.page_size(stack_mem_size)),    #TODO: hoeft niet dubbel hier
#             acl=MEM_W
#         )
#
#         _arguments = MemorySection(
#             address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
#             size=PVMMemory.page_size(len(argument_contents)),
#             contents=argument_contents,
#             acl=MEM_R
#         )
#
#         return PVMMemory(rom=_rom, heap=_heap, stack=_stack, arguments=_arguments)
#
#
#     @staticmethod
#     def init_registers(arguments: bytes) -> List[int]:
#         """
#         GP-0.6.2-eq:A.41
#         """
#         regs = [0] * 13
#         regs[0] = 2**32 - 2**16
#         regs[1] = 2**32 - 2*PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
#         regs[7] = 2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
#         regs[8] = len(arguments)
#         return regs
#
#
#     @classmethod
#     def from_serialized_bytes(cls, serialized_program: bytes, argument_contents: bytes, name: Optional[str]) -> Optional['PVMProgram']:
#         """
#         GP-0.6.6-eq:A.35 (Y)
#         """
#         try:
#
#             jam_bytes = JamBytes(serialized_program)
#
#             if DEBUG:
#                 override_heap_mem_pages = None
#                 if name in DEBUG_PROGRAM_OVERRIDE:
#                     with open(DEBUG_PROGRAM_OVERRIDE.get(name)['file'], 'rb') as fp:
#                         jam_bytes = JamBytes(fp.read())
#                         override_heap_mem_pages = DEBUG_PROGRAM_OVERRIDE.get(name)['heap_mem_pages']
#
#                         metadata = Bytes.decode(jam_bytes)
#
#             # GP?? |o|
#             pvm_rom_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
#             # GP?? |w|
#             pvm_heap_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
#             # GP?? z
#             heap_mem_pages = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
#             # GP?? s
#             stack_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
#             # GP?? o
#             pvm_rom_contents = jam_bytes.get_next_bytes(pvm_rom_size)
#             # GP?? w
#             pvm_heap_contents = jam_bytes.get_next_bytes(pvm_heap_size)
#
#             pvm_code_size = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
#             pvm_code = jam_bytes.get_next_bytes(pvm_code_size)
#
#             if DEBUG and override_heap_mem_pages:
#                 heap_mem_pages = override_heap_mem_pages
#
#             # GP-0.6.4-eq:A.40
#             if (5 * PVM_INIT_ZONE_SIZE +
#                 PVMMemory.zone_size(pvm_rom_size) +
#                 PVMMemory.zone_size(pvm_heap_size + heap_mem_pages * PVM_PAGE_SIZE) +
#                 PVMMemory.zone_size(stack_mem_size) + PVM_INPUT_DATA_SIZE
#             ) <= 2**32:
#
#                 instance = cls(
#                     code=PVMCode.from_jam_bytes(JamBytes(pvm_code)),
#                     registers=cls.init_registers(argument_contents),
#                     memory=cls.init_memory(pvm_rom_contents, pvm_heap_contents, argument_contents, heap_mem_pages, stack_mem_size),
#                     name=name
#                 )
#
#                 #TODO: TEMP HACK TO DEBUG INJECT CUSTOM PROGRAMS!!!!!!!
#                 if DEBUG:
#                     instance._code = pvm_code
#                     instance._ram = pvm_heap_contents
#                     instance._rom = pvm_rom_contents
#
#                 return instance
#             else:
#                 #TODO
#                 raise Exception("HUH?")
#
#         except RemainingScaleBytesNotEmptyException as e: # TODO deserialize exception
#             pass
#
#         return None
#
#
#     def to_serialized_bytes(self) -> bytes:
#         """
#         GP-0.6.2-eq:A.35 (Y)
#         """
#         #TODO!!!!!!!!!!!!!!
#         # data = bytes()
#         #
#         # # GP?? |o|
#         # data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
#         # # GP?? |w|
#         # data += len(self.memory._heap.contents).to_bytes(length=3, byteorder='little')
#         # # GP?? z
#         # data += int(1).to_bytes(length=2, byteorder='little')
#         # # GP?? s
#         # data += len(self.memory._stack.contents).to_bytes(length=3, byteorder='little')
#         #
#         # # GP?? o
#         # data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
#         # # GP?? w
#         # data += len(self.memory._heap.contents).to_bytes(length=3, byteorder='little')
#         #
#         # code_bytes = self.code.to_jam_bytes().to_bytes()
#         # data += int(len(code_bytes)).to_bytes(length=4, byteorder='little')
#         # data += code_bytes
#         #
#         # return data
#         return self.code.to_jam_bytes().to_bytes()
#
#
#     @classmethod
#     def initialize(cls, pvm_code: bytes) -> 'PVMProgram':
#         pass
