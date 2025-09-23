# Note: this class should be subclassed by a PVM specific implementation for its abstract methods

import logging

from abc import ABC, abstractmethod

from math import ceil
from dataclasses import dataclass

from pyjamaz.pvm.constants import PVM_PAGE_SIZE
from pyjamaz.pvm.exceptions import PVMMemoryError


def page_size(bytes: int) -> int:
    """
    GP-0.6.2-eq:A.38 (P)
    """
    return PVM_PAGE_SIZE * ceil(bytes / PVM_PAGE_SIZE)


@dataclass
class AbstractMemorySection(ABC):
    address: int    # The absolute memory address of this memory section
    size: int # Note: The (theoretical) max size of this section
    paged_tail: int # Note: the address of the last written index for this section
    contents: bytearray # Bytes for this section (note: actual type depends on PVM implementation)
    acl: int  # Default Access Control for this section  (note: actual type depends on PVM implementation)

    @abstractmethod
    def alloc_contents(self, _bytes): ...

    @abstractmethod
    def alloc_acl(self, acl_mode: int, page_size: int): ...

    @abstractmethod
    def set_content(self, content:bytes, start: int, end: int) -> int: ...

    @abstractmethod
    def read_uint(self, section: bytearray, addr: int, length: int) -> int: ...

    @abstractmethod
    def write_uint(section: bytearray, section_offset: int, bytes_to_write: int, value: int): ...

    @abstractmethod
    def acl_check(self, start_page: int, nr_pages: int, required_acl: int) -> bool: ...

    @abstractmethod
    def acl_set_pages(self, start_page: int, nr_pages: int, required_acl: int): ...


    def __init__(self, address, size, contents, acl=None):
        if not contents:
            contents = []

        # if size > settings.PVM_MAX_HEAP_SIZE:
        #     raise PVMMemoryError(f"Memory size too large: {size} > {settings.PVM_MAX_HEAP_SIZE}")

        self.acl:int = acl
        self.address:int = address
        self.size:int = page_size(size)

        # Note: actual implementation depends on PVM implementation
        self.alloc_contents(contents)

        paged_size = page_size(len(contents))
        self.paged_tail = address + paged_size

        # Note: actual implementation depends on PVM implementation
        self.alloc_acl(acl, paged_size)


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
