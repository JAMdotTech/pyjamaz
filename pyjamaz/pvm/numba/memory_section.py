import npt
import numpy as np

from pyjamaz.pvm.cpython.memory_section import MemorySection as CPythonMemorySection


# Note: these memory segment helpers are defined outside MemorySection, so we can refer to them from code not using
#       associated object types

class MemorySection(CPythonMemorySection):

    def __init__(self, address, size, contents, acl=None):
        self.acl_bitmap: npt.NDArray[np.uint64] = np.zeros(0, dtype=np.uint64) # Bitmask for per page ACL control
        super().__init__(address, size=size, contents=contents, acl=acl)

    def alloc_contents(self, _bytes):
        # Note: Numba cannot JIT-optimize operations on Python bytearray objects — they’re treated as opaque Python objects,
        self.contents = np.zeros(self.size, dtype=np.uint8)
        if _bytes:
            length = len(_bytes)
            if isinstance(_bytes, (list, tuple)):
                self.contents[0:length] = np.array(_bytes, dtype=np.uint8)
            elif isinstance(_bytes, np.ndarray):
                self.contents[0:length] = _bytes.astype(np.uint8)
            else:
                self.contents[0:length] = np.frombuffer(bytes(_bytes), dtype=np.uint8)
