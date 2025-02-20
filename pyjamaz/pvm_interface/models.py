from dataclasses import dataclass
from typing import List

from jamcodec.base import JamBytes
from jamcodec.mixins import Serializable
from jamcodec.types import U64, Array


@dataclass
class JamProgram(Serializable):
    # c
    pvm_code: bytes
    # ω
    pvm_registers: List[int]
    # µ
    pvm_memory: bytes

    @classmethod
    def from_serialized_bytes(cls, serialized_bytes: bytes) -> 'JamProgram':

        jam_bytes = JamBytes(serialized_bytes)

        # GP?? o
        readonly_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
        # GP?? w
        read_write_heap_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
        # GP?? z
        stack_mem_pages = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
        # GP?? s
        stack_mem_size = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')

        pvm_mem_r = jam_bytes.get_next_bytes(readonly_mem_size)
        pvm_mem_w = jam_bytes.get_next_bytes(read_write_heap_size)
        pvm_code_size = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
        pvm_code = jam_bytes.get_next_bytes(pvm_code_size)

        return cls(
            pvm_code=pvm_code,
            pvm_mem_r=?????
            pvm_mem_w=?????
            pvm_mem_s_count=?????
            pvm_mem_s_size=?????
        )

