import struct

import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.types import AbstractMemorySection

from pyjamaz.pvm.constants import PVM_PAGE_SIZE, MEM_I, MEM_R, MEM_W, MEM_RW

# Note: these memory segment helpers are defined outside MemorySection, so we can refer to them from code not using
#       associated object types

ACL_PAGES_PER_BITMAP = 32
ACL_BITS_PER_PAGE = 2
ACL_READ_BIT = 0b01
ACL_WRITE_BIT = 0b10

ACL_BITMAP_READ  = 0b0101010101010101010101010101010101010101010101010101010101010101
ACL_BITMAP_WRITE = 0b0111111111111111111111111111111111111111111111111111111111111111


def acl_bits(perm: int) -> int:
    if perm == MEM_I:
        return 0
    if perm == MEM_R:
        return ACL_READ_BIT
    if perm in (MEM_W, MEM_RW):
        return ACL_READ_BIT | ACL_WRITE_BIT
    return 0


def acl_bitmap_idx(page: int) -> int:
    return page // ACL_PAGES_PER_BITMAP


def acl_page_idx(page: int) -> int:
    return (ACL_PAGES_PER_BITMAP - 1 - (page % ACL_PAGES_PER_BITMAP)) * ACL_BITS_PER_PAGE


def set_page_acl(acl_bitmap, page_idx: int, acl: int) -> None:
    bitmap_idx = acl_bitmap_idx(page_idx)
    if bitmap_idx >= len(acl_bitmap):
        # Note: extending the ACL bitmap should only occur when we extend the heap (sbrk impl)
        raise PVMMemoryError(f'ACL for page {page_idx} is out of range')
    shift = acl_page_idx(page_idx)
    mask = np.uint64(0b11 << shift)
    bits = np.uint64(acl_bits(acl) << shift)
    acl_bitmap[bitmap_idx] = np.uint64((acl_bitmap[bitmap_idx] & ~mask) | bits)


def set_range_acl(acl_bitmap, start_page: int, nr_pages: int, acl: int) -> None:
    if nr_pages <= 0:
        return
    for page in range(start_page, start_page + nr_pages):
        set_page_acl(acl_bitmap, page, acl)


def check_acl(acl_bitmap, start_page: int, nr_pages: int, acl: int) -> bool:
    if nr_pages <= 0:
        return False

    required_bits = acl_bits(acl)

    end_page = start_page + nr_pages
    page = start_page

    while page < end_page:
        bitmap_idx = acl_bitmap_idx(page)
        bitmap = int(acl_bitmap[bitmap_idx]) if bitmap_idx < len(acl_bitmap) else 0
        bitmap_start = bitmap_idx * ACL_PAGES_PER_BITMAP
        bitmap_end = bitmap_start + ACL_PAGES_PER_BITMAP
        sub_end = min(end_page, bitmap_end)
        while page < sub_end:
            shift = acl_page_idx(page)
            bits = (bitmap >> shift) & 0b11
            if (bits & required_bits) != required_bits:
                return False
            page += 1

    return True


class MemorySection(AbstractMemorySection):

    def __init__(self, address, size, contents, acl=None):
        self.acl_bitmap: npt.NDArray[np.uint64] = np.zeros(0, dtype=np.uint64) # Bitmask for per page ACL control
        super().__init__(address, size=size, contents=contents, acl=acl)


    def alloc_contents(self, _bytes):
        self.contents = bytearray(self.size)
        self.contents[0: len(_bytes)] = _bytes


    def alloc_acl(self, acl_mode:int, paged_size:int):
        total_bytes = max(paged_size, self.size)
        # note: ceil div: -(-a // b)
        nr_pages = -(-total_bytes // PVM_PAGE_SIZE)
        acl_size = -(-nr_pages // ACL_PAGES_PER_BITMAP)
        self.acl_bitmap = np.zeros(max(0, acl_size), dtype=np.uint64)
        if acl_size > 0:
            if acl_mode is not None:
                set_range_acl(self.acl_bitmap, 0, nr_pages, acl_mode)


    def set_content(self, content:bytes, start: int, end: int):
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


    def acl_check(self, section_addr: int, length: int, required_acl: int) -> bool:
        if length <= 0:
            return True

        last_offset = section_addr + length - 1
        start_page = section_addr // PVM_PAGE_SIZE
        end_page = last_offset // PVM_PAGE_SIZE
        nr_pages = end_page - start_page + 1

        return check_acl(self.acl_bitmap, start_page, nr_pages, required_acl)


    def acl_set_pages(self, start_page: int, nr_pages: int, acl_level: int):
        set_range_acl(self.acl_bitmap, start_page, nr_pages, acl_level)


    def acl_check_pages(self, section_addr: int, length: int, required_acl: int) -> int:
        # checks if pages pass the ACL check
        if length <= 0:
            return -1

        last_offset = section_addr + length - 1
        start_page = section_addr // PVM_PAGE_SIZE
        end_page = last_offset // PVM_PAGE_SIZE

        required_bits = acl_bits(required_acl)

        for page in range(start_page, end_page + 1):
            bitmap_idx = acl_bitmap_idx(page)
            bitmap = int(self.acl_bitmap[bitmap_idx]) if bitmap_idx < len(self.acl_bitmap) else 0
            shift = acl_page_idx(page)
            bits = (bitmap >> shift) & 0b11
            if (bits & required_bits) != required_bits:
                return page

        return -1
