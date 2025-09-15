#!/usr/bin/env python3
"""
Warmup script specifically targeting opcodes that show compilation spikes.
"""

import os
import sys
import time
import numpy as np

# Ensure cache is enabled
cache_dir = os.path.expanduser("~/.pyjamaz_numba_cache")
os.makedirs(cache_dir, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = cache_dir
os.environ['NUMBA_CACHE'] = '1'

def create_targeted_warmup_program():
    """Create a program that specifically exercises the slow opcodes."""
    # These opcodes showed spikes in your latest log:
    # store_u64 (0x2A): 0.57s
    # set_lt_u (0x56): 0.43s  
    # move_reg (0x3B): 0.36s
    # store_imm_ind_u32 (0x6E): 0.35s
    
    program = []
    
    # Initialize some registers with values
    # load_imm r0, 0x1000 (memory address)
    program.extend([0x13, 0x00, 0x00, 0x10, 0x00, 0x00])  
    # load_imm r1, 0x12345678
    program.extend([0x13, 0x01, 0x78, 0x56, 0x34, 0x12])
    # load_imm r2, 0x87654321  
    program.extend([0x13, 0x02, 0x21, 0x43, 0x65, 0x87])
    
    # Exercise store_u64 (0x2A) - stores full 64-bit value
    # This seems to be the slowest, let's do it multiple times with different registers
    program.extend([0x2A, 0x01, 0x00, 0x10, 0x00, 0x00])  # store_u64 [0x1000], r1
    program.extend([0x2A, 0x02, 0x08, 0x10, 0x00, 0x00])  # store_u64 [0x1008], r2
    
    # Exercise set_lt_u (0x56) - unsigned less than comparison
    # set_lt_u r3, r1, r2
    program.extend([0x56, 0x13, 0x02])  
    # set_lt_u r4, r2, r1  
    program.extend([0x56, 0x24, 0x01])
    
    # Exercise move_reg (0x3B) - register to register move
    # move_reg r5, r1
    program.extend([0x3B, 0x05, 0x01])
    # move_reg r6, r2
    program.extend([0x3B, 0x06, 0x02])
    
    # Exercise store_imm_ind_u32 (0x6E) - store immediate indirect u32
    # store_imm_ind_u32 [r0+0x10], 0xABCDEF
    program.extend([0x6E, 0x00, 0x10, 0x00, 0x00, 0x00, 0xEF, 0xCD, 0xAB, 0x00])
    # store_imm_ind_u32 [r0+0x14], 0xFEDCBA
    program.extend([0x6E, 0x00, 0x14, 0x00, 0x00, 0x00, 0xBA, 0xDC, 0xFE, 0x00])
    
    # Also exercise some other opcodes that showed moderate spikes
    # cmov_iz (0x5C) - conditional move if zero
    program.extend([0x5C, 0x37, 0x04])  # cmov_iz r7, r3, r4
    
    # store_ind_u32 (0x47) - store indirect u32  
    program.extend([0x47, 0x01, 0x00, 0x20, 0x00, 0x00, 0x00])  # store_ind_u32 [r0+0x20], r1
    
    # load_ind_i32 (0x4A) - load indirect signed 32
    program.extend([0x4A, 0x08, 0x00, 0x20, 0x00, 0x00, 0x00])  # load_ind_i32 r8, [r0+0x20]
    
    # Final trap
    program.append(0x00)
    
    return program

def run_targeted_warmup():
    """Run the warmup focusing on problematic opcodes."""
    print("PVM Targeted Opcode Warmup")
    print("=" * 60)
    print("Targeting opcodes with compilation spikes:")
    print("  - store_u64 (0.57s spike)")
    print("  - set_lt_u (0.43s spike)")
    print("  - move_reg (0.36s spike)")
    print("  - store_imm_ind_u32 (0.35s spike)")
    print()
    
    try:
        from pyjamaz.pvm import PVMInterpreter, PVMProgram, PVMMemory, MemorySection
        
        # Create warmup program
        program_bytes = create_targeted_warmup_program()
        code = np.array(program_bytes, dtype=np.uint8)
        
        # Create memory with larger sections to avoid bounds issues
        memory = PVMMemory()
        
        # Code section (read-only)
        code_section = MemorySection(0, len(code) - 1, code.copy())
        memory.sections.append(code_section)
        
        # Large heap section (read-write) for memory operations
        heap_size = 16 * 1024 * 1024  # 16MB to ensure all addresses are valid
        heap_data = np.zeros(heap_size, dtype=np.uint8)
        heap_section = MemorySection(0x1000, 0x1000 + heap_size - 1, heap_data)
        memory.sections.append(heap_section)
        
        # Stack section (read-write)
        stack_size = 4 * 1024 * 1024  # 4MB
        stack_data = np.zeros(stack_size, dtype=np.uint8)
        stack_section = MemorySection(0x80000000, 0x80000000 + stack_size - 1, stack_data)
        memory.sections.append(stack_section)
        
        # Create program
        program = PVMProgram(
            code=code,
            code_size=len(code),
            init_regs=np.zeros(16, dtype=np.uint64),
            gas_limit=10000000,
            memory=memory
        )
        
        print("Running warmup passes...")
        print()
        
        # Run multiple passes to ensure all paths are compiled
        for pass_num in range(3):
            print(f"Pass {pass_num + 1}:")
            start = time.time()
            interpreter = PVMInterpreter(program)
            try:
                result = interpreter.invoke_native()
            except Exception as e:
                # Expected - program will trap
                pass
            elapsed = time.time() - start
            print(f"  Time: {elapsed:.3f}s")
            
            if pass_num == 0 and elapsed < 1.0:
                print("  Warning: First pass was too fast, compilation may not have occurred")
        
        print()
        print("=" * 60)
        print("✓ Targeted warmup complete!")
        print()
        print("The problematic opcodes should now be compiled and cached.")
        print("Run your test again to see if the spikes are gone.")
        
    except Exception as e:
        print(f"Error during warmup: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Make sure you're in the pyjamaz directory with PYTHONPATH=.")

if __name__ == "__main__":
    run_targeted_warmup()