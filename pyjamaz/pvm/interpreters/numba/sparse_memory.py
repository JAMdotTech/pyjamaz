from dataclasses import dataclass
from math import ceil
from typing import Optional, Sequence, Union

import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.constants import MEM_I, MEM_R, MEM_RW, MEM_W, PVM_INIT_ZONE_SIZE
from pyjamaz.pvm.exceptions import PVMError, PVMMemoryError
from pyjamaz.pvm.interpreters.numba.memory_section import MemorySection
from pyjamaz.pvm.types import PAGE_SIZE, _ADDR_MASK, _MAX_PAGE_IDX, _PAGE_MASK, _PAGE_SHIFT


@dataclass
class _SparseRegion:
    start: int
    data: bytearray

    @property
    def end(self) -> int:
        return self.start + len(self.data)


class SparsePVMMemory:
    """
    Sparse PVM memory for refine inner machines.

    The regular PVM memory maps the whole 4 GiB address space. Inner machines
    created by refine hostcall `machine` allocate pages explicitly through
    hostcall `pages`, so a paged sparse backing keeps the same ACL behaviour
    without paying for a fresh 4 GiB mmap per machine.
    """

    SIZE: int = 2**32

    def __init__(
        self,
        rom: Optional[MemorySection] = None,
        heap: Optional[MemorySection] = None,
        stack: Optional[MemorySection] = None,
        arguments: Optional[MemorySection] = None,
        logger=None,
    ):
        self._regions: list[_SparseRegion] = []
        self.pages_r: set[int] = set()
        self.pages_w: set[int] = set()
        self.sections = []

        self._mem_addr: int = -1
        self.heap_base: Optional[int] = None
        self.stack_base: Optional[int] = None
        self.heap_ptr: int = 0
        self.logger = logger
        self._layout_version: int = 0

        self._rom: Optional[MemorySection] = rom
        self._heap: Optional[MemorySection] = heap
        self._stack: Optional[MemorySection] = stack
        self._args: Optional[MemorySection] = arguments

        for section in (rom, heap, stack, arguments):
            if section:
                self.load_section(section)

        if heap:
            self.heap_base = heap.address
            self.heap_ptr = heap.address + heap.size
        if stack:
            self.stack_base = stack.address

    def _bump_layout_version(self) -> None:
        self._layout_version = getattr(self, "_layout_version", 0) + 1

    @staticmethod
    def _page_size(size: int) -> int:
        return ((int(size) + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE

    def _ensure_bounds(self, address: int, length: int) -> tuple[int, int]:
        address = int(address) & _ADDR_MASK
        length = int(length)
        if length < 0:
            raise PVMMemoryError(f"Invalid view length: {length}")
        end = address + length
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory range overflow: {address} + {length} > 2^32")
        return address, end

    def _find_region(self, address: int, length: int) -> Optional[_SparseRegion]:
        end = address + length
        for region in self._regions:
            if region.start <= address and end <= region.end:
                return region
        return None

    def _ensure_region(self, address: int, length: int) -> _SparseRegion:
        address, end = self._ensure_bounds(address, length)
        if length <= 0:
            region = self._find_region(address, 0)
            if region is not None:
                return region
            region = _SparseRegion(address, bytearray())
            self._regions.append(region)
            self._regions.sort(key=lambda item: item.start)
            return region

        existing = self._find_region(address, length)
        if existing is not None:
            return existing

        start_page = address >> _PAGE_SHIFT
        end_page = (end - 1) >> _PAGE_SHIFT
        new_start = start_page * PAGE_SIZE
        new_end = (end_page + 1) * PAGE_SIZE

        overlapping = [
            region
            for region in self._regions
            if not (region.end < new_start or region.start > new_end)
        ]
        for region in overlapping:
            new_start = min(new_start, region.start)
            new_end = max(new_end, region.end)

        merged = bytearray(new_end - new_start)
        for region in overlapping:
            dst = region.start - new_start
            merged[dst:dst + len(region.data)] = region.data

        overlapping_ids = {id(region) for region in overlapping}
        self._regions = [region for region in self._regions if id(region) not in overlapping_ids]
        region = _SparseRegion(new_start, merged)
        self._regions.append(region)
        self._regions.sort(key=lambda item: item.start)
        return region

    def view(self, address: int, length: int) -> memoryview:
        address, _end = self._ensure_bounds(address, length)
        if length == 0:
            return memoryview(bytearray())

        region = self._find_region(address, length)
        if region is None:
            raise PVMMemoryError(f"Memory range {address} + {length} is not allocated")
        offset = address - region.start
        return memoryview(region.data)[offset:offset + length]

    def view_array(self, address: int, length: int) -> npt.NDArray[np.uint8]:
        return np.frombuffer(self.view(address, length), dtype=np.uint8)

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

    def _check_access(self, address: int, length: int, mode: int, access: str) -> None:
        if length <= 0:
            return

        end = address + length
        start_page = address >> _PAGE_SHIFT
        end_page = (end - 1) >> _PAGE_SHIFT
        readable = mode in (MEM_R, MEM_RW)
        writable = mode in (MEM_W, MEM_RW)

        for pg in range(start_page, end_page + 1):
            if pg > _MAX_PAGE_IDX:
                self._page_fault(pg, address, access)
            if writable and pg not in self.pages_w:
                self._page_fault(pg, address, access)
            if readable and pg not in self.pages_r:
                self._page_fault(pg, address, access)

    def add_segment(self, address: int, size: int, acl: int, contents: bytes = b"") -> None:
        if size <= 0 and not contents:
            return

        address = int(address) & _ADDR_MASK
        size = max(int(size), len(contents))
        if size <= 0:
            return
        size = self._page_size(size)

        end = address + size
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory segment overflow: {address} + {size} > 2^32")

        region = self._ensure_region(address, size)
        start_page = address >> _PAGE_SHIFT
        for pg in range(start_page, start_page + size // PAGE_SIZE):
            self.set_acl(pg, acl)
        self._bump_layout_version()

        if contents:
            offset = address - region.start
            data_len = min(len(contents), size)
            region.data[offset:offset + data_len] = contents[:data_len]

        section = MemorySection(address=address, size=size, contents=b"", acl=acl)
        section.paged_tail = address + size
        section.contents = self.view_array(address, size)
        self.sections = [item for item in self.sections if int(item.address) != address]
        self.sections.append(section)

    def load_section(self, section: MemorySection) -> None:
        base_page = section.address >> _PAGE_SHIFT

        if section.size:
            nr_pages = ceil(section.size / PAGE_SIZE)
            default_acl = MEM_RW if section.acl is None else section.acl
            self._ensure_region(section.address, nr_pages * PAGE_SIZE)
            for local_page in range(nr_pages):
                self.merge_acl(base_page + local_page, default_acl)
            if nr_pages > 0:
                self._bump_layout_version()

        data_len = max(0, min(len(section.contents), section.paged_tail - section.address))
        if data_len > 0:
            self.write_bytes(section.address, section.contents[:data_len])

        section.contents = self.view(section.address, section.size)

    def _page_fault(self, page_idx: int, addr: int, access: str) -> None:
        self._mem_addr = page_idx * PAGE_SIZE
        raise PVMMemoryError(f"Memory address {addr} ACL {access} check failed")

    def read_bytes(self, address: int, length: int, padding: int = None) -> bytes:
        address, end = self._ensure_bounds(address, length)
        self._mem_addr = address

        if length <= 0:
            return b"".ljust(padding, b"\0") if padding else b""

        self._check_access(address, length, MEM_R, "read")
        region = self._find_region(address, length)
        if region is None:
            data = b"\0" * length
        else:
            offset = address - region.start
            data = bytes(region.data[offset:offset + length])

        if padding and len(data) < padding:
            data = data.ljust(padding, b"\0")
        return data

    def write_bytes(self, address: int, content: Union[bytes, bytearray, memoryview, Sequence[int]]) -> None:
        if not content:
            return

        data_bytes = content if isinstance(content, (bytes, bytearray, memoryview)) else bytes(content)
        address, _end = self._ensure_bounds(address, len(data_bytes))
        self._mem_addr = address

        self._check_access(address, len(data_bytes), MEM_W, "write")
        region = self._ensure_region(address, len(data_bytes))
        offset = address - region.start
        region.data[offset:offset + len(data_bytes)] = data_bytes

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
            return all(pg in self.pages_w for pg in range(start_page, end_page + 1))
        return all(pg in self.pages_r for pg in range(start_page, end_page + 1))

    def zero(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return

        start = page_idx * PAGE_SIZE
        length = nr_pages * PAGE_SIZE
        end = start + length
        if end > self.SIZE:
            raise PVMMemoryError(f"Memory zero overflow: {start} + {length} > 2^32")

        region = self._ensure_region(start, length)
        offset = start - region.start
        region.data[offset:offset + length] = b"\0" * length
        for pg in range(page_idx, page_idx + nr_pages):
            self.set_acl(pg, acl)
        self._bump_layout_version()

    def void(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        self.zero(page_idx, nr_pages, acl)

    def change_acl(self, page_idx: int, nr_pages: int, acl: int):
        if nr_pages <= 0:
            return
        for pg in range(page_idx, page_idx + nr_pages):
            self.set_acl(pg, acl)
        self._bump_layout_version()

    def is_null(self, page_idx: int, nr_pages: int) -> bool:
        for pg in range(page_idx, page_idx + nr_pages):
            if pg in self.pages_r or pg in self.pages_w:
                return False
        return True

    @staticmethod
    def clone_section(source: Optional[MemorySection]) -> Optional[MemorySection]:
        if source is None:
            return None

        data_len = max(0, int(source.paged_tail) - int(source.address))
        section_data = b""
        if data_len > 0:
            section_data = bytes(source.contents[:data_len])

        cloned = MemorySection(
            address=int(source.address),
            size=int(source.size),
            contents=section_data,
            acl=source.acl,
        )
        cloned.paged_tail = int(source.paged_tail)
        if hasattr(source, "acl_bitmap") and source.acl_bitmap is not None:
            cloned.acl_bitmap = source.acl_bitmap.copy()
        return cloned

    def clone(self) -> "SparsePVMMemory":
        rom = self.clone_section(self._rom)
        heap = self.clone_section(self._heap)
        stack = self.clone_section(self._stack)
        args = self.clone_section(self._args)

        cloned = SparsePVMMemory(rom=rom, heap=heap, stack=stack, arguments=args, logger=self.logger)
        cloned.heap_base = self.heap_base
        cloned.stack_base = self.stack_base
        cloned.heap_ptr = self.heap_ptr
        cloned._mem_addr = self._mem_addr
        cloned.pages_r = set(self.pages_r)
        cloned.pages_w = set(self.pages_w)
        cloned._layout_version = getattr(self, "_layout_version", 0)
        cloned._regions = [
            _SparseRegion(region.start, bytearray(region.data))
            for region in self._regions
        ]

        cloned.sections = []
        for source in getattr(self, "sections", []):
            section = self.clone_section(source)
            if section is None:
                continue
            section.contents = cloned.view_array(section.address, section.size)
            cloned.sections.append(section)
        return cloned

    def __copy__(self):
        return self.clone()

    def __deepcopy__(self, memo):
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        cloned = self.clone()
        memo[id(self)] = cloned
        return cloned

    @staticmethod
    def zone_size(items: int) -> int:
        return PVM_INIT_ZONE_SIZE * ceil(items / PVM_INIT_ZONE_SIZE)
