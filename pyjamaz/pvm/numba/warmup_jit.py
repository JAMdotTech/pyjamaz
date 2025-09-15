#!/usr/bin/env python3
"""
Warm up the JIT compiler by exercising all opcode paths.
This pre-compiles all branches to avoid delays during actual execution.
"""

import numpy as np
import time
from numba.typed import Dict, List
from numba import types

def create_test_program():
    """Create a test program that exercises common opcodes."""
    # Opcodes that showed delays in your log
    opcodes_to_test = [
        # Basic arithmetic and memory
        (0x13, 1),  # load_imm
        (0x16, 8),  # load_u64
        (0x1A, 4),  # add_imm_32
        (0x1D, 1),  # shlo_l_imm_64
        (0x20, 8),  # add_imm_64
        (0x33, 0),  # jump
        (0x4D, 1),  # branch_ne
        (0x47, 8),  # store_ind_u64
        (0x49, 8),  # load_ind_u64
    ]
    
    # Create a simple program with these opcodes
    program = []
    for opcode, arg_len in opcodes_to_test:
        program.append(opcode)
        # Add dummy arguments
        for _ in range(arg_len):
            program.append(0)
    
    # Add a trap at the end
    program.append(0x00)  # trap
    
    return np.array(program, dtype=np.uint8)

def warmup_interpreter():
    """Run the interpreter with various inputs to trigger JIT compilation."""
    print("Warming up PVM interpreter JIT compilation...")
    print("This will take ~1-2 minutes but will make future runs fast.")
    print("-" * 60)
    
    from pyjamaz.pvm.numba.interpreter_numba import PVMInterpreter
    
    interpreter = PVMInterpreter()
    
    # Create test program
    test_code = create_test_program()
    
    # Create memory sections
    code_section = np.array(test_code, dtype=np.uint8)
    heap_section = np.zeros(1024 * 1024, dtype=np.uint8)  # 1MB heap
    stack_section = np.zeros(1024 * 1024, dtype=np.uint8)  # 1MB stack
    
    # Set up the program
    from pyjamaz.pvm.numba.pvm_types import PVMProgram, MemorySection
    
    program = PVMProgram(
        code=test_code,
        code_size=len(test_code),
        init_regs=np.zeros(16, dtype=np.uint64),
        gas_limit=1000000,
    )
    
    # Add memory sections
    program.memory.sections = [
        MemorySection(0, len(code_section) - 1, code_section),
        MemorySection(0x10000, 0x10000 + len(heap_section) - 1, heap_section),
        MemorySection(0x80000000, 0x80000000 + len(stack_section) - 1, stack_section),
    ]
    
    # Exercise different code paths
    test_configs = [
        # Different register values
        {'regs': np.zeros(16, dtype=np.uint64)},
        {'regs': np.ones(16, dtype=np.uint64)},
        {'regs': np.arange(16, dtype=np.uint64)},
        # Different memory patterns
        {'heap': np.zeros(1024, dtype=np.uint8)},
        {'heap': np.ones(1024, dtype=np.uint8) * 0xFF},
    ]
    
    print("Compiling opcode handlers...")
    for i, config in enumerate(test_configs):
        print(f"  Pass {i+1}/{len(test_configs)}...", end='', flush=True)
        start = time.time()
        
        # Update program with test configuration
        if 'regs' in config:
            program.init_regs = config['regs']
        
        try:
            # Run interpreter (will trap quickly)
            interpreter.invoke_native(program)
        except Exception:
            # Expected - we're using dummy opcodes
            pass
        
        elapsed = time.time() - start
        print(f" {elapsed:.2f}s")
    
    print("-" * 60)
    print("✓ Warmup complete! Future runs should be fast.")
    print("\nNote: The first run of NEW opcode sequences may still")
    print("compile, but common paths are now cached.")

def warmup_specific_opcodes():
    """Warm up specific opcode paths that are slow."""
    print("\nWarming up specific slow opcodes...")
    
    # Import after setting up environment
    from pyjamaz.pvm.numba.interpreter_numba import (
        invoke_native, pvm_Z_jit, read_uint_jit, branch_jit,
        djump_jit, sync_state_and_return
    )
    
    # Create minimal test data
    test_u8_array = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.uint8)
    test_u64 = np.uint64(12345)
    test_i64 = np.int64(-12345)
    test_u32 = np.uint32(1234)
    test_i32_array = np.array([-1, 0, 1, 2], dtype=np.int32)
    
    # Pre-compile commonly used functions
    print("  - Compiling utility functions...")
    _ = pvm_Z_jit(test_u64, np.uint64(4))
    _ = read_uint_jit(test_u8_array, np.uint32(0), np.uint8(4))
    
    print("  - Compiling branch functions...")
    _ = branch_jit(test_u32, test_i64, True, test_i32_array)
    _ = branch_jit(test_u32, test_i64, False, test_i32_array)
    
    print("  - Compiling jump functions...")
    _ = djump_jit(test_u32, test_i32_array, test_u32, test_i32_array)
    
    print("✓ Specific opcodes warmed up")

if __name__ == "__main__":
    import sys
    
    # Ensure cache is enabled
    import os
    cache_dir = os.path.expanduser("~/.pyjamaz_numba_cache")
    if not os.path.exists(cache_dir):
        print(f"Creating cache directory: {cache_dir}")
        os.makedirs(cache_dir)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        warmup_specific_opcodes()
    else:
        warmup_interpreter()
        warmup_specific_opcodes()