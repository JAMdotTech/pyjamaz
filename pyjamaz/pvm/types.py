import logging

from abc import ABC, abstractmethod
from functools import lru_cache
from math import ceil
from dataclasses import dataclass, field
from typing import List, Union, Type, T, Optional, Sequence

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.mixins import Serializable
from jamcodec.types import VarInt64, Array, U8 as JU8, BitArray, UnsignedInteger, Bytes

from pyjamaz import settings

from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.exceptions import PVMMemoryError


def page_size(bytes: int) -> int:
    """
    GP-0.6.2-eq:A.38 (P)
    """
    return PVM_PAGE_SIZE * ceil(bytes / PVM_PAGE_SIZE)


# Shared page-based memory constants
ADDR_MOD = 2**32
PAGE_SIZE = PVM_PAGE_SIZE
_PAGE_SHIFT = PAGE_SIZE.bit_length() - 1
_PAGE_MASK = PAGE_SIZE - 1
_ADDR_MASK = ADDR_MOD - 1
_MAX_PAGE_IDX = (ADDR_MOD // PAGE_SIZE) - 1
_PAGE_CACHE_LIMIT = 16
_ZERO_PAGE = bytes(PAGE_SIZE)
_PVM_CODE_CACHE_LIMIT = 64


@dataclass
class AbstractMemorySection(ABC):
    address: int
    size: int
    paged_tail: int
    contents: bytearray
    acl: int

    def __init__(self, address, size, contents, acl=None):
        if not contents:
            contents = []

        if size > settings.PVM_MAX_HEAP_SIZE:
            raise PVMMemoryError(f"Memory size too large: {size} > {settings.PVM_MAX_HEAP_SIZE}")

        self.acl: int = acl
        self.address: int = address
        self.size: int = page_size(size)

        self.alloc_contents(contents)

        paged_size = page_size(len(contents))
        self.paged_tail = address + paged_size

        self.alloc_acl(acl, paged_size)

    def read_int(self, section_addr: int, length: int) -> int:
        if section_addr + length > self.size:
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        return self.read_uint(self.contents, section_addr, length)

    def write_int(self, section_addr: int, value: int, length: int):
        if section_addr + length > self.size:
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        return self.write_uint(self.contents, section_addr, length, value)

    @abstractmethod
    def alloc_contents(self, _bytes): ...

    @abstractmethod
    def alloc_acl(self, acl_mode: int, page_size: int): ...

    @abstractmethod
    def set_content(self, content: bytes, start: int, end: int) -> int: ...

    @abstractmethod
    def read_uint(self, section: bytearray, addr: int, length: int) -> int: ...

    @abstractmethod
    def write_uint(section: bytearray, section_offset: int, bytes_to_write: int, value: int): ...

    @abstractmethod
    def acl_check(self, start_page: int, nr_pages: int, required_acl: int) -> bool: ...

    @abstractmethod
    def acl_set_pages(self, start_page: int, nr_pages: int, required_acl: int): ...

    @abstractmethod
    def acl_check_pages(self, section_addr: int, length: int, required_acl: int) -> int:
        """
        Checks if pages pass the ACL check, if not, return first failing page.

        Returns:
            Page number of the first failing page, or -1 if all pages pass.
        """
        ...


class AbstractMemory(ABC):
    SIZE: int = 2**32
    _mem_addr: int
    heap_base: Optional[int]
    stack_base: Optional[int]
    heap_ptr: int

    @abstractmethod
    def __init__(
        self,
        rom: Optional[AbstractMemorySection] = None,
        heap: Optional[AbstractMemorySection] = None,
        stack: Optional[AbstractMemorySection] = None,
        arguments: Optional[AbstractMemorySection] = None,
        logger=None,
    ):
        ...

    @staticmethod
    def zone_size(items: int) -> int:
        """
        GP-0.6.2-eq:A.38 (Z)
        """
        return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)

    @abstractmethod
    def add_segment(self, address: int, size: int, acl: int, contents: bytes = b"") -> None: ...

    @abstractmethod
    def load_section(self, section: AbstractMemorySection) -> None: ...

    @abstractmethod
    def read_bytes(self, address: int, length: int, padding: int = None) -> bytes: ...

    @abstractmethod
    def write_bytes(self, address: int, content: Union[bytes, Sequence[int]]) -> None: ...

    @abstractmethod
    def read_int(self, addr: int, length: int) -> int: ...

    @abstractmethod
    def write_int(self, addr: int, value: int, length: int): ...

    @abstractmethod
    def is_accessible(self, address: int, length: int, mode: int) -> bool: ...

    @abstractmethod
    def zero(self, page_idx: int, nr_pages: int, acl: int): ...

    @abstractmethod
    def void(self, page_idx: int, nr_pages: int, acl: int): ...

    @abstractmethod
    def change_acl(self, page_idx: int, nr_pages: int, acl: int): ...

    @abstractmethod
    def is_null(self, page_idx: int, nr_pages: int) -> bool: ...


@dataclass
class PVMCode(Serializable):
    # GP-6.4:eq:A.2 (deblob)
    jump_table_entry_count: int = field(metadata={'codec': VarInt64})
    jump_table_entry_size: int = field(metadata={'codec': JU8})
    code_length: int = field(metadata={'codec': VarInt64})
    jump_table: List[int] = field(metadata={'codec': Array(JU8, 0)})
    code: bytes = field(metadata={'codec': Array(JU8, 0)})
    opcode_bitmask: List[bool] = field(metadata={'codec': BitArray(0)})

    @classmethod
    def from_jam_bytes(cls, scale_bytes: JamBytes, strict_decoding=True) -> 'PVMCode':
        jump_table_entry_count = VarInt64.decode(scale_bytes)
        jump_table_entry_size = JU8.decode(scale_bytes)
        code_length = VarInt64.decode(scale_bytes)

        jump_table = Array(UnsignedInteger(jump_table_entry_size * 8), jump_table_entry_count).decode(scale_bytes)
        code = Array(JU8, code_length).decode(scale_bytes)
        opcode_bitmask = BitArray(code_length, strict_decoding=strict_decoding).decode(scale_bytes)

        return cls(
            jump_table_entry_count=jump_table_entry_count,
            jump_table_entry_size=jump_table_entry_size,
            code_length=code_length,
            jump_table=jump_table,
            code=code,
            opcode_bitmask=opcode_bitmask,
        )

    @classmethod
    def from_bytes_cached(cls, data) -> "PVMCode":
        if not isinstance(data, bytes):
            data = bytes(data)
        return _pvm_code_from_bytes_cached(data)

    def to_codec_type(self) -> JamCodecType:
        codec_def = self.to_codec_def()
        # Change definition according to data
        codec_def.arguments['jump_table'] = Array(
            UnsignedInteger(self.jump_table_entry_size * 8), self.jump_table_entry_count
        )
        codec_def.arguments['code'] = Array(JU8, self.code_length)
        codec_def.arguments['opcode_bitmask'] = BitArray(self.code_length)

        scale_type = codec_def.new()
        scale_type.deserialize(self)

        return scale_type

    @classmethod
    def deserialize(cls: Type[T], data: Union[str, int, float, bool, dict, list]) -> T:
        return cls.from_jam_bytes(JamBytes(bytes(data)))

    def serialize(self) -> List[int]:
        return [b for b in self.to_jam_bytes().to_bytes()]


@lru_cache(maxsize=_PVM_CODE_CACHE_LIMIT)
def _pvm_code_from_bytes_cached(data: bytes) -> PVMCode:
    return PVMCode.from_jam_bytes(JamBytes(data))


@dataclass
class PVMProgram(Serializable):
    """

    """
    # c
    code: PVMCode
    # ω
    registers: List[int]
    # µ
    memory: AbstractMemory

    name: str = ''

    """
    GP-0.7.2-eq:A.42 | Initializing of memory pages
    """

    @staticmethod
    def init_memory(
            rom_contents: bytes,
            heap_contents: bytes,
            argument_contents: bytes,
            heap_mem_pages: int,
            stack_mem_size: int
    ) -> "AbstractMemory":
        # Note: Import lazily to avoid module initialization cycles.
        from pyjamaz.pvm import PVMInterpreter, PVMMemory

        rom_start = PVM_INIT_ZONE_SIZE
        rom_size = page_size(len(rom_contents))

        # If PVM_MIN_HEAP_SIZE is set, we preallocate at least that size to (hopefully) prevent lots of memory allocations...
        heap_mem_size = max(page_size(settings.PVM_MIN_HEAP_SIZE), page_size(len(heap_contents)) + heap_mem_pages * PVM_PAGE_SIZE)
        heap_start = (2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(rom_contents))

        stack_size = page_size(stack_mem_size)
        stack_start = 2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - stack_size

        args_start = 2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
        args_size = page_size(len(argument_contents))

        return PVMInterpreter.alloc_memory(
            rom_start=rom_start,
            rom_size=rom_size,
            rom_contents=rom_contents,
            heap_start=heap_start,
            heap_size=heap_mem_size,
            heap_contents=heap_contents,
            stack_start=stack_start,
            stack_size=stack_size,
            argument_start=args_start,
            argument_size=args_size,
            argument_contents=argument_contents,
        )

    @staticmethod
    def init_registers(arguments: bytes) -> List[int]:
        """
        GP-0.7.2-eq:A.43
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
        GP-0.7.2-eq:A.37 (function_Y)
        """
        from pyjamaz.pvm import PVMMemory

        # GP-0.7.2-eq:A.41
        if len(argument_contents) > PVM_INPUT_DATA_SIZE:
            return None

        try:

            jam_bytes = JamBytes(serialized_program)

            if settings.DEBUG:
                override_heap_mem_pages = None
                if name in settings.DEBUG_PROGRAM_OVERRIDE:
                    with open(settings.DEBUG_PROGRAM_OVERRIDE.get(name)['file'], 'rb') as fp:
                        jam_bytes = JamBytes(fp.read())
                        override_heap_mem_pages = settings.DEBUG_PROGRAM_OVERRIDE.get(name)['heap_mem_pages']

                        metadata = Bytes.decode(jam_bytes)

            # GP-0.7.2-eq:A.38 (|o|)
            pvm_rom_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP-0.7.2-eq:A.38 (|w|)
            pvm_heap_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP-0.7.2-eq:A.38 (z)
            heap_mem_pages = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
            # GP-0.7.2-eq:A.38 (s)
            stack_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
            # GP-0.7.2-eq:A.38 (o)
            pvm_rom_contents = jam_bytes.get_next_bytes(pvm_rom_size)
            # GP-0.7.2-eq:A.38 (w)
            pvm_heap_contents = jam_bytes.get_next_bytes(pvm_heap_size)

            pvm_code_size = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
            pvm_code = jam_bytes.get_next_bytes(pvm_code_size)

            if settings.DEBUG and override_heap_mem_pages:
                heap_mem_pages = override_heap_mem_pages

            # GP-0.7.2-eq:A.42
            if (5 * PVM_INIT_ZONE_SIZE +
                PVMMemory.zone_size(pvm_rom_size) +
                PVMMemory.zone_size(pvm_heap_size + heap_mem_pages * PVM_PAGE_SIZE) +
                PVMMemory.zone_size(stack_mem_size) + PVM_INPUT_DATA_SIZE
            ) <= 2**32:

                instance = cls(
                    code=PVMCode.from_bytes_cached(pvm_code),
                    registers=cls.init_registers(argument_contents),
                    memory=cls.init_memory(pvm_rom_contents, pvm_heap_contents, argument_contents, heap_mem_pages, stack_mem_size),
                    name=name
                )

                #TODO: TEMP HACK TO DEBUG INJECT CUSTOM PROGRAMS!!!!!!!
                if settings.DEBUG:
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
        GP-0.7.2-eq:A.37 (Y)
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
