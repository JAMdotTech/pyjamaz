#!/bin/bash

echo "Building Numba AOT PVM interpreter (warm-up compile)"
echo "====================================================="

SCRIPT_DIR="$( cd -- "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

NUMBA_DIR="${SCRIPT_DIR}/pyjamaz/pvm/numba/__pycache__"

echo "Script dir: ${SCRIPT_DIR}"
echo "Numba dir : ${NUMBA_DIR}"

if [ ! -d "${NUMBA_DIR}" ]; then
  echo "✗ Numba directory not found at ${NUMBA_DIR}"
  # Do not exit the terminal session; just return a non-zero code from the script
  return 1 2>/dev/null || exit 1
fi

echo ""
echo "Cleaning old builds/caches..."
( cd "${NUMBA_DIR}" && rm -f *.so *.pyd *.dll interpreter_numba_aot*.c interpreter_numba_aot*.h ) || true


echo ""
echo "Warming up JIT cache via pyjamaz.pvm.numba.aot ..."
python -m pyjamaz.pvm.numba.aot || true
#python -c "import aot_build as m" || true
AOT_RC=$?
if [ $AOT_RC -eq 0 ]; then
    echo "✓ AOT warm-up completed successfully"
else
    echo "⚠️  AOT warm-up failed with exit code $AOT_RC (continuing)"
    :
fi

echo ""
echo "Cached files (if any):"
ls -la "${NUMBA_DIR}/__pycache__" 2>/dev/null || echo "No __pycache__ found yet"

echo ""
echo "Done."
