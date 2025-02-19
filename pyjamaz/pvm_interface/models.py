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

        registers_count = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
        memory_count = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
        z = int.from_bytes(jam_bytes.get_next_bytes(2), byteorder='little')
        s = int.from_bytes(jam_bytes.get_next_bytes(3), byteorder='little')
        pvm_registers = jam_bytes.get_next_bytes(registers_count) #Array(U64, registers_count).decode(jam_bytes)
        pvm_memory = jam_bytes.get_next_bytes(memory_count)
        code_count = int.from_bytes(jam_bytes.get_next_bytes(4), byteorder='little')
        pvm_code = jam_bytes.get_next_bytes(code_count)

        return cls(
            pvm_code=pvm_code,
            pvm_registers=pvm_registers,
            pvm_memory=pvm_memory
        )

