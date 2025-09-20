# Note: this class should be subclassed by a PVM specific implementation for its abstract methods

import logging

import numpy as np
import numpy.typing as npt

from math import ceil
from dataclasses import dataclass
from typing import Optional

from pyjamaz.pvm.constants import PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE, MEM_I, MEM_R, ACL_READ_BIT, MEM_W, MEM_RW, \
    ACL_WRITE_BIT, ACL_PAGES_PER_BITMAP, ACL_BITS_PER_PAGE
from pyjamaz.pvm.exceptions import PVMMemoryError


def page_size(bytes: int) -> int:
    """
    GP-0.6.2-eq:A.38 (P)
    """
    return PVM_PAGE_SIZE * ceil(bytes / PVM_PAGE_SIZE)


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


def check_acl(acl_bitmap, start_page: int, nr_pages: int, required_bits: int) -> bool:
    if nr_pages <= 0:
        return False

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


@dataclass
class AbstractMemorySection:
    address: int    # The absolute memory address of this memory section
    size: int # Note: The (theoretical) max size of this section
    paged_tail: int # Note: the address of the last written index for this section
    contents: bytearray # Bytes for this section (note: actual type depends on PVM implementation)
    acl: Optional[np.uint64]  # Default Access Control for this section
    acl_bitmap: npt.NDArray[np.uint64]  # Bitmask for per page ACL control


    def alloc_contents(self, _bytes):
        raise Exception("implement in pvm")

    def set_content(self, content:bytes, start: int, end: int) -> int:
        raise Exception("implement in pvm")

    def read_uint(self, section: bytearray, addr: int, length: int) -> int:
        raise Exception("implement in pvm")

    def write_uint(section: bytearray, section_offset: int, bytes_to_write: int, value: int):
        raise Exception("implement in pvm")


    def __init__(self, address, size, contents, acl=None):
        if not contents:
            contents = []

        # if size > settings.PVM_MAX_HEAP_SIZE:
        #     raise PVMMemoryError(f"Memory size too large: {size} > {settings.PVM_MAX_HEAP_SIZE}")

        self.acl = acl
        self.address:int = address
        self.size:int = page_size(size)

        # Note: actual implementation depends on PVM implementation
        self.alloc_contents(contents)

        paged_size = page_size(len(contents))
        self.paged_tail = address + paged_size

        if acl is not None:
            nr_pages = paged_size // PVM_PAGE_SIZE
            acl_size = max(1, (nr_pages + ACL_PAGES_PER_BITMAP - 1) // ACL_PAGES_PER_BITMAP)
            self.acl_bitmap = np.zeros(acl_size, dtype=np.uint64)
            set_range_acl(self.acl_bitmap, 0, nr_pages, acl)
        else:
            nr_pages = paged_size // PVM_PAGE_SIZE
            self.acl_bitmap = np.zeros(max(1, (nr_pages + ACL_PAGES_PER_BITMAP - 1) // ACL_PAGES_PER_BITMAP), dtype=np.uint64)

    def contains(self, addr):
        return self.address <= addr < self.address + self.size

    def read_int(self, section_addr: int, length: int) -> int:
        if section_addr + length > (self.paged_tail - self.address):  # len(section):
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        return self.read_uint(self.contents, section_addr, length)

    def write_int(self, section_addr: int, value: int, length: int):

        if section_addr + length > (self.paged_tail - self.address):  # len(section):
            msg = f"MemorySection {self.address + section_addr} overflow: {length} (tail: {self.paged_tail} - size: {self.size})"
            logging.error(msg)
            raise PVMMemoryError(msg)

        return self.write_uint(self.contents, section_addr, length, value)
