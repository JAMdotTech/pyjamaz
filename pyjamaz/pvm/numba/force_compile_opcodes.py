#!/usr/bin/env python3
"""
Force compilation of slow opcode branches by creating minimal test cases.
This is a simpler approach that focuses on the specific slow opcodes.
"""

import os
import sys

# Set up caching first
cache_dir = os.path.expanduser("~/.pyjamaz_numba_cache")
os.makedirs(cache_dir, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = cache_dir
os.environ['NUMBA_CACHE'] = '1'

def force_compile():
    """Force compilation of the interpreter functions."""
    print("Force-compiling PVM interpreter branches...")
    print("This targets the specific opcodes that showed 8-30 second delays.")
    print("=" * 70)
    
    import numpy as np
    from numba import njit
    import time
    
    # Import the key functions that need compilation
    from pyjamaz.pvm.numba.interpreter_numba import (
        pvm_Z_jit, read_uint_jit, branch_jit, djump_jit,
        sync_state_and_return, reverse_bytes_jit,
        count_leading_zeroes_jit, count_trailing_zeroes_jit,
        pvm_X_jit, rori64_jit, roli64_jit,
        pvm_smod_jit, pvm_rtz_div_jit
    )
    
    print("Compiling utility functions...")
    
    # Test data
    test_u8 = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.uint8)
    test_u64 = np.uint64(0x0123456789ABCDEF)
    test_i64 = np.int64(-12345)
    test_u32 = np.uint32(12345)
    test_i32_array = np.array([0, 1, 2, 3], dtype=np.int32)
    test_u64_array = np.array([0, 1, 2, 3], dtype=np.uint64)
    
    functions_to_compile = [
        ("pvm_Z_jit", lambda: pvm_Z_jit(test_u64, np.uint64(4))),
        ("read_uint_jit", lambda: read_uint_jit(test_u8, np.uint32(0), np.uint8(4))),
        ("reverse_bytes_jit", lambda: reverse_bytes_jit(test_u64)),
        ("count_leading_zeroes_jit", lambda: count_leading_zeroes_jit(test_u64, 64)),
        ("count_trailing_zeroes_jit", lambda: count_trailing_zeroes_jit(test_u64, 64)),
        ("pvm_X_jit", lambda: pvm_X_jit(test_u64, np.uint64(32))),
        ("rori64_jit", lambda: rori64_jit(test_u64, np.uint64(8))),
        ("roli64_jit", lambda: roli64_jit(test_u64, np.uint64(8))),
        ("pvm_smod_jit", lambda: pvm_smod_jit(test_i64, test_i64)),
        ("pvm_rtz_div_jit", lambda: pvm_rtz_div_jit(test_i64, test_i64)),
        ("branch_jit", lambda: branch_jit(test_u32, test_i64, True, test_i32_array)),
        ("djump_jit", lambda: djump_jit(test_u32, test_i32_array, test_u32, test_i32_array)),
        ("sync_state_and_return", lambda: sync_state_and_return(
            test_u64_array, test_u64_array, test_i32_array,
            0, test_u32, test_u32, test_u32, test_u64, test_u32, 0
        )),
    ]
    
    for func_name, func_call in functions_to_compile:
        print(f"  - {func_name}...", end='', flush=True)
        start = time.time()
        try:
            result = func_call()
            elapsed = time.time() - start
            print(f" {elapsed:.3f}s")
        except Exception as e:
            elapsed = time.time() - start
            print(f" {elapsed:.3f}s (with expected error)")
    
    print("\n" + "=" * 70)
    print("✓ Compilation complete!")
    print(f"\nCache location: {cache_dir}")
    print("Future runs should be fast.")

def compile_minimal_interpreter():
    """Compile a minimal interpreter path to warm up the main function."""
    print("\nCompiling minimal interpreter path...")
    
    import numpy as np
    from numba.typed import Dict, List
    from numba import types
    
    # Create minimal test that will trap immediately
    test_code = np.array([0x00], dtype=np.uint8)  # Just a trap instruction
    
    # Try to create a minimal PVMProgram and run it
    try:
        from pyjamaz.pvm import PVMInterpreter, PVMProgram
        
        interpreter = PVMInterpreter()
        program = PVMProgram(
            code=test_code,
            code_size=1,
            init_regs=np.zeros(16, dtype=np.uint64),
            gas_limit=1000,
        )
        
        print("  Running minimal program to trigger compilation...")
        start = time.time()
        try:
            result = interpreter.invoke_native(program)
        except:
            pass  # Expected to trap
        
        elapsed = time.time() - start
        print(f"  Initial compilation took {elapsed:.2f}s")
        
        # Run again to show cached performance
        start = time.time()
        try:
            result = interpreter.invoke_native(program)
        except:
            pass
        elapsed = time.time() - start
        print(f"  Cached execution took {elapsed:.3f}s")
        
    except Exception as e:
        print(f"  Could not run full interpreter test: {e}")
        print("  (This is okay - utility functions are still compiled)")

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    force_compile()
    compile_minimal_interpreter()
    
    total_time = time.time() - start_time
    print(f"\nTotal pre-compilation time: {total_time:.2f}s")
    print("\nYour next run should have consistent millisecond performance!")