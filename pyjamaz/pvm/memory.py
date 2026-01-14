import logging

from math import ceil
from dataclasses import dataclass, field
from typing import List, T, Optional

from pyjamaz.pvm import MemorySection
from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, PVM_INPUT_DATA_SIZE, MEM_R, MEM_W, MEM_RW, MEM_I
from pyjamaz.pvm.exceptions import PanicError, PVMMemoryError, PVMError


@dataclass
class PVMMemory:
    sections: List[MemorySection]
    section_offsets: List[int]
    _rom: MemorySection
    _heap: MemorySection
    _stack: MemorySection
    _args: MemorySection
    _mem_addr: int
    _section: MemorySection
    _section_addr: int

    SIZE:int = 2**32

    @classmethod
    def allocate(cls, rom_pages, heap_pages, stack_pages, arg_pages):
        _rom = MemorySection(
            address=PVM_INIT_ZONE_SIZE,
            size=rom_pages * PVM_PAGE_SIZE,
            contents=bytes(rom_pages * PVM_PAGE_SIZE),
            acl=MEM_R
        )
        _heap = MemorySection(
            address=(2 * PVM_INIT_ZONE_SIZE) + PVMMemory.zone_size(_rom.size),
            size=heap_pages * PVM_PAGE_SIZE,
            contents=bytes(heap_pages * PVM_PAGE_SIZE),
            acl=MEM_W
        )
        _stack = MemorySection(
            address=2 ** 32 - (2 * PVM_INIT_ZONE_SIZE) - PVM_INPUT_DATA_SIZE - stack_pages * PVM_PAGE_SIZE,
            size=stack_pages * PVM_PAGE_SIZE,
            contents=bytes(stack_pages * PVM_PAGE_SIZE),
            acl=MEM_W,
        )
        _arguments = MemorySection(
            address=2 ** 32 - PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE,
            size=arg_pages * PVM_PAGE_SIZE,
            contents=bytes(arg_pages * PVM_PAGE_SIZE),
            acl=MEM_R
        )

        return PVMMemory(rom=_rom, heap=_heap, stack=_stack, arguments=_arguments)


    def __init__(
        self,
        rom: MemorySection,
        heap: MemorySection,
        stack: MemorySection,
        arguments: MemorySection
    ):
        # Track all mapped sections so find_section can support arbitrary mappings
        self.sections = []
        for section in (rom, heap, stack, arguments):
            if section:
                self.sections.append(section)

        self._rom = rom
        self._heap = heap
        self._stack = stack
        self._args = arguments

        self._mem_addr = None
        self._section = None
        self._section_addr = None

        self.update_offsets()


    def update_offsets(self) -> Optional[MemorySection]:
        self.section_offsets = [p.address for p in self.sections]


    def map_section(self, section: MemorySection):
        self.sections.append(section)
        self.update_offsets()


    def find_section(self, addr: int) -> Optional[MemorySection]:
        #GP-0.6.2-eq:A.7
        if addr < 2**16:
            msg = "Invalid memory access"
            logging.debug(msg)
            raise PanicError(msg)

        if not self.section_offsets:
            # Note: sections not mapped, return None for pagefault handling
            return None

        for section in self.sections:
            if section.address <= addr <= section.paged_tail:
                return section

        return None


    def write_int(self, addr: int, value: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
            section = self.find_section(addr)
        else:
            section = self._section

        if not section:
            # Record the base address of the missing page for teh pagefault
            self._mem_addr = addr - (addr % PVM_PAGE_SIZE)
            raise PVMMemoryError("MemorySection not found")

        section_addr = (addr - section.address)  #% section.size #TODO: not sure if % necesarry?
        if section.acl is not None and not section.acl_check(section_addr, length, MEM_W):
            # When an ACL check fails, report the base of the first failing page.
            fault_page = section.acl_check_pages(section_addr, length, MEM_W)
            if fault_page < 0:
                fault_page = section_addr // PVM_PAGE_SIZE
            self._mem_addr = section.address + fault_page * PVM_PAGE_SIZE
            raise PVMMemoryError(f"Memory address {addr} ACL write check failed")

        self._section = section
        self._section_addr = section_addr

        # Set the mem page according to the found page for this range
        section.write_int(section_addr, value, length)


    def read_int(self, addr: int, length: int):
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = addr

        if not (self._section and self._section.address <= addr < self._section.address + self._section.size):
            section = self.find_section(addr)
        else:
            section = self._section

        if not section:
            self._mem_addr = addr - (addr % PVM_PAGE_SIZE)
            raise PVMMemoryError("MemorySection not found")

        section_addr = (addr - section.address) #% section.size  #TODO: not sure if % necesarry?
        if section.acl is not None and not section.acl_check(section_addr, length, MEM_R):
            # When an ACL check fails, report the base of the first failing page.
            fault_page = section.acl_check_pages(section_addr, length, MEM_R)
            if fault_page < 0:
                fault_page = section_addr // PVM_PAGE_SIZE
            self._mem_addr = section.address + fault_page * PVM_PAGE_SIZE
            raise PVMMemoryError(f"Memory address {addr} ACL read check failed")

        self._section = section
        self._section_addr = section_addr

        # Set the mem page according to the found page for this range
        return section.read_int(section_addr, length)


    def is_accessible(self, address: int, length: int, mode: int) -> bool:
        if length == 0:
            return True

        try:
            section = self.find_section(address)
        except (PanicError, PVMMemoryError):
            section = None

        if not section:
            return False

        if mode not in (MEM_R, MEM_W, MEM_RW):
            raise PVMError(f"Invalid PVMMemory mode: {mode}")

        local_addr = address - section.address
        if section.acl and not section.acl_check(local_addr, length, mode):
            return False

        bytes_required = local_addr + length

        if bytes_required > section.size:
            return False

        return True


    def read_bytes(self, address: int, length: int, padding:int = None) -> bytes:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        if length == 0:
            return bytes()

        section = self.find_section(address)
        if not section:
            self._mem_addr = address - (address % PVM_PAGE_SIZE)
            raise PVMMemoryError(f"MemorySection not found {address}")

        section_addr = (address - section.address)  #% section.size  #TODO: not sure if % necesarry?
        if section.acl is not None and not section.acl_check(section_addr, length, MEM_R):
            raise PVMMemoryError(
                f"Memory address {address} ACL read check failed (offset={section_addr}, len={length}, "
                f"section_start={section.address}, paged_tail={section.paged_tail}, section_size={section.size})"
            )

        section_bytes = (section.size - section_addr)
        if section_bytes < length:
            raise PVMMemoryError(
                f"Heap overflow {length} > {section_bytes} (offset={section_addr}, section_size={section.size}, "
                f"section_start={section.address}, paged_tail={section.paged_tail})"
            )

        mem_bytes = bytes(section.contents[section_addr:section_addr+length])
        if padding and len(mem_bytes) < padding:
            mem_bytes.ljust(padding, b'\0')

        return mem_bytes


    def write_bytes(self, address: int, content: bytes) -> None:
        """
        """
        # Always store the requested memory address so we can refer it after a PVMMemoryError fx
        self._mem_addr = address

        bytes_remaining = len(content)
        # TODO: or raise PVMMemoryError?
        if bytes_remaining == 0:
            return

        section = self.find_section(address)
        if not section:
            self._mem_addr = address - (address % PVM_PAGE_SIZE)
            raise PVMMemoryError(f"MemorySection not found {address}")

        section_addr = (address - section.address) #% section.size  #TODO: not sure if % necesarry?
        if section.acl and not section.acl_check(section_addr, len(content), MEM_W):
            raise PVMMemoryError(
                f"Memory address {address} ACL check failed (offset={section_addr}, len={len(content)}, "
                f"section_start={section.address}, paged_tail={section.paged_tail}, section_size={section.size})"
            )

        section_bytes = (section.size - section_addr)

        if section_bytes < len(content):
            raise PVMMemoryError(
                f"Heap overflow {len(content)} > {section_bytes} (offset={section_addr}, section_size={section.size}, "
                f"section_start={section.address}, paged_tail={section.paged_tail})"
            )

        section.set_content(content, section_addr, section_addr+len(content))


    def zero(self, page_idx: int, nr_pages: int, acl: int):
        """
        Allocate and zero-initialize pages. Creates a MemorySection if none exists.
        For inner PVMs (refine context), sections can be created at any valid address.
        """
        mem_addr = page_idx * PVM_PAGE_SIZE
        nr_bytes = nr_pages * PVM_PAGE_SIZE

        # Try to find an existing section or create a new one
        section = self._find_or_create_section(mem_addr, nr_bytes, acl)

        # Zero the memory and set ACL
        local_offset = mem_addr - section.address
        local_page = local_offset // PVM_PAGE_SIZE
        section.acl_set_pages(local_page, nr_pages, acl)
        section.contents[local_offset:local_offset + nr_bytes] = bytes(nr_bytes)


    def _find_or_create_section(self, mem_addr: int, nr_bytes: int, acl: int) -> MemorySection:
        """
        Find an existing section containing the address, or create a new one.
        For inner PVMs (empty sections list), create sections dynamically.
        """
        # Check if address falls within an existing section
        for section in self.sections:
            if section.address <= mem_addr < section.address + section.size:
                # Extend section if needed
                end_needed = mem_addr + nr_bytes
                if end_needed > section.address + section.size:
                    self._extend_section(section, end_needed - section.address)
                return section

        # No existing section - create a new one
        # For inner PVMs, we allow sections anywhere (page >= 16)
        new_section = MemorySection(
            address=mem_addr,
            size=nr_bytes,
            contents=bytearray(nr_bytes),
            acl=acl
        )
        self.sections.append(new_section)
        self.update_offsets()
        return new_section


    def _extend_section(self, section: MemorySection, new_size: int):
        """Extend a section's contents to accommodate more pages."""
        if new_size > section.size:
            old_contents = section.contents
            old_size = len(old_contents)
            section.contents = bytearray(new_size)
            section.contents[:old_size] = old_contents
            section.size = new_size
            section.paged_tail = section.address + new_size
            # Re-allocate ACL bitmap for new size
            section.alloc_acl(section.acl, new_size)
            self.update_offsets()


    def void(self, page_idx: int, nr_pages: int, acl: int):
        mem_addr = page_idx * PVM_PAGE_SIZE

        section = self.find_section(mem_addr)
        if not section:
            raise PVMMemoryError(f"MemorySection not found {mem_addr}")

        page_nr = (mem_addr - section.address) // PVM_PAGE_SIZE
        section.acl_set_pages(page_nr, nr_pages, acl)
        offset = mem_addr - section.address
        section.contents[offset:offset + nr_pages * PVM_PAGE_SIZE] = bytes(nr_pages * PVM_PAGE_SIZE)


    def alter_accessibility(self, page_idx: int, nr_pages: int, acl: int):
        """
        Set accessibility for a range of pages (matching reference API).
        Pages must already be allocated via zero().
        """
        mem_addr = page_idx * PVM_PAGE_SIZE

        section = self.find_section(mem_addr)
        if not section:
            raise PVMMemoryError(f"Cannot alter accessibility: page {page_idx} not allocated")

        local_page = (mem_addr - section.address) // PVM_PAGE_SIZE
        section.acl_set_pages(local_page, nr_pages, acl)


    def is_null(self, page_idx: int, nr_pages: int) -> bool:
        """
        Check if pages are in NULL (inaccessible) state.
        Used by hc_pages for r > 2 validation (pages must be inaccessible before void operation).
        Returns True if all pages are either unallocated or have MEM_I (inaccessible) ACL.
        """
        for p in range(page_idx, page_idx + nr_pages):
            addr = p * PVM_PAGE_SIZE

            try:
                section = self.find_section(addr)
            except (PanicError, PVMMemoryError):
                section = None

            if section is None:
                continue  # Unallocated = NULL

            # Check if this page has inaccessible ACL
            local_addr = addr - section.address
            if section.acl_check(local_addr, PVM_PAGE_SIZE, MEM_R):
                return False
            if section.acl_check(local_addr, PVM_PAGE_SIZE, MEM_W):
                return False

        return True


    @staticmethod
    def zone_size(items: int) -> int:
        """
        GP-0.6.2-eq:A.38 (Z)
        """
        return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)
