# AOT Compilation for Numba PVM Interpreter

## Issue with NumPy Version

Your current environment has NumPy 2.3, but Numba requires NumPy 2.2 or less. 

## Solutions:

### Option 1: Downgrade NumPy (Recommended)
```bash
pip install "numpy<2.3"
```

### Option 2: Create a separate environment for AOT compilation
```bash
# Create new environment
python -m venv aot_env
source aot_env/bin/activate  # On Windows: aot_env\Scripts\activate

# Install compatible versions
pip install "numpy<2.3" numba

# Build AOT modules
cd pyjamaz/pvm/numba
./build_aot.sh

# Copy generated .so/.pyd files to your main environment
cp *.so ../../../  # Or wherever you need them
```

### Option 3: Use Docker for compilation
Create a Dockerfile:
```dockerfile
FROM python:3.12
RUN pip install "numpy<2.3" numba
WORKDIR /app
COPY pvm_numba_aot*.py ./
RUN python pvm_numba_aot.py && python pvm_numba_aot2.py
```

## Quick Fix for Your Issue

Since you're experiencing JIT compilation delays, here's a simpler approach:

1. **Use eager compilation** - Add this to your code before importing the interpreter:
```python
import os
os.environ['NUMBA_CACHE_DIR'] = '/path/to/cache'  # Persistent cache
os.environ['NUMBA_CACHE'] = '1'  # Enable caching
```

2. **Pre-warm the JIT** - Run a small test before your main code:
```python
from pyjamaz.pvm.numba import interpreter_numba

# Create minimal test data
test_code = np.array([0], dtype=np.uint8)
# ... other test data ...

# Run interpreter once to trigger compilation
interpreter = interpreter_numba.PVMInterpreter()
# Run a minimal test to compile all functions
```

3. **Use the precompile script I created**:
```python
python pyjamaz/pvm/numba/precompile_interpreter.py
```

This will compile most functions before your actual runs.

## Alternative: Pure JIT with Better Caching

Instead of AOT, you can improve JIT performance:

1. Set environment variables:
```bash
export NUMBA_CACHE_DIR=~/.numba_cache
export NUMBA_CACHE=1
export NUMBA_DISABLE_PERFORMANCE_WARNINGS=1
```

2. The cache will persist between runs, eliminating most compilation delays after the first run.

## Files Created for AOT

- `pvm_numba_aot.py` - Basic arithmetic and utility functions
- `pvm_numba_aot2.py` - Memory operations
- `aot_loader.py` - Loads AOT functions with JIT fallback
- `build_aot.sh` - Build script
- `setup.py` - Setup script for building

Once you fix the NumPy version issue, you can build and use the AOT modules as described in the build script.