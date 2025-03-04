import bisect

import numpy as np
import numpy.typing as npt

from math import ceil
from dataclasses import dataclass, field
from typing import List, Union, Type, T, Optional

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.mixins import Serializable
from jamcodec.types import VarInt64, Array, U8, BitArray, UnsignedInteger

from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.exceptions import UIntValueError, PanicError, PVMMemoryError


@dataclass
class PVMCode(Serializable):
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
class MemoryPage:
    address: int
    length: int
    break_pointer: int
    writable: bool
    contents: npt.NDArray[np.uint8]

    def __init__(self, address, length, writable, contents):
        self.address:int = address
        self.length:int = length
        self.writable:bool = writable
        self.contents: npt.NDArray[np.uint8] = np.zeros(self.length, dtype=np.uint8)
        if contents:
            self.update(0, contents)

    def update(self, idx, _bytes):
        # TODO: implement more efficiently
        for c_idx, val in enumerate(_bytes):
            self.contents[idx+c_idx] = np.uint8(val)
        self.break_pointer = len(_bytes)

    def contains(self, addr):
        return self.address <= addr < self.address + self.length

    def read(self, address: int, length: int) -> bytes:
        """
        TODO:
        outofbounds offset
        als we vanaf de outofbounds tot length lezen/scwijven -> aanzulen met nullen
        """
        if length == 0:
            return 0

        elif length == 1:
            return np.uint64(self.contents[address + 0]) % 2**8

        elif length == 2:
            byte0 = np.uint8(self.contents[address + 0])
            byte1 = np.uint16(self.contents[address + 1])
            return np.uint64((byte1 << 8) + byte0) % 2**16

        elif length == 3:
            byte0 = np.uint8(self.contents[address + 0])
            byte1 = np.uint16(self.contents[address + 1])
            byte2 = np.uint32(self.contents[address + 2])
            return np.uint64((byte2 << 16) + (byte1 << 8) + byte0) % 2 ** 32

        elif length == 4:
            byte0 = np.uint8(self.contents[address + 0])
            byte1 = np.uint16(self.contents[address + 1])
            byte2 = np.uint32(self.contents[address + 2])
            byte3 = np.uint32(self.contents[address + 3])
            return np.uint64(
                (byte3 << 24) +
                (byte2 << 16) +
                (byte1 << 8) +
                byte0
            ) % 2**32

        elif length == 8:
            byte0 = np.uint8(self.contents[address + 0])
            byte1 = np.uint16(self.contents[address + 1])
            byte2 = np.uint32(self.contents[address + 2])
            byte3 = np.uint32(self.contents[address + 3])
            byte4 = np.uint64(self.contents[address + 4])
            byte5 = np.uint64(self.contents[address + 5])
            byte6 = np.uint64(self.contents[address + 6])
            byte7 = np.uint64(self.contents[address + 7])
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


    def write(self, address: int, value: int, length: int):
        # Note: GP applies a modulus over the value to write denoted by their bit length
        if length < 8:
            value = value % (2 ** (length*8))

        if length == 1:
            self.contents[address + 0] = np.uint8(value & 0xFF)
        elif length == 2:
            self.contents[address + 0] = np.uint8( value & 0x00FF)
            self.contents[address + 1] = np.uint8((value & 0xFF00) >> 8)
        elif length == 4:
            self.contents[address + 0] = np.uint8( value & 0x000000FF)
            self.contents[address + 1] = np.uint8((value & 0x0000FF00) >> 8)
            self.contents[address + 2] = np.uint8((value & 0x00FF0000) >> 16)
            self.contents[address + 3] = np.uint8((value & 0xFF000000) >> 24)
        elif length == 8:
            self.contents[address + 0] = np.uint8( value & 0x00000000000000FF)
            self.contents[address + 1] = np.uint8((value & 0x000000000000FF00) >> 8)
            self.contents[address + 2] = np.uint8((value & 0x0000000000FF0000) >> 16)
            self.contents[address + 3] = np.uint8((value & 0x00000000FF000000) >> 24)
            self.contents[address + 4] = np.uint8((value & 0x000000FF00000000) >> 32)
            self.contents[address + 5] = np.uint8((value & 0x0000FF0000000000) >> 40)
            self.contents[address + 6] = np.uint8((value & 0x00FF000000000000) >> 48)
            self.contents[address + 7] = np.uint8((value & 0xFF00000000000000) >> 56)
        else:
            raise UIntValueError(f"Invalid uint length: {length}")


@dataclass
class PVMMemory:
    pages: List[MemoryPage]
    page_offsets: List[int]
    _rom: MemoryPage
    _heap: MemoryPage
    _stack: MemoryPage
    _args: MemoryPage
    _mem_addr: int
    _page: int
    _page_addr: int

    def __init__(
        self,
        rom: MemoryPage,
        heap: MemoryPage,
        stack: MemoryPage,
        arguments: MemoryPage
    ):
        self._rom = rom
        self._heap = heap
        self._stack = stack
        self._args = arguments

        self.pages: List[MemoryPage] = [rom, heap, stack, arguments]
        self.page_offsets = [p.address for p in self.pages]

        self._mem_addr = None
        self._page = None
        self._page_addr = None

    def find_page(self, addr):
        if not self.page_offsets:
            raise PVMMemoryError("Memory not initialized")

        #GP-0.6.2-eq:A.7
        if addr < 2**16:
            raise PanicError("Invalid memory access")

        # Find rightmost index where addr would be inserted and then check if it falls in the page
        index = bisect.bisect_right(self.page_offsets, addr) - 1
        if index < 0:
            raise PVMMemoryError("Memory not initialized")

        page = self.pages[index]
        if page.contains(addr):
            return page
        else:
            return None

    #TODO: rename to write_int
    def write(self, addr: int, value: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        #TODO: can an int span two pages or is it always 'atomic'? if so, apply similar construct as write_bytes
        if not (self._page and self._page.address <= addr < self._page.address + self._page.length):
            page = self.find_page(addr)
        else:
            page = self._page

        if not page:
            raise PVMMemoryError("Page not found")

        if not page.writable:
            raise PVMMemoryError(f"Page {addr} is not writable")

        page_addr = addr - page.address
        self._page = page
        self._page_addr = page_addr

        if page_addr + length > page.length:
            raise PVMMemoryError(f"Page {page_addr} overflow: {length} ({page.length})")

        # Set the mem page according to the found page for this range
        page.write(page_addr, value, length)

    #TODO: rename to read_int
    def read(self, addr: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        #TODO: can an int span multiple pages or is it always 'atomic'? if so, apply similar construct as read_bytes
        if not (self._page and self._page.address <= addr < self._page.address + self._page.length):
            page = self.find_page(addr)
        else:
            page = self._page

        if not page:
            raise PVMMemoryError("Page not found")

        # if not page.readable:
        #     raise PVMMemoryError(f"Page {addr} is not writable")

        page_addr = addr - page.address
        self._page = page
        self._page_addr = page_addr

        if page_addr + length > page.length:
            raise PVMMemoryError(f"Page {page_addr} overflow: {length} ({page.length})")

        # Set the mem page according to the found page for this range
        return page.read(page_addr, length)

    def read_bytes(self, address: int, length: int) -> bytes:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        if length == 0:
            return bytes()

        addr = address
        pages = []
        bytes_remaining = length
        while bytes_remaining > 0:
            page = self.find_page(addr)
            if not page:
                raise PVMMemoryError(f"Page not found {addr}")

            page_addr = addr - page.address
            page_bytes = min(length, page.length - page_addr)
            pages.append((page, page_addr, min(page_bytes, bytes_remaining)))

            bytes_remaining -= page_bytes
            if bytes_remaining > 0:
                addr += page_bytes

        bytez = bytes()
        for pg in pages:
            bytez += bytes(pg[0].contents[pg[1]:pg[1]+pg[2]])

        return bytez

    def write_bytes(self, address: int, content: bytes) -> bytes:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        bytes_remaining = len(content)
        if bytes_remaining == 0:
            return

        addr = address
        pages = []

        while bytes_remaining > 0:
            page = self.find_page(addr)
            if not page:
                raise PVMMemoryError(f"Page not found {addr}")

            page_addr = addr - page.address
            page_bytes = (page.length - page_addr)
            pages.append((page, page_addr, min(page_bytes, bytes_remaining)))

            bytes_remaining -= page_bytes
            if bytes_remaining > 0:
                addr += page_bytes

        offset = 0
        for pg in pages:
            pg[0].contents[pg[1]:pg[1] + pg[2]] = content[offset:offset+pg[2]]
            offset += pg[2]

    def extend_heap(self, size):
        page_size = PVMMemory.page_size(size)
        if self._heap.address + page_size >= self._stack.address:
            raise PVMMemoryError("Heap overflow")

        old_heap = self._heap.contents
        new_heap = np.zeros(page_size, dtype=np.uint8)
        old_size = len(old_heap)
        if old_size > size:
            old_size = size

        new_heap[:old_size] = old_heap[:old_size]
        self._heap.contents = new_heap

        self._heap.length = page_size
        self._heap.break_pointer = size

        return page_size

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

    """
    GP-0.6.2-eq:A.40 | Initializing of memory pages
    """
    @staticmethod
    def init_memory(
            rom: bytes,
            ram: bytes,
            arguments: bytes,
            heap_mem_size: int,
            stack_mem_size: int
    ) -> PVMMemory:

        _rom = MemoryPage(
            address=PVM_INIT_ZONE_SIZE,
            length=PVMMemory.page_size(min(len(rom),1)),
            writable=False,
            contents=rom
        )

        # TODO: add sanity check on heap_mem_size
        heap = MemoryPage(
            address=2 * PVM_INIT_ZONE_SIZE + PVMMemory.zone_size(len(rom)),
            length=PVMMemory.page_size(len(ram)) + heap_mem_size,
            writable=True,
            contents=ram
        )

        #TODO: add sanity check on stack_mem_size
        stack = MemoryPage(
            address=2 ** 32 - 2 * PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE - PVMMemory.page_size(stack_mem_size),
            length=PVMMemory.page_size(stack_mem_size),
            writable=True,
            contents=bytes(PVMMemory.page_size(stack_mem_size)),
        )

        arguments = MemoryPage(
            address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
            length=len(arguments),
            writable=False,
            contents=arguments,
        )

        return PVMMemory(rom=_rom, heap=heap, stack=stack, arguments=arguments)


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
    def from_serialized_bytes(cls, serialized_program: bytes, arguments: bytes) -> Optional['PVMProgram']:
        """
        GP-0.6.2-eq:A.35 (Y)
        """
        try:
            jam_bytes = JamBytes(serialized_program)

            # GP?? |o|
            pvm_rom_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? |w|
            pvm_ram_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? z
            stack_mem_pages = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
            # GP?? s
            stack_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP?? o
            pvm_rom = jam_bytes.get_next_bytes(pvm_rom_size)
            # GP?? w
            pvm_ram = jam_bytes.get_next_bytes(pvm_ram_size)

            pvm_code_size = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
            pvm_code = jam_bytes.get_next_bytes(pvm_code_size)

            if (5 * PVM_INIT_ZONE_SIZE +
                PVMMemory.zone_size(pvm_rom_size) +
                PVMMemory.zone_size(pvm_ram_size + stack_mem_pages * PVM_PAGE_SIZE) +
                PVMMemory.zone_size(stack_mem_size) + PVM_INPUT_DATA_SIZE
            ) <= 2**32:

                return cls(
                    code=PVMCode.from_jam_bytes(JamBytes(pvm_code)),
                    registers=cls.init_registers(arguments),
                    memory=cls.init_memory(pvm_rom, pvm_ram, arguments, stack_mem_pages, stack_mem_size),
                )
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
        data = bytes()

        # GP?? |o|
        data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
        # GP?? |w|
        data += len(self.memory._ram.contents).to_bytes(length=3, byteorder='little')
        # GP?? z
        data += int(1).to_bytes(length=2, byteorder='little')
        # GP?? s
        data += len(self.memory._stack.contents).to_bytes(length=3, byteorder='little')

        # GP?? o
        data += len(self.memory._rom.contents).to_bytes(length=3, byteorder='little')
        # GP?? w
        data += len(self.memory._ram.contents).to_bytes(length=3, byteorder='little')

        code_bytes = self.code.to_jam_bytes().to_bytes()
        data += int(len(code_bytes)).to_bytes(length=4, byteorder='little')
        data += code_bytes

        return data


    @classmethod
    def initialize(cls, pvm_code: bytes) -> 'PVMProgram':
        pass
