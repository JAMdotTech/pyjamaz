#!/usr/bin/env bash
set -uo pipefail

echo " Building Numba AOT PVM interpreter           "

# Enable verbose tracing when DEBUG=1 is set in the environment
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/.."
NUMBA_DIR="$SCRIPT_DIR/pyjamaz/pvm/interpreters/numba"

# Match CPU between build & run
export NUMBA_CPU_NAME=generic
# Where to write/read the cache
#export NUMBA_CACHE_DIR=/app/numba-cache
# Cache-only, but allow warmup compiles
export NUMBA_CACHE_ONLY=1
export NUMBA_CACHE_WARMUP=1
unset NUMBA_DISABLE_JIT

export PVM_INTERPRETER=NUMBA_AOT_COMPILE

echo "Script dir: $SCRIPT_DIR"
echo "Numba dir : $NUMBA_DIR"

echo
echo "Compiling interpreter_numba_aot..."
echo "Started at: $(date)"
if python -m pyjamaz.pvm.interpreters.numba.interpreter_numba_aot_ffi; then
  echo "✓ AOT build completed successfully"
else
  echo "⚠️  AOT build failed (continuing shell session)"
fi
echo "Finished at: $(date)"


unset NUMBA_CPU_NAME
unset NUMBA_CACHE_ONLY
unset NUMBA_CACHE_WARMUP
unset NUMBA_DISABLE_JIT
#unset PVM_INTERPRETER


echo
echo "Listing built files..."
found="$(find "$NUMBA_DIR" -maxdepth 1 -type f -name 'interpreter_numba_aot_ffi*' -print)"
if [ -n "$found" ]; then
  ls -lh $found
else
  echo "No artifacts built yet"
fi

