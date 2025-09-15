"""
AOT compilation module for complex Numba JIT functions - Part 2.
This handles memory operations and other complex functions.

Implements exports with signatures that match the JIT versions used by
interpreter_numba.py so they can be substituted 1:1 via the loader.
"""

import numpy as np
import numba.types
from numba.pycc import CC
from numba.typed import Dict

# Create the compilation unit
cc = CC('pvm_numba_aot2')
cc.verbose = True

# Type aliases
types = numba.types
u8 = types.uint8
u32 = types.uint32
u64 = types.uint64
i32 = types.int32
i64 = types.int64

# Array types
u8_array = types.Array(u8, 1, 'C')
u64_array = types.Array(u64, 1, 'C')
i32_array = types.Array(i32, 1, 'C')

# List of arrays type for memory sections
u8_array_list = types.ListType(u8_array)

# Dict type for ACL
dict_u64_u64 = types.DictType(u64, u64)

# Constants (must match interpreter_numba.py)
MEM_INACCESSIBLE = 0
MEM_WRITABLE = 2
PAGE_SIZE = 4096

# 23. mem_write_jit - exact signature and behavior matching interpreter
@cc.export('mem_write_jit', (u64, u64, u8, u64_array, u64_array, u8_array_list, dict_u64_u64))
def mem_write_jit(addr, value, bytes_to_write, section_starts, section_ends, section_arrays, acl_dict):
    """Write value to memory with bounds and ACL checking.
    Returns status:int32 where 0 is success and -1 is fault.
    """
    idx = -1
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = i
            break

    if idx < 0:
        return np.int32(-1)

    page_nr = addr // np.uint64(PAGE_SIZE)
    if (page_nr not in acl_dict) or (acl_dict[page_nr] < np.uint64(MEM_WRITABLE)):
        return np.int32(-1)

    start = section_starts[idx]
    off = addr - start
    a = section_arrays[idx]

    if off + np.uint64(bytes_to_write) > np.uint64(len(a)):
        return np.int32(-1)

    # Mask value for <8 byte writes
    if bytes_to_write < np.uint8(8):
        shift = np.uint64(bytes_to_write) * np.uint64(8)
        mask = (np.uint64(1) << shift) - np.uint64(1)
        value = value & mask

    base = int(off)
    if bytes_to_write == np.uint8(1):
        a[base] = np.uint8(value & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(2):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(4):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
        a[base + 2] = np.uint8((value >> np.uint64(16)) & np.uint64(0xFF))
        a[base + 3] = np.uint8((value >> np.uint64(24)) & np.uint64(0xFF))
    elif bytes_to_write == np.uint8(8):
        a[base] = np.uint8(value & np.uint64(0xFF))
        a[base + 1] = np.uint8((value >> np.uint64(8)) & np.uint64(0xFF))
        a[base + 2] = np.uint8((value >> np.uint64(16)) & np.uint64(0xFF))
        a[base + 3] = np.uint8((value >> np.uint64(24)) & np.uint64(0xFF))
        a[base + 4] = np.uint8((value >> np.uint64(32)) & np.uint64(0xFF))
        a[base + 5] = np.uint8((value >> np.uint64(40)) & np.uint64(0xFF))
        a[base + 6] = np.uint8((value >> np.uint64(48)) & np.uint64(0xFF))
        a[base + 7] = np.uint8((value >> np.uint64(56)) & np.uint64(0xFF))
    else:
        return np.int32(-1)

    return np.int32(0)

# 24. mem_read_jit - exact signature and behavior matching interpreter
@cc.export('mem_read_jit', (u64, u8, u64_array, u64_array, u8_array_list, dict_u64_u64))
def mem_read_jit(addr, bytes_to_read, section_starts, section_ends, section_arrays, acl_dict):
    """Read value from memory with bounds and ACL checking.
    Returns (status:int32, value:uint64) where status==0 on success.
    """
    idx = -1
    for i in range(len(section_starts)):
        if section_starts[i] <= addr <= section_ends[i]:
            idx = i
            break

    if idx < 0:
        return np.int32(-1), np.uint64(0)

    page_nr = addr // np.uint64(PAGE_SIZE)
    if (page_nr not in acl_dict) or (acl_dict[page_nr] == np.uint64(MEM_INACCESSIBLE)):
        return np.int32(-1), np.uint64(0)

    start = section_starts[idx]
    off = addr - start
    a = section_arrays[idx]
    if off + np.uint64(bytes_to_read) > np.uint64(len(a)):
        return np.int32(-1), np.uint64(0)

    base = int(off)
    if bytes_to_read == np.uint8(1):
        return np.int32(0), np.uint64(a[base])
    elif bytes_to_read == np.uint8(2):
        return np.int32(0), (np.uint64(a[base]) | (np.uint64(a[base + 1]) << np.uint64(8)))
    elif bytes_to_read == np.uint8(4):
        return np.int32(0), (np.uint64(a[base]) |
                              (np.uint64(a[base + 1]) << np.uint64(8)) |
                              (np.uint64(a[base + 2]) << np.uint64(16)) |
                              (np.uint64(a[base + 3]) << np.uint64(24)))
    elif bytes_to_read == np.uint8(8):
        return np.int32(0), (np.uint64(a[base]) |
                              (np.uint64(a[base + 1]) << np.uint64(8)) |
                              (np.uint64(a[base + 2]) << np.uint64(16)) |
                              (np.uint64(a[base + 3]) << np.uint64(24)) |
                              (np.uint64(a[base + 4]) << np.uint64(32)) |
                              (np.uint64(a[base + 5]) << np.uint64(40)) |
                              (np.uint64(a[base + 6]) << np.uint64(48)) |
                              (np.uint64(a[base + 7]) << np.uint64(56)))
    else:
        return np.int32(-1), np.uint64(0)

# 25. get_memory_hash
@cc.export('get_memory_hash', u64(u8_array_list, i32))
def get_memory_hash(section_arrays, seg_idx):
    """Get hash of memory segment."""
    if 0 <= seg_idx < len(section_arrays):
        mem = section_arrays[seg_idx]
        h = np.uint64(0)
        for i in range(len(mem)):
            h = h * np.uint64(31) + np.uint64(mem[i])
        return h
    return np.uint64(0)

# 26. sbrk_jit - Heap growth function (matches interpreter signature)
@cc.export('sbrk_jit', (u64, u64, u64, dict_u64_u64, i64, u8_array_list, u64_array))
def sbrk_jit(size, current_heap_ptr, next_section_start, acl_dict, mem_writable, section_arrays, section_starts):
    """JIT implementation of sbrk heap allocation with optional heap growth.
    Returns (new_heap_ptr:uint64, grew_flag:int32) where grew_flag==1 if buffer extended.
    """
    if size == 0:
        return current_heap_ptr, np.int32(0)

    new_heap_ptr = current_heap_ptr + size
    if new_heap_ptr >= next_section_start:
        return np.uint64(0), np.int32(0)

    # Calculate page boundaries (ceil to page size)
    next_page_boundary = ((current_heap_ptr + np.uint64(PAGE_SIZE) - np.uint64(1)) // np.uint64(PAGE_SIZE)) * np.uint64(PAGE_SIZE)

    grew_flag = np.int32(0)
    if new_heap_ptr > next_page_boundary:
        new_heap_end = ((new_heap_ptr + np.uint64(PAGE_SIZE) - np.uint64(1)) // np.uint64(PAGE_SIZE)) * np.uint64(PAGE_SIZE)
        growth = new_heap_end - next_page_boundary

        # Attempt to grow underlying heap buffer when we exceed pre-allocated memory
        try:
            heap_arr = section_arrays[1]
            base_start = section_starts[1]
            desired_len = int(new_heap_end - base_start)
            cur_len = len(heap_arr)
            if desired_len > cur_len:
                new_arr = np.zeros(desired_len, dtype=np.uint8)
                for i in range(cur_len):
                    new_arr[i] = heap_arr[i]
                section_arrays[1] = new_arr
                grew_flag = np.int32(1)
        except Exception:
            pass

        # Create ACL of new pages
        next_page_nr = current_heap_ptr // np.uint64(PAGE_SIZE)
        pages = growth // np.uint64(PAGE_SIZE) + np.uint64(1)
        for page_nr in range(int(pages)):
            acl_dict[next_page_nr + np.uint64(page_nr)] = np.uint64(mem_writable)

    return new_heap_ptr, grew_flag

# 27. djump_jit - Dynamic jump
@cc.export('djump_jit', i32(u32, i32_array, u32, i32_array))
def djump_jit(a, jump_table, pc, pc_to_inst_index):
    """Handle dynamic jump."""
    if a >= len(jump_table):
        return np.int32(-1)
    
    target_offset = jump_table[a]
    if target_offset == -1:
        return np.int32(-1)
    
    target_pc = np.int64(pc) + np.int64(target_offset)
    
    if target_pc < 0 or target_pc >= len(pc_to_inst_index):
        return np.int32(-1)
    
    target_inst = pc_to_inst_index[target_pc]
    return target_inst

if __name__ == '__main__':
    # Compile the module
    cc.compile()
