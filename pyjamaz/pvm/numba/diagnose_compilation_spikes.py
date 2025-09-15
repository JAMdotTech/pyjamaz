#!/usr/bin/env python3
"""
Diagnose why certain opcodes still show compilation spikes after caching.
"""

import os
import sys

def analyze_spike_pattern():
    """Analyze the pattern of compilation spikes."""
    
    # Opcodes showing spikes from your log
    spike_data = [
        (33, "store_u64", 8.446),
        (56, "set_lt_u", 9.791),
        (59, "move_reg", 8.712),
        (110, "store_imm_ind_u32", 9.335),
    ]
    
    print("Opcodes with compilation spikes:")
    print("=" * 60)
    for inst_num, opcode, duration in spike_data:
        print(f"  {inst_num:3d} {opcode:20s} {duration:.3f}s")
    
    print("\nPossible causes:")
    print("1. These opcodes access memory with different layouts")
    print("2. Type specialization for different array types")
    print("3. First-time compilation of error handling paths")
    print("4. Cache eviction or corruption")

def check_numba_diagnostics():
    """Enable Numba diagnostics to understand compilation."""
    print("\n" + "=" * 60)
    print("To diagnose further, run with these environment variables:")
    print()
    print("export NUMBA_DEBUG_CACHE=1")
    print("export NUMBA_DEBUG_TYPEINFER=1") 
    print("export NUMBA_DEVELOPER_MODE=1")
    print("export NUMBA_DUMP_CFG=1")
    print()
    print("This will show when and why Numba compiles functions.")

def suggest_fixes():
    """Suggest fixes for the compilation spikes."""
    print("\n" + "=" * 60)
    print("Fixes to try:")
    print()
    print("1. Force single type signatures:")
    print("   Add explicit signatures to problematic functions")
    print()
    print("2. Disable specialization for memory functions:")
    print("   Use @njit(cache=True, forceobj=False, nogil=True)")
    print()
    print("3. Pre-compile with all memory layouts:")
    print("   Run warmup with different memory configurations")
    print()
    print("4. Check cache integrity:")
    print("   Clear cache and rebuild: rm -rf ~/.pyjamaz_numba_cache")

def create_diagnostic_patch():
    """Create a patch to add diagnostics to the interpreter."""
    
    patch = '''
# Add this to interpreter_numba.py to diagnose compilation

import functools
import time

def diagnose_compilation(func_name):
    """Decorator to track compilation times."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            if elapsed > 1.0:  # Log slow compilations
                print(f"SLOW: {func_name} took {elapsed:.2f}s")
            return result
        return wrapper
    return decorator

# Apply to memory functions that show spikes:
# @diagnose_compilation("mem_write_jit")
# @njit(cache=True)
# def mem_write_jit(...):
'''
    
    print("\n" + "=" * 60)
    print("Diagnostic patch for tracking slow compilations:")
    print(patch)

def analyze_memory_access_patterns():
    """Analyze why memory opcodes specifically are slow."""
    print("\n" + "=" * 60)
    print("Memory-related opcodes analysis:")
    print()
    print("The spikes occur in memory operations:")
    print("- store_u64")
    print("- store_imm_ind_u32")
    print("- set_lt_u (may access memory for comparison)")
    print("- move_reg (may involve memory barriers)")
    print()
    print("This suggests the issue is with memory access patterns")
    print("triggering recompilation for different:")
    print("- Array strides")
    print("- Memory section configurations")
    print("- Alignment requirements")

if __name__ == "__main__":
    print("PVM Compilation Spike Diagnosis")
    print("=" * 60)
    print()
    
    analyze_spike_pattern()
    analyze_memory_access_patterns()
    check_numba_diagnostics()
    suggest_fixes()
    create_diagnostic_patch()
    
    print("\n" + "=" * 60)
    print("Immediate action:")
    print("1. Clear the cache: rm -rf ~/.pyjamaz_numba_cache")
    print("2. Run with NUMBA_DEBUG_CACHE=1 to see what's compiling")
    print("3. Consider using fixed signatures for memory functions")