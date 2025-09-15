"""
Example showing how to modify interpreter_numba.py to use AOT compiled functions.

Add this code at the beginning of interpreter_numba.py after the imports:
"""

# === ADD THIS TO interpreter_numba.py AFTER IMPORTS ===

# Try to load AOT compiled functions
try:
    from .aot_loader import get_function, AOT_AVAILABLE
    
    if AOT_AVAILABLE:
        print("Using AOT compiled functions for better performance")
        
        # Replace JIT functions with AOT versions
        # The pattern is: function_name = get_function('function_name', original_jit_function)
        
        # Example for umul64wide:
        # Original:
        # @njit(cache=True)
        # def umul64wide(a: U64, b: U64):
        #     ...
        
        # With AOT:
        def _umul64wide_jit(a: U64, b: U64):
            # Original implementation
            pass
        
        umul64wide = get_function('umul64wide', njit(cache=True)(_umul64wide_jit))
        
except ImportError:
    print("AOT modules not available, using JIT compilation")
    # Continue with normal JIT compilation

# === ALTERNATIVE APPROACH: Full replacement pattern ===

"""
For a cleaner approach, you can wrap each function definition like this:
"""

from functools import wraps

def aot_or_jit(func_name):
    """Decorator that uses AOT if available, otherwise JIT."""
    def decorator(func):
        # Try to get AOT version
        try:
            from .aot_loader import get_function, AOT_AVAILABLE
            if AOT_AVAILABLE:
                return get_function(func_name, njit(cache=True)(func))
        except:
            pass
        
        # Fall back to JIT
        return njit(cache=True)(func)
    
    return decorator

# Then use it like:
# @aot_or_jit('umul64wide')
# def umul64wide(a: U64, b: U64):
#     ... original implementation ...

# === USAGE INSTRUCTIONS ===

"""
To use AOT compilation:

1. Build the AOT modules:
   cd pyjamaz/pvm/numba
   ./build_aot.sh
   
   Or manually:
   python pvm_numba_aot.py
   python pvm_numba_aot2.py

2. Modify interpreter_numba.py to use the AOT loader as shown above

3. The interpreter will automatically use AOT functions if available,
   falling back to JIT if not.

Benefits:
- No JIT compilation delay on first run
- Consistent performance from the start
- Can distribute pre-compiled binaries
- Works with all existing code unchanged
"""