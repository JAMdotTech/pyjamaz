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


@dataclass
class AbstractMemorySection:
    address: int    # The absolute memory address of this memory section
    size: int # Note: The (theoretical) max size of this section
    paged_tail: int # Note: the address of the last written index for this section
    contents: bytearray # Bytes for this section (note: actual type depends on PVM implementation)
    acl: Optional[np.uint64]  # Default Access Control for this section
    acl_bitmap: npt.NDArray[np.uint64]  # Bitmask for per page ACL control

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
            acl_size = max(1, paged_size // PVM_PAGE_SIZE)
            self.acl_bitmap = np.zeros(acl_size, dtype=np.uint64)
            self.set_range_acl(0, acl_size, acl)
        else:
            self.acl_bitmap = np.zeros(max(1, paged_size // PVM_PAGE_SIZE), dtype=np.uint64)


    def alloc_contents(self, _bytes):
        # self.contents = np.zeros(self.size, dtype=np.uint8)
        # if _bytes:
        #     length = len(_bytes)
        #     if isinstance(_bytes, (list, tuple)):
        #         self.contents[0:length] = np.array(_bytes, dtype=np.uint8)
        #     elif isinstance(_bytes, np.ndarray):
        #         self.contents[0:length] = _bytes.astype(np.uint8)
        #     else:
        #         self.contents[0:length] = np.frombuffer(bytes(_bytes), dtype=np.uint8)
        raise Exception("implement in pvm")

    def set_content(self, content:bytes, start: int, end: int) -> int:
        #section.contents[start:end] = np.frombuffer(content, dtype=np.uint8)  numba
        #section.contents[start:end] = content  cpython
        raise Exception("implement in pvm")

    def read_uint(self, section: bytearray, addr: int, length: int) -> int:
        raise Exception("implement in pvm")

    def write_uint(section: bytearray, section_offset: int, bytes_to_write: int, value: int):
        raise Exception("implement in pvm")

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

    def set_page_acl(self, page_idx: int, perm: int) -> None:
        bitmap_idx = acl_bitmap_idx(page_idx)
        if bitmap_idx >= len(self.acl_bitmap):
            new_len = bitmap_idx + 1
            extended = np.zeros(new_len, dtype=np.uint64)
            extended[:len(self.acl_bitmap)] = self.acl_bitmap
            self.acl_bitmap = extended
        shift = acl_page_idx(page_idx)
        mask = np.uint64(0b11 << shift)
        bits = np.uint64(acl_bits(perm) << shift)
        self.acl_bitmap[bitmap_idx] = np.uint64((self.acl_bitmap[bitmap_idx] & ~mask) | bits)

    def set_range_acl(self, start_page: int, nr_pages: int, acl: int) -> None:
        if nr_pages <= 0:
            return
        for page in range(start_page, start_page + nr_pages):
            self.set_page_acl(page, acl)

    def check_acl(self, start_page: int, nr_pages: int, required_bits: int) -> bool:
        if nr_pages <= 0:
            return True

        end_page = start_page + nr_pages
        page = start_page

        while page < end_page:
            bitmap_idx = acl_bitmap_idx(page)
            bitmap = int(self.acl_bitmap[bitmap_idx]) if bitmap_idx < len(self.acl_bitmap) else 0
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
