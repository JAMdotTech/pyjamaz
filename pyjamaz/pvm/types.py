import logging
from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
import numpy.typing as npt

from math import ceil
from dataclasses import dataclass, field
from typing import List, Union, Type, T, Optional, Dict

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.mixins import Serializable
from jamcodec.types import VarInt64, Array, U8, BitArray, UnsignedInteger, Bytes

from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.exceptions import UIntValueError, PanicError, PVMMemoryError
from pyjamaz.settings import DEBUG, DEBUG_PROGRAM_OVERRIDE


class PVMLogger(ABC):

    @abstractmethod
    def hc_regs(self, msg, phase):
        pass

    @abstractmethod
    def hc_log(self, msg, data):
        pass

    @abstractmethod
    def pvm_regs(self, msg) -> None:
        pass

    @abstractmethod
    def hc_debug(self, log_lvl: int, log_lvl_name: str, core_idx: int, service_id: int, target_msg: str, message: str) -> None:
        pass

    @abstractmethod
    def pvm_hash(self):
        pass

    @abstractmethod
    def pvm_counters(self):
        pass

    @abstractmethod
    def pvm_header(self):
        pass


class PVMMemoryMode(Enum):
    inaccesible = 0
    readable    = 1
    writable    = 2


@dataclass
class PVMCode(Serializable):
    # GP-6.4:eq:A.2 (deblob)
    jump_table_entry_count: int = field(metadata={'codec': VarInt64})
    jump_table_entry_size: int = field(metadata={'codec': U8})
    code_length: int = field(metadata={'codec': VarInt64})
    jump_table: List[int] = field(metadata={'codec': Array(U8, 0)})
    code: bytes = field(metadata={'codec': Array(U8, 0)})
    opcode_bitmask: List[bool] = field(metadata={'codec': BitArray(0)})

    @classmethod
    def from_jam_bytes(cls, scale_bytes: JamBytes, strict_decoding=True) -> 'PVMCode':
        jump_table_entry_count = VarInt64.decode(scale_bytes)
        jump_table_entry_size = U8.decode(scale_bytes)
        code_length = VarInt64.decode(scale_bytes)

        jump_table = Array(UnsignedInteger(jump_table_entry_size * 8), jump_table_entry_count).decode(scale_bytes)
        code = Array(U8, code_length).decode(scale_bytes)
        opcode_bitmask = BitArray(code_length, strict_decoding=strict_decoding).decode(scale_bytes)

        return cls(
            jump_table_entry_count=jump_table_entry_count,
            jump_table_entry_size=jump_table_entry_size,
            code_length=code_length,
            jump_table=jump_table,
            code=code,
            opcode_bitmask=opcode_bitmask,
        )

    def to_codec_type(self) -> JamCodecType:
        codec_def = self.to_codec_def()
        # Change definition according to data
        codec_def.arguments['jump_table'] = Array(
            UnsignedInteger(self.jump_table_entry_size * 8), self.jump_table_entry_count
        )
        codec_def.arguments['code'] = Array(U8, self.code_length)
        codec_def.arguments['opcode_bitmask'] = BitArray(self.code_length)

        scale_type = codec_def.new()
        scale_type.deserialize(self)

        return scale_type

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:
        return cls.from_jam_bytes(JamBytes(bytes(data)))

    def serialize(self) -> List[int]:
        return [b for b in self.to_jam_bytes().to_bytes()]


@dataclass
class MemorySection:
    acl: PVMMemoryMode  # Access list for Memory access (PVMMemoryMode; None=no acl, 0=inaccesible, 1=readable, 2==writable)
    address: int    # The absolute memory address of this memory section
    size: int # Note: The (theoretical) max size of this section
    paged_tail: int # Note: the address of the last written index for this section
    contents: npt.NDArray[np.uint8]

    def __init__(self, address, length, contents, acl:PVMMemoryMode):
        if not contents:
            contents = []

        self.acl = acl
        self.address:int = address
        self.size:int = length
        #TODO!!!!!!!!!!!!!!!!! ode aan peter: make nicer!!!!!!
        if self.size > 2**21:
            raise Exception(f'Memory size too large: {self.size}')

        self.contents: npt.NDArray[np.uint8] = np.zeros(self.size, dtype=np.uint8)
        #self.tail = address
        self.update(0, contents)
        #self.paged_tail = address + self.size
        self.paged_tail = PVMMemory.page_size(len(contents)+address)    #TODO: we might need to exclude address from, the paged_size calculation, rename paged_tail to a netter name, abs_section_tail somethingsoething
        self.size = PVMMemory.page_size(len(contents))

    def update(self, idx, _bytes):
        # TODO: implement more efficiently
        for c_idx, val in enumerate(_bytes):
            self.contents[idx+c_idx] = np.uint8(val)
        #self.tail += len(_bytes)

    def contains(self, addr):
        return self.address <= addr < self.address + self.size

    def read_int(self, section_addr: int, length: int) -> np.uint64:
        if section_addr + length > self.size:
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        if length == 0:
            return np.uint64(0)

        elif length == 1:
            return np.uint64(self.contents[section_addr + 0]) % 2**8

        elif length == 2:
            byte0 = np.uint8(self.contents[section_addr + 0])
            byte1 = np.uint16(self.contents[section_addr + 1])
            return np.uint64((byte1 << 8) + byte0) % 2**16

        elif length == 3:
            byte0 = np.uint8(self.contents[section_addr + 0])
            byte1 = np.uint16(self.contents[section_addr + 1])
            byte2 = np.uint32(self.contents[section_addr + 2])
            return np.uint64((byte2 << 16) + (byte1 << 8) + byte0) % 2 ** 32

        elif length == 4:
            byte0 = np.uint8(self.contents[section_addr + 0])
            byte1 = np.uint16(self.contents[section_addr + 1])
            byte2 = np.uint32(self.contents[section_addr + 2])
            byte3 = np.uint32(self.contents[section_addr + 3])
            return np.uint64(
                (byte3 << 24) +
                (byte2 << 16) +
                (byte1 << 8) +
                byte0
            ) % 2**32

        elif length == 8:
            byte0 = np.uint8(self.contents[section_addr + 0])
            byte1 = np.uint16(self.contents[section_addr + 1])
            byte2 = np.uint32(self.contents[section_addr + 2])
            byte3 = np.uint32(self.contents[section_addr + 3])
            byte4 = np.uint64(self.contents[section_addr + 4])
            byte5 = np.uint64(self.contents[section_addr + 5])
            byte6 = np.uint64(self.contents[section_addr + 6])
            byte7 = np.uint64(self.contents[section_addr + 7])
            return np.uint64(
                (byte7 << 56) +
                (byte6 << 48) +
                (byte5 << 40) +
                (byte4 << 32) +
                (byte3 << 24) +
                (byte2 << 16) +
                (byte1 << 8) +
                byte0
            )
        else:
            raise UIntValueError(f"Invalid uint length: {length}")

    def write_int(self, section_addr: int, value: int, length: int):

        if section_addr + length > self.size:
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        # Note: GP applies a modulus over the value to write denoted by their bit length
        if length < 8:
            value = value % (2 ** (length*8))

        if length == 1:
            self.contents[section_addr + 0] = np.uint8(value & 0xFF)
        elif length == 2:
            self.contents[section_addr + 0] = np.uint8(value & 0x00FF)
            self.contents[section_addr + 1] = np.uint8((value & 0xFF00) >> 8)
        elif length == 4:
            self.contents[section_addr + 0] = np.uint8(value & 0x000000FF)
            self.contents[section_addr + 1] = np.uint8((value & 0x0000FF00) >> 8)
            self.contents[section_addr + 2] = np.uint8((value & 0x00FF0000) >> 16)
            self.contents[section_addr + 3] = np.uint8((value & 0xFF000000) >> 24)
        elif length == 8:
            self.contents[section_addr + 0] = np.uint8(value & 0x00000000000000FF)
            self.contents[section_addr + 1] = np.uint8((value & 0x000000000000FF00) >> 8)
            self.contents[section_addr + 2] = np.uint8((value & 0x0000000000FF0000) >> 16)
            self.contents[section_addr + 3] = np.uint8((value & 0x00000000FF000000) >> 24)
            self.contents[section_addr + 4] = np.uint8((value & 0x000000FF00000000) >> 32)
            self.contents[section_addr + 5] = np.uint8((value & 0x0000FF0000000000) >> 40)
            self.contents[section_addr + 6] = np.uint8((value & 0x00FF000000000000) >> 48)
            self.contents[section_addr + 7] = np.uint8((value & 0xFF00000000000000) >> 56)
        else:
            raise UIntValueError(f"Invalid uint length: {length}")


@dataclass
class PVMMemory:
    sections: List[MemorySection]
    section_offsets: List[int]
    _rom: MemorySection
    _heap: MemorySection
    _stack: MemorySection
    _args: MemorySection
    _mem_addr: int
    _section: MemorySection
    _section_addr: int
    _acl: Optional[Dict[int, int]] # TODO convert to PVMMemoryMode??

    SIZE:int = 2**32


    @classmethod
    def allocate(cls, rom_pages, heap_pages, stack_pages, arg_pages):
        _rom = MemorySection(
            address=PVM_INIT_ZONE_SIZE,
            length=rom_pages * PVM_PAGE_SIZE,
            contents=bytes(rom_pages * PVM_PAGE_SIZE),
            acl=PVMMemoryMode.readable
        )
        _heap = MemorySection(
            address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(_rom.size),
            length=heap_pages * PVM_PAGE_SIZE,
            contents=bytes(heap_pages * PVM_PAGE_SIZE),
            acl=PVMMemoryMode.writable
        )
        _stack = MemorySection(
            address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - stack_pages * PVM_PAGE_SIZE,
            length=stack_pages * PVM_PAGE_SIZE,
            contents=bytes(stack_pages * PVM_PAGE_SIZE),
            acl=PVMMemoryMode.writable,
        )
        _arguments = MemorySection(
            address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
            length=arg_pages * PVM_PAGE_SIZE,
            contents=bytes(arg_pages * PVM_PAGE_SIZE),
            acl=PVMMemoryMode.readable
        )

        return PVMMemory(rom=_rom, heap=_heap, stack=_stack, arguments=_arguments)

    def __init__(
        self,
        rom: MemorySection,
        heap: MemorySection,
        stack: MemorySection,
        arguments: MemorySection
    ):
        self._rom = rom
        self._heap = heap
        self._stack = stack
        self._args = arguments

        self._mem_addr = None
        self._section = None
        self._section_addr = None

        self.update_offsets()

        self._acl = {}
        for p in (self._rom, self._heap, self._stack, self._args):
            if not p:
                continue
            page_nr = p.address // PVM_PAGE_SIZE
            nr_pages = p.size // PVM_PAGE_SIZE
            self._acl.update({(page_nr + n): p.acl.value for n in range(nr_pages)})

    def update_offsets(self) -> Optional[MemorySection]:
        self.section_offsets = [p.address for p in (self._rom, self._heap, self._stack, self._args) if p]


    def find_section(self, addr: int) -> Optional[MemorySection]:
        if not self.section_offsets:
            msg = "Memory not initialized"
            logging.error(msg)
            raise PVMMemoryError(msg)

        #GP-0.6.2-eq:A.7
        if addr < 2**16:
            msg = "Invalid memory access"
            logging.debug(msg)
            raise PanicError(msg)

        if self._heap and addr >= self._heap.address and addr <= self._heap.paged_tail:
            return self._heap
        elif self._stack and addr >= self._stack.address and addr <= self._stack.paged_tail:
            return self._stack
        elif self._rom and addr >= self._rom.address and addr <= self._rom.paged_tail:
            return self._rom
        elif self._args and addr >= self._args.address and addr <= self._args.paged_tail:
            return self._args
        else:
            return None


    def write_int(self, addr: int, value: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
            section = self.find_section(addr)
        else:
            section = self._section

        if not section:
            raise PVMMemoryError("MemorySection not found")

        if self._acl is not None:
            page_nr = addr // PVM_PAGE_SIZE
            if not page_nr in self._acl or self._acl[page_nr] < PVMMemoryMode.writable.value:
                raise PVMMemoryError(f"MemorySection {addr} - ({section.size} bytes) is not writable")

        section_addr = (addr - section.address)  #% section.size #TODO: not sure if % necesarry?
        self._section = section
        self._section_addr = section_addr

        # Set the mem page according to the found page for this range
        section.write_int(section_addr, value, length)


    def read_int(self, addr: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
            section = self.find_section(addr)
        else:
            section = self._section

        if not section:
            raise PVMMemoryError("MemorySection not found")

        if self._acl is not None:
            page_nr = addr // PVM_PAGE_SIZE
            if not page_nr in self._acl or self._acl[page_nr] == PVMMemoryMode.inaccesible.value:
                raise PVMMemoryError(f"MemorySection {addr} - ({section.size} bytes) is inaccessible")

        section_addr = (addr - section.address) #% section.size  #TODO: not sure if % necesarry?
        self._section = section
        self._section_addr = section_addr

        # Set the mem page according to the found page for this range
        return section.read_int(section_addr, length)


    def is_accessible(self, address: int, length: int, mode: PVMMemoryMode) -> bool:
        try:
            section = self.find_section(address)
        except (PanicError, PVMMemoryError):
            section = None

        if not section:
            return False

        if length == 0:
            return True

        if mode not in (PVMMemoryMode.readable, PVMMemoryMode.writable):
            raise PVMMemoryError(f"Invalid mode: {mode}")

        if self._acl is not None:
            # Check ACL for all pages that this operation spans
            start_page = address // PVM_PAGE_SIZE
            end_address = address + length - 1
            end_page = end_address // PVM_PAGE_SIZE
            
            for page_nr in range(start_page, end_page + 1):
                if not page_nr in self._acl or self._acl[page_nr] < mode.value:
                    return False

        local_addr = address - section.address
        bytes_required = local_addr + length

        if bytes_required > section.size:
            return False

        return True


    def read_bytes(self, address: int, length: int, padding:int = None) -> bytes:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        if length == 0:
            return bytes()

        section = self.find_section(address)
        if not section:
            raise PVMMemoryError(f"MemorySection not found {address}")

        # if self._acl is not None and self._acl.get(address//PVM_PAGE_SIZE) == PVMMemoryMode.inaccesible.value:
        #     #TODO: check per page if operations spans multiple pages
        #     raise PVMMemoryError(f"MemorySection {section.address} - ({section.size} bytes) is inaccessible")

        section_addr = (address - section.address)  #% section.size  #TODO: not sure if % necesarry?
        section_bytes = (section.size - section_addr)

        if section_bytes < length:
            raise PVMMemoryError(f"Heap overflow {length} > {section_bytes}")

        if self._acl is not None:
            page_nr = address // PVM_PAGE_SIZE
            if not page_nr in self._acl or self._acl[page_nr] == PVMMemoryMode.inaccesible.value:
                raise PVMMemoryError(f"MemorySection {address} - ({section.size} bytes) is nor readable")

        mem_bytes = bytes(section.contents[section_addr:section_addr+length])
        if padding and len(mem_bytes) < padding:
            mem_bytes.ljust(padding, b'\0')

        return mem_bytes


    def write_bytes(self, address: int, content: bytes) -> None:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        bytes_remaining = len(content)
        # TODO: or raise PVMMemoryError?
        if bytes_remaining == 0:
            return

        section = self.find_section(address)
        if not section:
            raise PVMMemoryError(f"MemorySection not found {address}")

        if self._acl is not None:
            page_nr = address // PVM_PAGE_SIZE
            if not page_nr in self._acl or self._acl[page_nr] < PVMMemoryMode.writable.value:
                raise PVMMemoryError(f"MemorySection {address} - ({section.size} bytes) is not writable")

        section_addr = (address - section.address) #% section.size  #TODO: not sure if % necesarry?
        section_bytes = (section.size - section_addr)

        if section_bytes < len(content):
            raise PVMMemoryError(f"Heap overflow {len(content)} > {section_bytes}")

        section.contents[section_addr:section_addr+len(content)] = np.frombuffer(content, dtype=np.uint8)


    def extend_heap(self, size):
        # Note: sbrk opcode
        if size == 0:
            return self._heap.paged_tail

        current_heap_ptr = self._heap.paged_tail
        new_heap_ptr = current_heap_ptr + size
        if new_heap_ptr >= self._stack.address:
            return 0

        next_page_boundary = PVMMemory.page_size(current_heap_ptr)
        if new_heap_ptr > next_page_boundary:
            growth = PVMMemory.page_size(new_heap_ptr) - next_page_boundary
            self._heap.contents = np.concatenate((self._heap.contents, np.zeros(growth, dtype=np.uint8)))
            self._heap.size = len(self._heap.contents)

            # Create ACL of new pages
            next_page_nr = current_heap_ptr // PVM_PAGE_SIZE
            pages = growth // PVM_PAGE_SIZE + 1
            for page_nr in range(pages):
                self._acl[next_page_nr + page_nr] = PVMMemoryMode.writable.value

        self._heap.paged_tail = new_heap_ptr
        return self._heap.paged_tail


    def zero(self, page_idx: int, nr_pages: int):
        mem_addr = page_idx * PVM_PAGE_SIZE

        if not self.section_offsets and mem_addr == PVM_INIT_ZONE_SIZE:
            if not self._rom:
                self._rom = MemorySection(
                    address=PVM_INIT_ZONE_SIZE,
                    length=nr_pages*PVM_PAGE_SIZE,
                    contents=bytes(nr_pages*PVM_PAGE_SIZE),
                    acl=PVMMemoryMode.writable
                )
            addr = page_idx * PVM_PAGE_SIZE - self._rom.address
            mem = self._rom.contents

        elif mem_addr == (2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(self._rom.contents)):
            if not self._heap:
                self._heap = MemorySection(
                    address = (2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(self._rom.contents)),
                    length = nr_pages * PVM_PAGE_SIZE,
                    contents = bytes(nr_pages*PVM_PAGE_SIZE),
                    acl=PVMMemoryMode.writable
                )
            addr = page_idx * PVM_PAGE_SIZE - self._heap.address
            mem = self._heap.contents

        elif self._stack is None:
            if not self._stack:
                self._stack = MemorySection(
                    address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - (nr_pages * PVM_PAGE_SIZE),
                    length=nr_pages * PVM_PAGE_SIZE,
                    contents=bytes(nr_pages * PVM_PAGE_SIZE),
                    acl=PVMMemoryMode.writable
                )
            addr = page_idx * PVM_PAGE_SIZE - self._stack.address
            mem = self._stack.contents

        else:
            raise PVMMemoryError(f"Invalid void operation: MemorySection not found {mem_addr}")

        self.update_offsets()
        for page_nr in range(nr_pages):
            self._acl[page_idx + page_nr] = PVMMemoryMode.writable.value
            for idx in range(PVM_PAGE_SIZE):
                mem[addr + page_nr * PVM_PAGE_SIZE + idx] = 0


    def void(self, page_idx: int, nr_pages: int):
        mem_addr = page_idx * PVM_PAGE_SIZE

        section = self.find_section(mem_addr)
        if not section:
            raise PVMMemoryError(f"MemorySection not found {mem_addr}")

        for page_nr in range(nr_pages):
            self._acl[page_idx + page_nr] = PVMMemoryMode.inaccesible.value
        for x in range(nr_pages * PVM_PAGE_SIZE):
            section.contents[mem_addr-section.address + x] = 0



    @staticmethod
    def page_size(items: int) -> int:
        """
        GP-0.6.2-eq:A.38 (P)
        """
        return PVM_PAGE_SIZE * ceil(items / PVM_PAGE_SIZE)


    @staticmethod
    def zone_size(items: int) -> int:
        """
        GP-0.6.2-eq:A.38 (Z)
        """
        return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)


@dataclass
class PVMProgram(Serializable):
    """

    """
    # c
    code: PVMCode
    # ω
    registers: List[int]
    # µ
    memory: PVMMemory

    name: str = ''

    """
    GP-0.6.2-eq:A.40 | Initializing of memory pages
    """
    @staticmethod
    def init_memory(
            rom_contents: bytes,
            heap_contents: bytes,
            argument_contents: bytes,
            heap_mem_pages: int,
            stack_mem_size: int
    ) -> PVMMemory:

        _rom = MemorySection(
            address=PVM_INIT_ZONE_SIZE,
            length=PVMMemory.page_size(len(rom_contents)),
            contents=rom_contents,
            acl=PVMMemoryMode.readable
        )

        # TODO: add sanity check on heap_mem_size
        _heap = MemorySection(
            address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(rom_contents)),
            length=PVMMemory.page_size(len(heap_contents)) + heap_mem_pages * PVM_PAGE_SIZE,
            contents=heap_contents,
            acl=PVMMemoryMode.writable
        )

        _stack = MemorySection(
            address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - PVMMemory.page_size(stack_mem_size),
            length=PVMMemory.page_size(stack_mem_size),
            contents=bytes(PVMMemory.page_size(stack_mem_size)),    #TODO: hoeft niet dubbel hier
            acl=PVMMemoryMode.writable
        )

        _arguments = MemorySection(
            address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
            length=PVMMemory.page_size(len(argument_contents)),
            contents=argument_contents,
            acl=PVMMemoryMode.readable
        )

        return PVMMemory(rom=_rom, heap=_heap, stack=_stack, arguments=_arguments)


    @staticmethod
    def init_registers(arguments: bytes) -> List[int]:
        """
        GP-0.6.2-eq:A.41
        """
        regs = [0] * 13
        regs[0] = 2**32 - 2**16
        regs[1] = 2**32 - 2*PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
        regs[7] = 2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
        regs[8] = len(arguments)
        return regs


    @classmethod
    def from_serialized_bytes(cls, serialized_program: bytes, argument_contents: bytes, name: Optional[str]) -> Optional['PVMProgram']:
        """
        GP-0.6.6-eq:A.35 (Y)
        """
        try:

            jam_bytes = JamBytes(serialized_program)

            if DEBUG:
                override_heap_mem_pages = None
                if name in DEBUG_PROGRAM_OVERRIDE:
                    with open(DEBUG_PROGRAM_OVERRIDE.get(name)['file'], 'rb') as fp:
                        jam_bytes = JamBytes(fp.read())
                        override_heap_mem_pages = DEBUG_PROGRAM_OVERRIDE.get(name)['heap_mem_pages']

                        metadata = Bytes.decode(jam_bytes)

            # GP?? |o|
            pvm_rom_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? |w|
            pvm_heap_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? z
            heap_mem_pages = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
            # GP?? s
            stack_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? o
            pvm_rom_contents = jam_bytes.get_next_bytes(pvm_rom_size)
            # GP?? w
            pvm_heap_contents = jam_bytes.get_next_bytes(pvm_heap_size)

            pvm_code_size = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
            pvm_code = jam_bytes.get_next_bytes(pvm_code_size)

            if DEBUG and override_heap_mem_pages:
                heap_mem_pages = override_heap_mem_pages

            # GP-0.6.4-eq:A.40
            if (5 * PVM_INIT_ZONE_SIZE +
                PVMMemory.zone_size(pvm_rom_size) +
                PVMMemory.zone_size(pvm_heap_size + heap_mem_pages * PVM_PAGE_SIZE) +
                PVMMemory.zone_size(stack_mem_size) + PVM_INPUT_DATA_SIZE
            ) <= 2**32:

                instance = cls(
                    code=PVMCode.from_jam_bytes(JamBytes(pvm_code)),
                    registers=cls.init_registers(argument_contents),
                    memory=cls.init_memory(pvm_rom_contents, pvm_heap_contents, argument_contents, heap_mem_pages, stack_mem_size),
                    name=name
                )

                #TODO: TEMP HACK TO DEBUG INJECT CUSTOM PROGRAMS!!!!!!!
                if DEBUG:
                    instance._code = pvm_code
                    instance._ram = pvm_heap_contents
                    instance._rom = pvm_rom_contents

                return instance
            else:
                #TODO
                raise Exception("HUH?")

        except RemainingScaleBytesNotEmptyException as e: # TODO deserialize exception
            pass

        return None


    def to_serialized_bytes(self) -> bytes:
        """
        GP-0.6.2-eq:A.35 (Y)
        """
        #TODO!!!!!!!!!!!!!!
        # data = bytes()
        #
        # # GP?? |o|
        # data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
        # # GP?? |w|
        # data += len(self.memory._heap.contents).to_bytes(length=3, byteorder='little')
        # # GP?? z
        # data += int(1).to_bytes(length=2, byteorder='little')
        # # GP?? s
        # data += len(self.memory._stack.contents).to_bytes(length=3, byteorder='little')
        #
        # # GP?? o
        # data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
        # # GP?? w
        # data += len(self.memory._heap.contents).to_bytes(length=3, byteorder='little')
        #
        # code_bytes = self.code.to_jam_bytes().to_bytes()
        # data += int(len(code_bytes)).to_bytes(length=4, byteorder='little')
        # data += code_bytes
        #
        # return data
        return self.code.to_jam_bytes().to_bytes()


    @classmethod
    def initialize(cls, pvm_code: bytes) -> 'PVMProgram':
        pass
