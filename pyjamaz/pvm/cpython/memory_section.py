import struct

from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.memory_section_abstract import AbstractMemorySection


class MemorySection(AbstractMemorySection):

    def alloc_contents(self, _bytes):
        self.contents = bytearray(self.size)
        self.contents[0: len(_bytes)] = _bytes

    def set_content(self, content:bytes, start: int, end: int) -> int:
        self.contents[start:end] = content

    def read_uint(self, mem: bytearray, addr: int, n: int) -> int:
        if n == 0:
            return 0 & 0xFF
        if n == 1:
            return mem[addr]
        elif n == 2:
            return struct.unpack_from('<H', mem, addr)[0]
        elif n == 4:
            return struct.unpack_from('<I', mem, addr)[0]
        elif n == 8:
            return struct.unpack_from('<Q', mem, addr)[0]
        elif n == 3:
            # Safely read 3 bytes without requiring 4-byte availability
            lo = struct.unpack_from('<H', mem, addr)[0]
            hi = struct.unpack_from('<B', mem, addr + 2)[0]
            return lo | (hi << 16)

        raise PVMMemoryError("read_uint: unsupported length")

    def write_uint(self, mem: bytearray, addr: int, n: int, value: int):
        if n == 1:
            mem[addr] = value & 0xFF
        elif n == 2:
            struct.pack_into('<H', mem, addr, value)
        elif n == 4:
            struct.pack_into('<I', mem, addr, value)
        elif n == 8:
            struct.pack_into('<Q', mem, addr, value)
        else:
            raise PVMMemoryError(f"Invalid write length: {n}")
