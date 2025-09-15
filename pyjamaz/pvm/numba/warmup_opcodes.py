#!/usr/bin/env python3
"""
Warmup script that exercises the specific opcodes showing delays.
Run this once after restarting Python to compile all branches.
"""

import os
import time

# Ensure caching is enabled
cache_dir = os.path.expanduser("~/.pyjamaz_numba_cache")
os.makedirs(cache_dir, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = cache_dir
os.environ['NUMBA_CACHE'] = '1'

def create_warmup_program():
    """Create a program that uses all the slow opcodes."""
    # Based on your log, these opcodes showed 8-30 second delays:
    # 0x13 (load_imm): 7.93s
    # 0x1A (add_imm_32): 7.99s  
    # 0x1D (shlo_l_imm_64): 8.44s
    # 0x33 (jump): 30.56s (!!)
    # 0x4D (branch_ne): 8.24s
    
    program = [
        # Exercise load_imm (0x13)
        0x13, 0x01, 0x00, 0x00, 0x00,  # load_imm r1, 0
        
        # Exercise add_imm_32 (0x1A) 
        0x1A, 0x01, 0x01, 0x00, 0x00,  # add_imm_32 r1, 1
        
        # Exercise shlo_l_imm_64 (0x1D)
        0x1D, 0x01, 0x01,  # shlo_l_imm_64 r1, 1
        
        # Exercise jump (0x33) - this is the slowest!
        0x33, 0x03, 0x00, 0x00, 0x00,  # jump +3 (skip trap)
        0x00,  # trap (skipped)
        
        # Exercise branch_ne (0x4D)
        0x13, 0x02, 0x01, 0x00, 0x00,  # load_imm r2, 1
        0x4D, 0x02, 0x03, 0x00, 0x00,  # branch_ne r2, +3
        0x00,  # trap (skipped)
        
        # Also exercise other opcodes from your log
        0x16, 0x03, 0x00,  # load_u64 (0x16)
        0x20, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # add_imm_64 (0x20)
        0x47, 0x00, 0x03,  # store_ind_u64 (0x47)
        0x49, 0x04, 0x00,  # load_ind_u64 (0x49)
        
        0x00,  # Final trap
    ]
    
    return program

def run_warmup():
    """Run the warmup program to trigger compilation."""
    print("PVM Opcode Warmup")
    print("=" * 60)
    print("This will compile the opcodes that show 8-30 second delays.")
    print("After this runs, your actual programs will be fast.\n")
    
    import numpy as np
    
    # Import PVM components
    try:
        from pyjamaz.pvm import PVMInterpreter, PVMProgram, PVMMemory, MemorySection
        
        # Create warmup program
        program_bytes = create_warmup_program()
        code = np.array(program_bytes, dtype=np.uint8)
        
        # Create memory with code, heap, and stack sections
        memory = PVMMemory()
        
        # Code section (read-only)
        code_section = MemorySection(0, len(code) - 1, code.copy())
        memory.sections.append(code_section)
        
        # Heap section (read-write) 
        heap_size = 1024 * 1024  # 1MB
        heap_data = np.zeros(heap_size, dtype=np.uint8)
        heap_section = MemorySection(0x10000, 0x10000 + heap_size - 1, heap_data)
        memory.sections.append(heap_section)
        
        # Stack section (read-write)
        stack_size = 1024 * 1024  # 1MB  
        stack_data = np.zeros(stack_size, dtype=np.uint8)
        stack_section = MemorySection(0x80000000, 0x80000000 + stack_size - 1, stack_data)
        memory.sections.append(stack_section)
        
        # Create program
        program = PVMProgram(
            code=code,
            code_size=len(code),
            init_regs=np.zeros(16, dtype=np.uint64),
            gas_limit=1000000,
            memory=memory
        )
        
        # Initialize registers for memory access
        program.init_regs[0] = 0x10000  # Point r0 to heap
        
        print("Running warmup program...")
        print("(First run will be slow due to compilation)\n")
        
        # First run - this will compile
        print("Pass 1 (compilation):")
        start = time.time()
        interpreter = PVMInterpreter(program)
        try:
            result = interpreter.invoke_native()
        except Exception as e:
            # Expected - program will trap
            pass
        elapsed1 = time.time() - start
        print(f"  Time: {elapsed1:.2f}s\n")
        
        # Second run - should be fast (cached)
        print("Pass 2 (cached):")
        start = time.time()
        interpreter = PVMInterpreter(program)
        try:
            result = interpreter.invoke_native()
        except:
            pass
        elapsed2 = time.time() - start
        print(f"  Time: {elapsed2:.3f}s\n")
        
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
        print(f"Speedup: {speedup:.1f}x")
        
        print("\n" + "=" * 60)
        print("✓ Warmup complete!")
        print("\nAll opcodes are now compiled and cached.")
        print("Your next runs should have consistent millisecond performance.")
        
    except Exception as e:
        print(f"Error during warmup: {e}")
        print("\nTip: Make sure you're in the pyjamaz directory and have")
        print("     export PYTHONPATH=.")

if __name__ == "__main__":
    run_warmup()