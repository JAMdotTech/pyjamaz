import logging

import numpy as np
import numpy.typing as npt

from math import ceil
from dataclasses import dataclass, field
from typing import List, Union, Type, T, Optional

from jamcodec.base import JamBytes, JamCodecType
from jamcodec.exceptions import RemainingScaleBytesNotEmptyException
from jamcodec.mixins import Serializable
from jamcodec.types import VarInt64, Array, U8 as JU8, BitArray, UnsignedInteger, Bytes

from pyjamaz import settings
from pyjamaz.pvm import MemorySection
from pyjamaz.pvm.memory import PVMMemory
from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE, MEM_R, MEM_W
from pyjamaz.settings import DEBUG, DEBUG_PROGRAM_OVERRIDE


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
            size=PVMMemory.page_size(len(rom_contents)),
            contents=rom_contents,
            acl=MEM_R
        )

        # If PVM_MIN_HEAP_SIZE is set, we preallocate at least that size to (hopefully) prevent lots of memory allocations...
        heap_mem_size = max(PVMMemory.page_size(settings.PVM_MIN_HEAP_SIZE), PVMMemory.page_size(len(heap_contents)) + heap_mem_pages * PVM_PAGE_SIZE)
        _heap = MemorySection(
            address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(len(rom_contents)),
            size=heap_mem_size,
            contents=heap_contents,
            acl=MEM_W
        )

        _stack = MemorySection(
            address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - PVMMemory.page_size(stack_mem_size),
            size=PVMMemory.page_size(stack_mem_size),
            contents=bytes(PVMMemory.page_size(stack_mem_size)),    #TODO: hoeft niet dubbel hier
            acl=MEM_W
        )

        _arguments = MemorySection(
            address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
            size=PVMMemory.page_size(len(argument_contents)),
            contents=argument_contents,
            acl=MEM_R
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
