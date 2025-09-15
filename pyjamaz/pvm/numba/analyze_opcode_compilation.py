#!/usr/bin/env python3
"""
Analyze which opcodes are causing compilation delays.
This helps identify the specific branches that need pre-compilation.
"""

import os
import sys

# Set up environment
cache_dir = os.path.expanduser("~/.pyjamaz_numba_cache")
os.makedirs(cache_dir, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = cache_dir
os.environ['NUMBA_CACHE'] = '1'

def analyze_opcode_structure():
    """Analyze the opcode if/elif structure to understand compilation patterns."""
    print("Analyzing PVM opcode structure...")
    print("=" * 70)
    
    from pyjamaz.pvm.constants import (
        inst_none, inst_one_reg, inst_one_reg_one_imm, 
        inst_offset, inst_two_reg, inst_two_reg_one_imm,
        inst_two_reg_one_off, inst_two_reg_two_imm,
        inst_three_reg
    )
    
    # Map instruction types to their complexity
    inst_type_names = {
        inst_none: "inst_none",
        inst_one_reg: "inst_one_reg", 
        inst_one_reg_one_imm: "inst_one_reg_one_imm",
        inst_offset: "inst_offset",
        inst_two_reg: "inst_two_reg",
        inst_two_reg_one_imm: "inst_two_reg_one_imm",
        inst_two_reg_one_off: "inst_two_reg_one_off",
        inst_two_reg_two_imm: "inst_two_reg_two_imm",
        inst_three_reg: "inst_three_reg"
    }
    
    # Opcodes that showed delays in your log
    slow_opcodes = {
        0x13: ("load_imm", 7.93),
        0x1A: ("add_imm_32", 7.99),
        0x1D: ("shlo_l_imm_64", 8.44),
        0x33: ("jump", 30.56),
        0x4D: ("branch_ne", 8.24),
    }
    
    print("Opcodes with compilation delays:")
    for opcode, (name, delay) in slow_opcodes.items():
        print(f"  {name:15} (0x{opcode:02X}): {delay:.2f}s")
    
    print("\nThese delays occur because:")
    print("1. Each instruction type has its own if/elif branch")
    print("2. Within each type, there are nested if/elif for specific opcodes")
    print("3. Numba compiles each branch only when first executed")
    print("4. The 'jump' opcode (30s) likely has the most complex implementation")
    
    return slow_opcodes

def suggest_warmup_sequence():
    """Suggest a warmup sequence to pre-compile all branches."""
    print("\n" + "=" * 70)
    print("Recommended warmup approach:")
    print("\n1. Create a test program that uses each slow opcode:")
    
    warmup_code = """
# Warmup program to trigger compilation of all branches
test_program = [
    # Basic loads and arithmetic
    0x13, 0x01, 0x00, 0x00, 0x00,  # load_imm r1, 0
    0x1A, 0x01, 0x01, 0x00, 0x00,  # add_imm_32 r1, 1
    0x1D, 0x01, 0x01,              # shlo_l_imm_64 r1, 1
    
    # Jumps and branches  
    0x33, 0x05, 0x00, 0x00, 0x00,  # jump +5
    0x00,                          # trap (skipped)
    0x4D, 0x01, 0x00, 0x00, 0x00,  # branch_ne r1, 0
    
    # Other frequently used opcodes
    0x16, 0x02, 0x00,              # load_u64 r2, [r0]
    0x20, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # add_imm_64
    
    0x00,  # trap (end)
]
"""
    print(warmup_code)
    
    print("\n2. Run this before your actual workload")
    print("3. The first run will be slow (compiling)")
    print("4. Subsequent runs will be fast (cached)")

def check_cache_status():
    """Check the current cache status."""
    print("\n" + "=" * 70)
    print("Cache status:")
    
    cache_dir = os.environ.get('NUMBA_CACHE_DIR', '~/.numba_cache')
    cache_dir = os.path.expanduser(cache_dir)
    
    if os.path.exists(cache_dir):
        # Count cached files
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
                file_count += 1
        
        print(f"  Cache directory: {cache_dir}")
        print(f"  Cached files: {file_count}")
        print(f"  Total size: {total_size / 1024 / 1024:.2f} MB")
    else:
        print(f"  Cache directory does not exist: {cache_dir}")
        print("  No functions have been cached yet")

if __name__ == "__main__":
    slow_opcodes = analyze_opcode_structure()
    suggest_warmup_sequence()
    check_cache_status()
    
    print("\n" + "=" * 70)
    print("Next steps:")
    print("1. Run a warmup program with all opcodes you'll use")
    print("2. Make sure NUMBA_CACHE=1 is set")
    print("3. Consider using @njit(cache=True, parallel=True) for invoke_native")
    print("   if you have multiple cores available")