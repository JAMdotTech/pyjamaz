from math import ceil
from typing import Dict, Optional, Sequence, Union, TYPE_CHECKING
from pyjamaz.pvm.constants import PVM_INIT_ZONE_SIZE, PVM_PAGE_SIZE, MEM_R, MEM_W, MEM_RW, MEM_I
from pyjamaz.pvm.exceptions import PVMMemoryError, PVMError

if TYPE_CHECKING:
    from pyjamaz.pvm.interpreters.cpython.memory_section import MemorySection

# Page-based memory constants
ADDR_MOD = 2**32
PAGE_SIZE = PVM_PAGE_SIZE
_PAGE_SHIFT = PAGE_SIZE.bit_length() - 1
_PAGE_MASK = PAGE_SIZE - 1
_ADDR_MASK = ADDR_MOD - 1
_PAGE_CACHE_LIMIT = 16
_ZERO_PAGE = bytes(PAGE_SIZE)


class PVMMemory:

    SIZE: int = 2**32

    def __init__(
        self,
        rom=None,
        heap=None,
        stack=None,
        arguments=None,
        logger=None,
    ):
        self.pages: Dict[int, bytearray] = {}
        self.pages_r: set[int] = set()
        self.pages_w: set[int] = set()
        self._page_cache: Dict[int, bytearray] = {}

        self._mem_addr: int = -1
        self.heap_base: Optional[int] = None
        self.stack_base: Optional[int] = None
        self.heap_ptr: int = 0
        self.logger = logger

        for section in (rom, heap, stack, arguments):
            if section:
                self.load_section(section)

        if heap:
            self.heap_base = heap.address
            self.heap_ptr = heap.address + heap.size
        if stack:
            self.stack_base = stack.address


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

        size = max(size, len(contents))
        if size <= 0:
            return
        size = ((size + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE

        start_page = address >> _PAGE_SHIFT
        page_count = size // PAGE_SIZE
        for pg in range(start_page, start_page + page_count):
            self.set_acl(pg, acl)
            self._page_cache.pop(pg, None)

        data_len = min(len(contents), size)
        if data_len <= 0:
            return

        nr_pages = ceil(data_len / PAGE_SIZE)
        for local_page in range(nr_pages):
            start = local_page * PAGE_SIZE
            end = min(start + PAGE_SIZE, data_len)
            self.write(start_page + local_page, contents[start:end])


    def load_section(self, section: "MemorySection") -> None:
        base_page = section.address >> _PAGE_SHIFT

        if section.size:
            nr_pages = ceil(section.size / PAGE_SIZE)
            default_acl = MEM_RW if section.acl is None else section.acl
            for local_page in range(nr_pages):
                self.merge_acl(base_page + local_page, default_acl)

        data_len = max(0, min(len(section.contents), section.paged_tail - section.address))
        if data_len <= 0:
            return

        nr_pages = ceil(data_len / PAGE_SIZE)
        for local_page in range(nr_pages):
            start = local_page * PAGE_SIZE
            end = min(start + PAGE_SIZE, data_len)
            self.write(base_page + local_page, section.contents[start:end])


    def write(self, page_idx: int, data: bytes) -> None:
        page = self.pages.get(page_idx)
        if page is None:
            if not data or not any(data):
                return
            page = bytearray(PAGE_SIZE)
            self.pages[page_idx] = page
        if data:
            page[0:len(data)] = data


    def page_content(self, page_idx: int, *, create: bool = False) -> bytearray:
        cached_page = self._page_cache.get(page_idx)
        if cached_page is not None:
            return cached_page

        page_data = self.pages.get(page_idx)
        if page_data is not None:
            if len(self._page_cache) < _PAGE_CACHE_LIMIT:
                self._page_cache[page_idx] = page_data
            return page_data

        if not create:
            return _ZERO_PAGE

        page_data = bytearray(PAGE_SIZE)
        self.pages[page_idx] = page_data
        if len(self._page_cache) < _PAGE_CACHE_LIMIT:
            self._page_cache[page_idx] = page_data
        return page_data


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
            if pg not in self.pages_r:
                if self.logger:
                    self.logger.debug(f"Not allowed to read {address}(Page={pg})")
                self._page_fault(pg, address, "read")

            page_off = address & _PAGE_MASK
            src_page = self.page_content(pg, create=False)
            data = bytes(src_page[page_off:page_off + length])
            if padding and len(data) < padding:
                data = data.ljust(padding, b"\0")
            return data

        # Multi-page path: validate page ACLs and collect zero-copy slices,
        # then materialize once via join.
        start_page = address >> _PAGE_SHIFT
        end_page = (end - 1) >> _PAGE_SHIFT
        parts = []
        for pg in range(start_page, end_page + 1):
            page_start = pg << _PAGE_SHIFT
            seg_start = address if pg == start_page else page_start
            seg_end = end if pg == end_page else page_start + PAGE_SIZE

            if pg not in self.pages_r:
                fault_addr = seg_start
                if self.logger:
                    self.logger.debug(f"Not allowed to read {fault_addr}(Page={pg})")
                self._page_fault(pg, fault_addr, "read")

            page_off = seg_start - page_start
            chunk = seg_end - seg_start
            src_page = self.page_content(pg, create=False)
            parts.append(memoryview(src_page)[page_off:page_off + chunk])

        data = b"".join(parts)
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
            if pg not in self.pages_w:
                if self.logger:
                    self.logger.debug(f"Not allowed to write {address}(Page={pg})")
                self._page_fault(pg, address, "write")

            page_off = address & _PAGE_MASK
            dst_page = self.page_content(pg, create=True)
            dst_page[page_off:page_off + length] = data_bytes
            return

        start_page = address >> _PAGE_SHIFT
        end_page = (end - 1) >> _PAGE_SHIFT

        # Multi-page path: validate first to avoid partial writes on faults.
        for pg in range(start_page, end_page + 1):
            page_start = pg << _PAGE_SHIFT
            fault_addr = address if pg == start_page else page_start
            if pg not in self.pages_w:
                if self.logger:
                    self.logger.debug(f"Not allowed to write {fault_addr}(Page={pg})")
                self._page_fault(pg, fault_addr, "write")

        in_mv = data_bytes if isinstance(data_bytes, memoryview) else memoryview(data_bytes)
        cursor = 0
        for pg in range(start_page, end_page + 1):
            page_start = pg << _PAGE_SHIFT
            seg_start = address if pg == start_page else page_start
            seg_end = end if pg == end_page else page_start + PAGE_SIZE
            page_off = seg_start - page_start
            chunk = seg_end - seg_start

            dst_page = self.page_content(pg, create=True)
            dst_page[page_off:page_off + chunk] = in_mv[cursor:cursor + chunk]
            cursor += chunk

        return


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
        for pg in range(page_idx, page_idx + nr_pages):
            page_data = self.page_content(pg, create=True)
            page_data[:] = _ZERO_PAGE
            self.set_acl(pg, acl)
            self._page_cache.pop(pg, None)

        return


    def void(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        self.zero(page_idx, nr_pages, acl)


    def change_acl(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        for pg in range(page_idx, page_idx + nr_pages):
            self.set_acl(pg, acl)
            self._page_cache.pop(pg, None)


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
