import math
import numpy as np

from pyjamaz.graypaper_constants import PVM_PAGE_SIZE
from pyjamaz.pvm.exceptions import UIntValueError
from pyjamaz.pvm.interpreters.graypaper.defs import u8, u16, u32, u64
from pyjamaz.pvm.memory_section_abstract import AbstractMemorySection


class MemorySection(AbstractMemorySection):

    def __init__(self, address, size, contents, acl=None):
        self._acl = {}
        super().__init__(address, size=size, contents=contents, acl=acl)


    def alloc_contents(self, _bytes):
        self.contents = bytearray(self.size)
        self.contents[0: len(_bytes)] = _bytes


    def alloc_acl(self, acl_mode: int, paged_size: int):
        nr_pages = math.ceil(paged_size / PVM_PAGE_SIZE)
        self._acl.update({n: acl_mode for n in range(nr_pages)})


    def set_content(self, content:bytes, start: int, end: int) -> int:
        self.contents[start:end] = content


    def read_uint(self, mem: bytearray, addr: int, n: int) -> np.uint64:
        if n == 0:
            return u64(0)

        elif n == 1:
            return u64(self.contents[addr + 0]) % 2**8

        elif n == 2:
            byte0 = u8(self.contents[addr + 0])
            byte1 = u16(self.contents[addr + 1])
            return u64((byte1 << 8) + byte0) % 2**16

        elif n == 3:
            byte0 = u8(self.contents[addr + 0])
            byte1 = u16(self.contents[addr + 1])
            byte2 = u32(self.contents[addr + 2])
            return u64((byte2 << 16) + (byte1 << 8) + byte0) % 2 ** 32

        elif n == 4:
            byte0 = u8(self.contents[addr + 0])
            byte1 = u16(self.contents[addr + 1])
            byte2 = u32(self.contents[addr + 2])
            byte3 = u32(self.contents[addr + 3])
            return u64(
                (byte3 << 24) +
                (byte2 << 16) +
                (byte1 << 8) +
                byte0
            ) % 2**32

        elif n == 8:
            byte0 = u8(self.contents[addr + 0])
            byte1 = u16(self.contents[addr + 1])
            byte2 = u32(self.contents[addr + 2])
            byte3 = u32(self.contents[addr + 3])
            byte4 = u64(self.contents[addr + 4])
            byte5 = u64(self.contents[addr + 5])
            byte6 = u64(self.contents[addr + 6])
            byte7 = u64(self.contents[addr + 7])
            return u64(
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
            raise UIntValueError(f"Invalid uint length: {n}")


    def write_uint(self, mem: bytearray, addr: int, n: int, value: int):
        if n == 1:
            self.contents[addr + 0] = u8(value & 0xFF)
        elif n == 2:
            self.contents[addr + 0] = u8(value & 0x00FF)
            self.contents[addr + 1] = u8((value & 0xFF00) >> 8)
        elif n == 4:
            self.contents[addr + 0] = u8(value & 0x000000FF)
            self.contents[addr + 1] = u8((value & 0x0000FF00) >> 8)
            self.contents[addr + 2] = u8((value & 0x00FF0000) >> 16)
            self.contents[addr + 3] = u8((value & 0xFF000000) >> 24)
        elif n == 8:
            self.contents[addr + 0] = u8(value & 0x00000000000000FF)
            self.contents[addr + 1] = u8((value & 0x000000000000FF00) >> 8)
            self.contents[addr + 2] = u8((value & 0x0000000000FF0000) >> 16)
            self.contents[addr + 3] = u8((value & 0x00000000FF000000) >> 24)
            self.contents[addr + 4] = u8((value & 0x000000FF00000000) >> 32)
            self.contents[addr + 5] = u8((value & 0x0000FF0000000000) >> 40)
            self.contents[addr + 6] = u8((value & 0x00FF000000000000) >> 48)
            self.contents[addr + 7] = u8((value & 0xFF00000000000000) >> 56)
        else:
            raise UIntValueError(f"Invalid uint length: {n}")


    def acl_check(self, section_addr: int, nr_bytes: int, required_acl: int) -> bool:
        start_page = section_addr // PVM_PAGE_SIZE
        end_page = (section_addr + nr_bytes) // PVM_PAGE_SIZE

        if start_page == end_page and (not start_page in self._acl or self._acl[start_page] < required_acl):
            return False
        else:
            nr_pages = end_page - start_page + 1
            for page_nr in range(nr_pages):
                if start_page + page_nr not in self._acl or self._acl[start_page + page_nr] < required_acl:
                    return False

        return True


    def acl_set_pages(self, start_page: int, nr_pages: int, acl_level: int):
        for page_nr in range(nr_pages):
            self._acl[start_page + page_nr] = acl_level
