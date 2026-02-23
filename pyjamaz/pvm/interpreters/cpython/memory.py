import mmap

from math import ceil
from typing import Optional, Sequence, TYPE_CHECKING, Union

from pyjamaz.pvm.constants import MEM_I, MEM_R, MEM_RW, MEM_W, PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE
from pyjamaz.pvm.exceptions import PVMError, PVMMemoryError

if TYPE_CHECKING:
    from .memory_section import MemorySection


# Page-based memory constants
ADDR_MOD = 2**32
PAGE_SIZE = PVM_PAGE_SIZE
_PAGE_SHIFT = PAGE_SIZE.bit_length() - 1
_PAGE_MASK = PAGE_SIZE - 1
_ADDR_MASK = ADDR_MOD - 1
_MAX_PAGE_IDX = (ADDR_MOD // PAGE_SIZE) - 1


class PVMMemory:
    SIZE: int = 2**32

    def __init__(
        self,
        rom: Optional["MemorySection"] = None,
        heap: Optional["MemorySection"] = None,
        stack: Optional["MemorySection"] = None,
        arguments: Optional["MemorySection"] = None,
        logger=None,
    ):
        self._mm = mmap.mmap(-1, self.SIZE)
        self._mv = memoryview(self._mm)

        self.pages_r: set[int] = set()
        self.pages_w: set[int] = set()

        self._mem_addr: int = -1
        self.heap_base: Optional[int] = None
        self.stack_base: Optional[int] = None
        self.heap_ptr: int = 0
        self.logger = logger

        self._rom: Optional["MemorySection"] = rom
        self._heap: Optional["MemorySection"] = heap
        self._stack: Optional["MemorySection"] = stack
        self._args: Optional["MemorySection"] = arguments

        for section in (rom, heap, stack, arguments):
            if section:
                self.load_section(section)

        if heap:
            self.heap_base = heap.address
            self.heap_ptr = heap.address + heap.size
        if stack:
            self.stack_base = stack.address

    def view(self, address: int, length: int) -> memoryview:
        address = int(address) & _ADDR_MASK
        if length < 0:
            raise PVMMemoryError(f"Invalid view length: {length}")
        end = address + length
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory view overflow: {address} + {length} > 2^32")
        return self._mv[address:end]

    def merge_acl(self, page_idx: int, acl: Optional[int]) -> None:
        acl = MEM_RW if acl is None else acl
        if acl != MEM_I:
            self.pages_r.add(page_idx)
        if acl in (MEM_W, MEM_RW):
            self.pages_w.add(page_idx)

    def set_acl(self, page_idx: int, acl: Optional[int]) -> None:
        acl = MEM_RW if acl is None else acl
        if acl == MEM_I:
            self.pages_r.discard(page_idx)
            self.pages_w.discard(page_idx)
            return

        self.pages_r.add(page_idx)
        if acl in (MEM_W, MEM_RW):
            self.pages_w.add(page_idx)
        else:
            self.pages_w.discard(page_idx)

    def add_segment(self, address: int, size: int, acl: int, contents: bytes = b"") -> None:
        if size <= 0 and not contents:
            return

        address = int(address) & _ADDR_MASK
        size = max(size, len(contents))
        if size <= 0:
            return
        size = ((size + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE

        end = address + size
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory segment overflow: {address} + {size} > 2^32")

        start_page = address >> _PAGE_SHIFT
        page_count = size // PAGE_SIZE
        for pg in range(start_page, start_page + page_count):
            self.set_acl(pg, acl)

        data_len = min(len(contents), size)
        if data_len <= 0:
            return

        self._mv[address:address + data_len] = memoryview(contents)[:data_len]

    def load_section(self, section: "MemorySection") -> None:
        base_page = section.address >> _PAGE_SHIFT

        if section.size:
            nr_pages = ceil(section.size / PAGE_SIZE)
            default_acl = MEM_RW if section.acl is None else section.acl
            for local_page in range(nr_pages):
                self.merge_acl(base_page + local_page, default_acl)

        data_len = max(0, min(len(section.contents), section.paged_tail - section.address))
        if data_len > 0:
            self._mv[section.address:section.address + data_len] = section.contents[:data_len]

        # Keep section storage as a shared view onto canonical mmap memory.
        section.contents = self.view(section.address, section.size)

    def _page_fault(self, page_idx: int, addr: int, access: str) -> None:
        self._mem_addr = page_idx * PAGE_SIZE
        raise PVMMemoryError(f"Memory address {addr} ACL {access} check failed")

    def read_bytes(self, address: int, length: int, padding: int = None) -> bytes:
        address = int(address) & _ADDR_MASK
        self._mem_addr = address

        if length <= 0:
            return b"".ljust(padding, b"\0") if padding else b""

        end = address + length

        # Single-page fast path
        if (address >> _PAGE_SHIFT) == ((end - 1) >> _PAGE_SHIFT):
            pg = address >> _PAGE_SHIFT
            if pg > _MAX_PAGE_IDX or pg not in self.pages_r:
                if self.logger:
                    self.logger.debug(f"Not allowed to read {address}(Page={pg})")
                self._page_fault(pg, address, "read")

            data = bytes(self._mv[address:address + length])
            if padding and len(data) < padding:
                data = data.ljust(padding, b"\0")
            return data

        # Multi-page path: validate ACL page-by-page first, then perform one bulk copy.
        scan_addr = address
        while scan_addr < end:
            pg = scan_addr >> _PAGE_SHIFT
            page_off = scan_addr & _PAGE_MASK
            chunk = min(PAGE_SIZE - page_off, end - scan_addr)

            if pg > _MAX_PAGE_IDX or pg not in self.pages_r:
                if self.logger:
                    self.logger.debug(f"Not allowed to read {scan_addr}(Page={pg})")
                self._page_fault(pg, scan_addr, "read")

            scan_addr += chunk

        data = bytes(self._mv[address:end])
        if padding and len(data) < padding:
            data = data.ljust(padding, b"\0")
        return data

    def write_bytes(self, address: int, content: Union[bytes, Sequence[int]]) -> None:
        if not content:
            return

        data_bytes = content if isinstance(content, (bytes, bytearray, memoryview)) else bytes(content)
        address = int(address) & _ADDR_MASK
        self._mem_addr = address

        length = len(data_bytes)
        end = address + length

        # Single-page fast path
        if (address >> _PAGE_SHIFT) == ((end - 1) >> _PAGE_SHIFT):
            pg = address >> _PAGE_SHIFT
            if pg > _MAX_PAGE_IDX or pg not in self.pages_w:
                if self.logger:
                    self.logger.debug(f"Not allowed to write {address}(Page={pg})")
                self._page_fault(pg, address, "write")

            self._mv[address:address + length] = data_bytes
            return

        # Multi-page path: validate ACL page-by-page first, then perform one bulk write.
        scan_addr = address
        while scan_addr < end:
            pg = scan_addr >> _PAGE_SHIFT
            page_off = scan_addr & _PAGE_MASK
            chunk = min(PAGE_SIZE - page_off, end - scan_addr)

            if pg > _MAX_PAGE_IDX or pg not in self.pages_w:
                if self.logger:
                    self.logger.debug(f"Not allowed to write {scan_addr}(Page={pg})")
                self._page_fault(pg, scan_addr, "write")

            scan_addr += chunk

        self._mv[address:end] = data_bytes

    def read_int(self, addr: int, length: int) -> int:
        if length <= 0:
            return 0
        data = self.read_bytes(addr, length)
        return int.from_bytes(data, byteorder="little")

    def write_int(self, addr: int, value: int, length: int):
        if length <= 0:
            return
        mask = (1 << (length * 8)) - 1
        data = int(value) & mask
        self.write_bytes(addr, data.to_bytes(length, byteorder="little"))

    def is_accessible(self, address: int, length: int, mode: int) -> bool:
        if length == 0:
            return True
        address = int(address) & _ADDR_MASK

        if mode not in (MEM_R, MEM_W, MEM_RW):
            raise PVMError(f"Invalid PVMMemory mode: {mode}")

        end = address + length
        start_page = address >> _PAGE_SHIFT
        end_page = (end - 1) >> _PAGE_SHIFT

        if mode in (MEM_W, MEM_RW):
            for pg in range(start_page, end_page + 1):
                if pg not in self.pages_w:
                    return False
            return True

        for pg in range(start_page, end_page + 1):
            if pg not in self.pages_r:
                return False
        return True

    def zero(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return

        start = page_idx * PAGE_SIZE
        end = start + nr_pages * PAGE_SIZE
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory zero overflow: {start} + {nr_pages * PAGE_SIZE} > 2^32")

        self._mv[start:end] = b"\0" * (nr_pages * PAGE_SIZE)
        for pg in range(page_idx, page_idx + nr_pages):
            self.set_acl(pg, acl)

    def void(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        self.zero(page_idx, nr_pages, acl)

    def change_acl(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        for pg in range(page_idx, page_idx + nr_pages):
            self.set_acl(pg, acl)

    def is_null(self, page_idx: int, nr_pages: int) -> bool:
        for pg in range(page_idx, page_idx + nr_pages):
            if pg in self.pages_r or pg in self.pages_w:
                return False
        return True

    @staticmethod
    def zone_size(items: int) -> int:
        """
        GP-0.6.2-eq:A.38 (Z)
        """
        return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)
