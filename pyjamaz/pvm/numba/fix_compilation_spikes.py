#!/usr/bin/env python3
"""
Fix for compilation spikes by ensuring consistent typing.

The issue: Memory functions receive arrays with different types/layouts,
causing Numba to compile new specializations (8-9 second delays).
"""

def generate_fixes():
    """Generate fixes for the compilation spikes."""
    
    print("Fix 1: Add explicit signatures to memory functions")
    print("=" * 60)
    print("""
# Replace this:
@njit(cache=True)
def mem_write_jit(addr: U64, value: U64, bytes_to_write: U8,
                  section_starts, section_ends, section_arrays, acl_dict):

# With this (explicit signatures):
from numba import types

mem_write_sig = types.int32(
    types.uint64,  # addr
    types.uint64,  # value  
    types.uint8,   # bytes_to_write
    types.uint64[:],  # section_starts - force consistent array type
    types.uint64[:],  # section_ends
    types.ListType(types.uint8[:]),  # section_arrays
    types.DictType(types.uint64, types.uint64)  # acl_dict
)

@njit(mem_write_sig, cache=True)
def mem_write_jit(addr, value, bytes_to_write,
                  section_starts, section_ends, section_arrays, acl_dict):
""")

    print("\nFix 2: Ensure arrays are consistently typed")
    print("=" * 60)
    print("""
# In invoke_native, ensure arrays have consistent types:

# Make sure these are always contiguous C arrays:
mem_section_starts = np.ascontiguousarray(mem_section_starts, dtype=np.uint64)
mem_section_ends = np.ascontiguousarray(mem_section_ends, dtype=np.uint64)

# Ensure section_arrays is a typed list:
if not isinstance(section_arrays, List):
    typed_arrays = List()
    for arr in section_arrays:
        typed_arrays.append(np.ascontiguousarray(arr, dtype=np.uint8))
    section_arrays = typed_arrays
""")

    print("\nFix 3: Disable parallel compilation")
    print("=" * 60)
    print("""
# Add to the environment setup:
os.environ['NUMBA_NUM_THREADS'] = '1'  # Avoid parallel compilation issues
os.environ['NUMBA_THREADING_LAYER'] = 'sequential'
""")

    print("\nFix 4: Pre-declare array types")
    print("=" * 60)
    print("""
# At module level, declare the types once:
from numba import types
from numba.typed import List

# Standard array types
u64_array_type = types.uint64[:]
u8_array_type = types.uint8[:]
u8_array_list_type = types.ListType(u8_array_type)

# Then use these types consistently throughout
""")

def create_quick_fix_patch():
    """Create a patch that can be applied immediately."""
    
    patch_content = '''# Quick fix for compilation spikes
# Add this at the top of interpreter_numba.py after imports

# Disable parallel compilation which can cause cache conflicts
os.environ['NUMBA_NUM_THREADS'] = '1'
os.environ['NUMBA_THREADING_LAYER'] = 'sequential'

# Force garbage collection before interpreter runs
import gc
gc.collect()

# Pre-compile critical functions with common signatures
def _precompile_critical_functions():
    """Pre-compile functions that show spikes."""
    import numpy as np
    from numba.typed import List, Dict
    from numba import types
    
    # Create typed test data
    test_starts = np.array([0, 1000, 2000], dtype=np.uint64)
    test_ends = np.array([999, 1999, 2999], dtype=np.uint64)
    test_arrays = List([
        np.zeros(1000, dtype=np.uint8),
        np.zeros(1000, dtype=np.uint8),
        np.zeros(1000, dtype=np.uint8)
    ])
    test_acl = Dict.empty(
        key_type=types.uint64,
        value_type=types.uint64
    )
    
    # Force compilation of memory functions
    try:
        mem_write_jit(np.uint64(100), np.uint64(42), np.uint8(8),
                     test_starts, test_ends, test_arrays, test_acl)
    except:
        pass  # Expected to fail, just need compilation

# Run pre-compilation
_precompile_critical_functions()
'''
    
    return patch_content

if __name__ == "__main__":
    print("Fixing PVM Compilation Spikes")
    print("=" * 60)
    print()
    
    print("The root cause:")
    print("Memory functions are receiving arrays with different types/layouts")
    print("causing Numba to compile new specializations (8-9 second delays).")
    print()
    
    generate_fixes()
    
    print("\n" + "=" * 60)
    print("Quick fix to try immediately:")
    print()
    
    patch = create_quick_fix_patch()
    
    # Save the patch
    patch_file = "/tmp/pvm_spike_fix.patch"
    with open(patch_file, 'w') as f:
        f.write(patch)
    
    print(f"Patch saved to: {patch_file}")
    print()
    print("To apply:")
    print(f"1. Add the contents of {patch_file} to interpreter_numba.py")
    print("2. Clear cache: rm -rf ~/.pyjamaz_numba_cache")
    print("3. Run your program - spikes should be gone")
    
    print("\n" + "=" * 60)
    print("Alternative: Use eager compilation")
    print()
    print("Set NUMBA_EAGER_COMPILE=1 to compile all signatures upfront")
    print("This will make the first import slower but eliminate spikes.")