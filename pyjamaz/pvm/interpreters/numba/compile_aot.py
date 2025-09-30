"""
Ahead Of Time compilation bootstrap & bridge for Numba compiled PVM
"""
from __future__ import annotations
import importlib
import importlib.util
import sys
import pathlib
from importlib.machinery import SourceFileLoader

__all__ = ['invoke_native_aot', '_compile_from_source']


invoke_native_aot = None  # will be resolved below


def _try_import_compiled():
    try:
        return importlib.import_module('pyjamaz.pvm.numba.interpreter_numba_aot_ffi')
    except Exception:
        return None


def _resolve_runtime_symbol():
    global invoke_native_aot
    mod = _try_import_compiled()
    if mod is not None and hasattr(mod, 'invoke_native'):
        invoke_native_aot = getattr(mod, 'invoke_native')
        return
    try:
        from pyjamaz.pvm.interpreters.numba.interpreter_numba_jit import invoke_native as _invoke_native_jit
    except Exception:
        from .interpreter_numba_jit import invoke_native as _invoke_native_jit  # type: ignore
    invoke_native_aot = _invoke_native_jit


_resolve_runtime_symbol()


def _compile_from_source():
    aot_src = pathlib.Path(__file__).with_name('interpreter_numba_aot_ffi.py')
    if not aot_src.exists():
        raise RuntimeError(f"AOT source file not found: {aot_src}")
    mod_name = 'pyjamaz.pvm.numba._aot_build_tmp'
    spec = importlib.util.spec_from_loader(mod_name, SourceFileLoader(mod_name, str(aot_src)))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    if not hasattr(mod, 'cc'):
        raise RuntimeError("interpreter_numba_aot_ffi.py must define `cc = CC(...)`.")
    mod.cc.compile()


if __name__ == '__main__':
    _compile_from_source()