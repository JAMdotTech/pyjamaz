#!/usr/bin/env python3
"""
Force eager compilation of all critical functions to eliminate runtime spikes.
"""

import os
import sys

# Set environment variables BEFORE importing numba
os.environ['NUMBA_CACHE_DIR'] = os.path.expanduser("~/.pyjamaz_numba_cache")
os.environ['NUMBA_CACHE'] = '1'
os.environ['NUMBA_DISABLE_PERFORMANCE_WARNINGS'] = '1'
os.environ['NUMBA_NUM_THREADS'] = '1'
os.environ['NUMBA_THREADING_LAYER'] = 'sequential'

# Force eager compilation
os.environ['NUMBA_EAGER_COMPILE'] = '1'

print("Forcing eager compilation of PVM interpreter...")
print("This will take a while on first run, but eliminates runtime spikes.")
print()

try:
    # Import the interpreter to trigger compilation
    from pyjamaz.pvm.numba.interpreter_numba import (
        invoke_native, mem_write_jit, mem_read_jit, 
        read_uint_jit, pvm_X_jit, pvm_Z_jit, sbrk_jit
    )
    
    print("✓ Core functions compiled")
    
    # Import the interpreter class
    from pyjamaz.pvm.numba.interpreter_numba import PVMInterpreter
    print("✓ Interpreter class loaded")
    
    print()
    print("Eager compilation complete!")
    print()
    print("To use this in your code, set these environment variables:")
    print("  export NUMBA_EAGER_COMPILE=1")
    print("  export NUMBA_CACHE_DIR=~/.pyjamaz_numba_cache")
    print("  export NUMBA_CACHE=1")
    
except Exception as e:
    print(f"Error during compilation: {e}")
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    print()
    print("You can now run your tests and should see consistent performance.")