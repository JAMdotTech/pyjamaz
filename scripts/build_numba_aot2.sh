#!/usr/bin/env bash
set -uo pipefail

echo "=============================================="
echo " Building Numba AOT PVM interpreter (AOT2)    "
echo "=============================================="

# Enable verbose tracing when DEBUG=1 is set in the environment
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/.."
NUMBA_DIR="$SCRIPT_DIR/pyjamaz/pvm/numba"

echo "Script dir: $SCRIPT_DIR"
echo "Numba dir : $NUMBA_DIR"

echo
echo "Cleaning old builds/caches..."
# Safe even if there are no matches (zsh-friendly)
find "$NUMBA_DIR" -type f \( -name 'interpreter_numba_entry_aot*.so' -o -name 'interpreter_numba_entry_aot*.pyd' -o -name 'interpreter_numba_entry_aot*.dylib' -o -name 'interpreter_numba_entry_aot*.dll' -o -name 'interpreter_numba_entry_aot*.o' -o -name 'interpreter_numba_entry_aot*.c' \) -delete 2>/dev/null || true
rm -rf "$NUMBA_DIR/__pycache__" 2>/dev/null || true

echo
echo "Compiling interpreter_numba_entry_aot..."
echo "Started at: $(date)"
if python -m pyjamaz.pvm.numba.interpreter_numba_entry_aot; then
  echo "✓ AOT build completed successfully"
else
  echo "⚠️  AOT build failed (continuing shell session)"
fi
echo "Finished at: $(date)"

echo
echo "Listing built files..."
found="$(find "$NUMBA_DIR" -maxdepth 1 -type f -name 'interpreter_numba_entry_aot*' -print)"
if [ -n "$found" ]; then
  ls -lh $found
else
  echo "No artifacts built yet"
fi

# Keep the terminal open if this is an interactive TTY
if [ -t 1 ]; then
  echo
  read -r -p "Press ENTER to close this window..." _
fi