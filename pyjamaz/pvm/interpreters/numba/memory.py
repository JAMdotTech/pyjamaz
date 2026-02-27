import numpy as np
import numpy.typing as npt

from pyjamaz.pvm.interpreters.cpython.memory import PVMMemory as CPythonPVMMemory
from pyjamaz.pvm.interpreters.numba.memory_section import MemorySection
from pyjamaz.pvm.types import _ADDR_MASK, page_size


class PVMMemory(CPythonPVMMemory):
    """
    Wraps CPythonPVMMemory using mmap, but uses zero copy numpy uint8 views instead for Numba compatibility
    """

    def __init__(
        self,
        rom: MemorySection | None = None,
        heap: MemorySection | None = None,
        stack: MemorySection | None = None,
        arguments: MemorySection | None = None,
        logger=None,
    ):
        super().__init__(rom=rom, heap=heap, stack=stack, arguments=arguments, logger=logger)
        self.sections = []

    def view_array(self, address: int, length: int) -> npt.NDArray[np.uint8]:
        return np.frombuffer(self.view(address, length), dtype=np.uint8)

    def add_segment(self, address: int, size: int, acl: int, contents: bytes = b"") -> None:
        super().add_segment(address, size, acl, contents)

        if size <= 0 and not contents:
            return

        address = int(address) & _ADDR_MASK
        seg_size = max(int(size), len(contents))
        if seg_size <= 0:
            return
        seg_size = page_size(seg_size)

        section = MemorySection(address=address, size=seg_size, contents=b"", acl=acl)
        section.paged_tail = address + seg_size
        section.contents = self.view_array(address, seg_size)

        if not hasattr(self, "sections") or self.sections is None:
            self.sections = []

        self.sections = [s for s in self.sections if int(s.address) != address]
        self.sections.append(section)

    def clone(self) -> "PVMMemory":
        base_clone = super().clone()
        cloned = object.__new__(PVMMemory)
        cloned.__dict__ = base_clone.__dict__

        source_sections = getattr(self, "sections", None)
        cloned.sections = []
        if source_sections:
            for source in source_sections:
                if source is None:
                    continue
                section = object.__new__(MemorySection)
                section.address = int(source.address)
                section.size = int(source.size)
                section.paged_tail = int(source.paged_tail)
                section.acl = source.acl
                section.contents = cloned.view_array(section.address, section.size)
                if hasattr(source, "acl_bitmap") and source.acl_bitmap is not None:
                    section.acl_bitmap = source.acl_bitmap.copy()
                else:
                    section.acl_bitmap = np.zeros(0, dtype=np.uint64)
                cloned.sections.append(section)

        return cloned
