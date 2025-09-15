#!/bin/bash
# Build script for AOT compilation of Numba PVM interpreter functions

echo "Building Numba AOT modules for PVM interpreter..."
echo "================================================"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Clean old builds
echo "Cleaning old builds..."
rm -f *.so *.pyd *.dll pvm_numba_aot*.c pvm_numba_aot*.h

# Build AOT modules
echo ""
echo "Building pvm_numba_aot..."
python pvm_numba_aot.py
if [ $? -eq 0 ]; then
    echo "✓ pvm_numba_aot built successfully"
else
    echo "✗ Failed to build pvm_numba_aot"
    exit 1
fi

echo ""
echo "Building pvm_numba_aot2..."
python pvm_numba_aot2.py
if [ $? -eq 0 ]; then
    echo "✓ pvm_numba_aot2 built successfully"
else
    echo "✗ Failed to build pvm_numba_aot2"
    exit 1
fi

# Build AOT core loop
echo ""
echo "Building pvm_numba_aot_invoke..."
python pvm_numba_aot_invoke.py
if [ $? -eq 0 ]; then
    echo "✓ pvm_numba_aot_invoke built successfully"
else
    echo "✗ Failed to build pvm_numba_aot_invoke"
    exit 1
fi

# List generated files
echo ""
echo "Generated files:"
ls -la *.so *.pyd *.dll 2>/dev/null || echo "No shared libraries found"

echo ""
echo "Build complete! You can now use the AOT compiled functions."
echo ""
echo "To use in your code:"
echo "  from pyjamaz.pvm.numba import interpreter_numba_aot"
echo ""
echo "The interpreter will automatically use AOT functions if available."
