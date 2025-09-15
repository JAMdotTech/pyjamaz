"""
Loader module for AOT compiled functions.
This module attempts to load AOT compiled functions and falls back to JIT if needed.
"""

import os
import sys
import warnings
from numba import njit

# Flag to track if AOT is available
AOT_AVAILABLE = False
AOT_FUNCTIONS = {}
REQUIRE_AOT = os.environ.get('PVM_AOT_ONLY', '0') == '1'

def load_aot_modules():
    """Try to load AOT compiled modules."""
    global AOT_AVAILABLE, AOT_FUNCTIONS
    
    # Add current directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    try:
        # Try to import AOT modules
        import pvm_numba_aot
        import pvm_numba_aot2
        import pvm_numba_aot_invoke
        
        # Map function names to AOT implementations (safe subset only)
        AOT_FUNCTIONS = {
            # Scalar/array helpers with matching signatures
            'umul64wide': pvm_numba_aot.umul64wide,
            'imul64wide': pvm_numba_aot.imul64wide,
            'smul_u64wide': pvm_numba_aot.smul_u64wide,
            'rori64_jit': pvm_numba_aot.rori64_jit,
            'roli64_jit': pvm_numba_aot.roli64_jit,
            'rori32_jit': pvm_numba_aot.rori32_jit,
            'roli32_jit': pvm_numba_aot.roli32_jit,
            'pvm_smod_jit': pvm_numba_aot.pvm_smod_jit,
            'pvm_rtz_div_jit': pvm_numba_aot.pvm_rtz_div_jit,
            'pvm_X_jit': pvm_numba_aot.pvm_X_jit,
            'pvm_Z_jit': pvm_numba_aot.pvm_Z_jit,
            'count_leading_zeroes_jit': pvm_numba_aot.count_leading_zeroes_jit,
            'count_trailing_zeroes_jit': pvm_numba_aot.count_trailing_zeroes_jit,
            'reverse_bytes_jit': pvm_numba_aot.reverse_bytes_jit,
            'read_uint_jit': pvm_numba_aot.read_uint_jit,
            'riscv_div_jit': pvm_numba_aot.riscv_div_jit,
            'pvm_Z_inv_jit': pvm_numba_aot.pvm_Z_inv_jit,
            'find_memory_section_jit': pvm_numba_aot.find_memory_section_jit,
            '_fmix64_jit': pvm_numba_aot._fmix64_jit,
            'hash_memory_segment': pvm_numba_aot.hash_memory_segment,
            # From pvm_numba_aot2 (memory + complex helpers with matching signatures)
            'mem_write_jit': pvm_numba_aot2.mem_write_jit,
            'mem_read_jit': pvm_numba_aot2.mem_read_jit,
            'get_memory_hash': pvm_numba_aot2.get_memory_hash,
            'sbrk_jit': pvm_numba_aot2.sbrk_jit,
            'djump_jit': pvm_numba_aot2.djump_jit,
        }
        
        # AOT core loop (optional but required if PVM_AOT_ONLY=1)
        AOT_FUNCTIONS['invoke_native'] = pvm_numba_aot_invoke.invoke_native
        
        AOT_AVAILABLE = True
        print("Successfully loaded AOT compiled functions")
        return True
        
    except ImportError as e:
        if REQUIRE_AOT:
            raise ImportError(f"PVM_AOT_ONLY=1 set but AOT modules not available: {e}")
        warnings.warn(f"AOT modules not available: {e}. Using JIT compilation.")
        return False

def get_function(name, jit_fallback):
    """
    Get a function by name, using AOT if available, otherwise JIT.
    
    Args:
        name: Function name
        jit_fallback: The JIT compiled function to use as fallback
    
    Returns:
        The AOT or JIT function
    """
    if AOT_AVAILABLE and name in AOT_FUNCTIONS:
        aot_func = AOT_FUNCTIONS[name]
        
        # For functions with default parameters, wrap them
        if name in ['count_leading_zeroes_jit', 'count_trailing_zeroes_jit']:
            # Create a wrapper that provides the default value
            def wrapper(value, max_bits=64):
                return aot_func(value, max_bits)
            return wrapper
        
        return aot_func
    if REQUIRE_AOT:
        raise RuntimeError(f"PVM_AOT_ONLY=1 set but no AOT implementation for '{name}'")
    return jit_fallback

# Load AOT modules on import
load_aot_modules()
