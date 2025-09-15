#!/usr/bin/env python3
"""
Enable persistent Numba caching to avoid JIT compilation delays.
Run this before using the interpreter to set up caching.
"""

import os
import sys

from pyjamaz.settings import PVM_AOT_CACHE


def setup_numba_cache():
    """Configure Numba for optimal caching."""
    
    # Set cache directory
    cache_dir = os.path.expanduser(PVM_AOT_CACHE)
    os.makedirs(cache_dir, exist_ok=True)
    
    # Set environment variables
    os.environ['NUMBA_CACHE_DIR'] = cache_dir
    os.environ['NUMBA_CACHE'] = '1'
    os.environ['NUMBA_DISABLE_PERFORMANCE_WARNINGS'] = '1'
    
    print(f"Numba cache enabled at: {cache_dir}")
    print("After first run, functions will load from cache (no compilation delay)")
    
    # Import numba to ensure settings take effect
    try:
        import numba
        print(f"Numba version: {numba.__version__}")
    except ImportError:
        print("Warning: Numba not installed")
    
    return cache_dir

def clear_cache():
    """Clear the Numba cache if needed."""
    cache_dir = os.path.expanduser(PVM_AOT_CACHE)
    if os.path.exists(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
        print(f"Cleared cache at: {cache_dir}")
    else:
        print("No cache to clear")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_cache()
    else:
        setup_numba_cache()
        print("\nTo clear cache, run: python enable_cache.py clear")