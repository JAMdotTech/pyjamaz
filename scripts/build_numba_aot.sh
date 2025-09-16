#!/bin/bash

echo "Building Numba AOT PVM interpreter (warm-up compile)"
echo "====================================================="

SCRIPT_DIR="$( cd -- "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PKG_ROOT="${SCRIPT_DIR}/.."                 # .../pyjamaz
SRC_DIR="${PKG_ROOT}/pyjamaz/pvm/numba"     # .../pyjamaz/pyjamaz/pvm/numba

echo "Script dir: ${SCRIPT_DIR}"
echo "Package  : ${PKG_ROOT}"
echo "Source   : ${SRC_DIR}"

if [ ! -d "${SRC_DIR}" ]; then
  echo "✗ Source directory not found at ${SRC_DIR}"
  return 1 2>/dev/null || exit 1
fi

echo ""
echo "Cleaning old builds/caches..."
# Be robust when sourced from zsh (no matches) by disabling globbing temporarily
(
  set -f
  cd "${SRC_DIR}" 2>/dev/null && rm -f *.so *.pyd *.dll pvm_numba_aot*.c pvm_numba_aot*.h interpreter_numba_aot*.c interpreter_numba_aot*.h || true
  set +f
) || true


echo ""
echo "Activating virtualenv (if provided) and setting PYTHONPATH..."
# Allow override via VENV_ACTIVATE env var; else use user-provided default
VENV_ACTIVATE_DEFAULT="/Users/matthijsblaas/.venvs/pyjamaz/bin/activate"
VENV_ACTIVATE_PATH="${VENV_ACTIVATE:-$VENV_ACTIVATE_DEFAULT}"
if [ -f "$VENV_ACTIVATE_PATH" ]; then
  # shellcheck source=/dev/null
  . "$VENV_ACTIVATE_PATH"
  echo "✓ Activated venv at $VENV_ACTIVATE_PATH"
else
  echo "⚠️  No venv found at $VENV_ACTIVATE_PATH (continuing with system python)"
fi

# Match user's instructions: run from ${PKG_ROOT} and set PYTHONPATH=.
cd "${PKG_ROOT}" || exit 1
export PYTHONPATH=.
echo "PWD=$(pwd) PYTHONPATH=${PYTHONPATH}"

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
echo "Cached/compiled files (if any):"
ls -la "${SRC_DIR}" 2>/dev/null || true
find "${PKG_ROOT}" -maxdepth 3 -type f \( -name 'pvm_numba_aot*.*' -o -name 'interpreter_numba_aot*.*' -o -name '*.so' -o -name '*.pyd' -o -name '*.dll' \) 2>/dev/null || true

echo ""
echo "Done."
