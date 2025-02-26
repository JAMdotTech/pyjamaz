from dataclasses import dataclass, field
from typing import List, Union, Type, T, Optional

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.mixins import Serializable
from jamcodec.types import VarInt64, Array, U8, BitArray, UnsignedInteger
from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.utils import memory_zone_size, memory_page_size


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
    writable: bool
    contents: bytes

@dataclass
class PVMMemory:
    pages: List[MemoryPage]

    def read(self, address: int, length: int) -> bytes:
        pass

    def write(self, address: int, value: bytes):
        pass

@dataclass
class PVMProgram(Serializable):
    """

    """
    # c
    code: bytes
    # ω
    registers: List[int]
    # µ
    memory: PVMMemory

    @staticmethod
    def init_memory(
            rom: bytes, ram: bytes, arguments: bytes, stack_mem_pages: int, stack_mem_size: int
    ) -> PVMMemory:
        """
        GP-0.6.2-eq:A.40 | Initializing of memory pages

        """
        memory = PVMMemory(pages=[])

        memory.pages.append(MemoryPage(
            address=PVM_INIT_ZONE_SIZE,
            length=len(rom),
            writable=False,
            contents=rom,
        ))
        # TODO create page for buffer overflow protection?
        length = memory_page_size(len(rom)) - len(rom)
        memory.pages.append(MemoryPage(
            address=PVM_INIT_ZONE_SIZE + len(rom),
            length=length,
            writable=False,
            contents=bytes(length)
        ))
        memory.pages.append(MemoryPage(
            address=2*PVM_INIT_ZONE_SIZE + memory_zone_size(len(rom)),
            length=len(ram),
            writable=True,
            contents=ram,
        ))
        length = memory_page_size(len(ram)) - len(ram) + stack_mem_pages * PVM_PAGE_SIZE
        if length > 0:
            memory.pages.append(
                MemoryPage(
                    address=2 * PVM_INIT_ZONE_SIZE + memory_zone_size(len(rom)) + len(ram),
                    length=length,
                    writable=True,
                    contents=bytes(length),
                )
            )

        memory.pages.append(
            MemoryPage(
                address=2**32 - 2 * PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE - memory_page_size(stack_mem_size),
                length=memory_page_size(stack_mem_size),
                writable=True,
                contents=bytes(memory_page_size(stack_mem_size)),
            )
        )
        memory.pages.append(
            MemoryPage(
                address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
                length=len(arguments),
                writable=False,
                contents=arguments,
            )
        )
        if len(arguments) > 0:
            memory.pages.append(
                MemoryPage(
                    address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE + len(arguments),
                    length=memory_page_size(len(arguments)) - len(arguments),
                    writable=False,
                    contents=bytes(memory_page_size(len(arguments)) - len(arguments)),
                )
            )


        return memory

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
                memory_zone_size(pvm_rom_size) +
                memory_zone_size(pvm_ram_size + stack_mem_pages * PVM_PAGE_SIZE) +
                memory_zone_size(stack_mem_size) + PVM_INPUT_DATA_SIZE
            ) <= 2**32:

                return cls(
                    code=pvm_code,
                    registers=cls.init_registers(arguments),
                    memory=cls.init_memory(pvm_rom, pvm_ram, arguments, stack_mem_pages, stack_mem_size),
                )
        except RemainingScaleBytesNotEmptyException as e: # TODO deserialize exception
            pass

        return None

    @classmethod
    def initialize(cls, pvm_code: bytes) -> 'PVMProgram':
        pass
