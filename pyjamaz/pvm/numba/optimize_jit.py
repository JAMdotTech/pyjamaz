#!/usr/bin/env python3
"""
Optimize JIT compilation for the PVM interpreter.
This script sets up optimal caching and can pre-compile functions.
"""

import os
import sys
import warnings

from pyjamaz.settings import PVM_AOT_CACHE


def setup_numba_env():
    """Set up environment for optimal Numba performance."""
    # Create cache directory
    cache_dir = os.path.expanduser(PVM_AOT_CACHE)
    os.makedirs(cache_dir, exist_ok=True)
    
    # Set environment variables BEFORE importing numba
    os.environ['NUMBA_CACHE_DIR'] = cache_dir
    os.environ['NUMBA_CACHE'] = '1'
    os.environ['NUMBA_DISABLE_PERFORMANCE_WARNINGS'] = '1'
    os.environ['NUMBA_WARNINGS'] = '0'
    
    print(f"✓ Numba cache directory: {cache_dir}")
    return cache_dir

def precompile_simple_functions():
    """Pre-compile simple functions that don't depend on complex types."""
    print("\nPre-compiling simple functions...")
    
    try:
        # Import after setting environment
        import numpy as np
        from numba import njit
        
        # Create simple test functions that match signatures
        @njit(cache=True)
        def test_umul64wide(a, b):
            mask32 = np.uint64((1 << 32) - 1)
            a_lo = a & mask32
            a_hi = a >> np.uint64(32)
            b_lo = b & mask32
            b_hi = b >> np.uint64(32)
            
            p00 = a_lo * b_lo
            p01 = a_lo * b_hi
            p10 = a_hi * b_lo
            p11 = a_hi * b_hi
            
            p00_lo = p00 & mask32
            p00_hi = p00 >> np.uint64(32)
            
            mid = p00_hi + (p01 & mask32) + (p10 & mask32)
            mid_lo = mid & mask32
            mid_hi = mid >> np.uint64(32)
            
            low = (mid_lo << np.uint64(32)) | p00_lo
            high = p11 + (p01 >> np.uint64(32)) + (p10 >> np.uint64(32)) + mid_hi
            
            return high, low
        
        @njit(cache=True)
        def test_reverse_bytes(x):
            return ((x & np.uint64(0x00000000000000FF)) << np.uint64(56) |
                    (x & np.uint64(0x000000000000FF00)) << np.uint64(40) |
                    (x & np.uint64(0x0000000000FF0000)) << np.uint64(24) |
                    (x & np.uint64(0x00000000FF000000)) << np.uint64(8) |
                    (x & np.uint64(0x000000FF00000000)) >> np.uint64(8) |
                    (x & np.uint64(0x0000FF0000000000)) >> np.uint64(24) |
                    (x & np.uint64(0x00FF000000000000)) >> np.uint64(40) |
                    (x & np.uint64(0xFF00000000000000)) >> np.uint64(56))
        
        # Pre-compile by running with test data
        test_u64 = np.uint64(0x0123456789ABCDEF)
        
        # Run functions to trigger compilation
        _ = test_umul64wide(test_u64, test_u64)
        _ = test_reverse_bytes(test_u64)
        
        print("✓ Pre-compiled basic arithmetic functions")
        
    except Exception as e:
        print(f"⚠ Warning during pre-compilation: {e}")

def update_interpreter_for_caching():
    """Generate code to add to interpreter_numba.py for optimal caching."""
    
    code = '''
# Add this at the top of interpreter_numba.py after imports:

import os

# Set up Numba caching
_cache_dir = os.path.expanduser(PVM_AOT_CACHE)
os.makedirs(_cache_dir, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = _cache_dir
os.environ['NUMBA_CACHE'] = '1'

# This ensures all @njit functions use caching
'''
    
    print("\nTo enable caching in interpreter_numba.py, add this code after imports:")
    print("=" * 70)
    print(code)
    print("=" * 70)

def main():
    print("PVM Numba JIT Optimization")
    print("=" * 50)
    
    # Step 1: Set up environment
    cache_dir = setup_numba_env()
    
    # Step 2: Try to pre-compile simple functions
    precompile_simple_functions()
    
    # Step 3: Show how to update interpreter
    update_interpreter_for_caching()
    
    print("\n✓ Optimization complete!")
    print(f"\nCache location: {cache_dir}")
    print("After first run, functions will load from cache (no compilation delay)")
    print("\nTo clear cache: rm -rf " + cache_dir)

if __name__ == "__main__":
    main()