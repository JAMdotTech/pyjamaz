#!/usr/bin/env bash
set -euo pipefail

echo " Building Numba AOT PVM interpreter           "

# Enable verbose tracing when DEBUG=1 is set in the environment
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/.."
cd "$SCRIPT_DIR"

# Match CPU between build & run
export NUMBA_CPU_NAME=generic
export NUMBA_CPU_FEATURES=""
# Cache-only, but allow warmup compiles
export NUMBA_CACHE_ONLY=1
export NUMBA_CACHE_WARMUP=1
unset NUMBA_DISABLE_JIT

export PVM_INTERPRETER=NUMBA_AOT_COMPILE

echo "Script dir: $SCRIPT_DIR"

echo
echo "Compiling interpreter_numba_aot..."
echo "Started at: $(date)"
python -m pyjamaz.pvm.interpreters.numba.interpreter_numba_aot_ffi
echo "✓ AOT cache warmup completed successfully"
echo "Finished at: $(date)"
