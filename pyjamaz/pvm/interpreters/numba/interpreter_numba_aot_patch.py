import os, sys, pickle, importlib.util, hashlib, marshal
import numba
import inspect

from numba.core import caching
from numba.core.caching import IndexDataCacheFile
from numba.core import compiler as _nb_compiler
from numba.core import dispatcher as _nb_dispatcher
from numba.core import config as _nb_config


# Note:
# we ensure the cpu fingerprint matches between dcoker cache build and runtime.
# wtihout this, numba includes host cpu name/features in the cache key, which
# causes cache misses when warmup happens with NUMBA_CPU_NAME=generic but the
# runtime process inherits the host defaults. deefault to "generic" (no# extra
# features) unless the user explicitly opts in via environment variables.

if "NUMBA_CPU_NAME" not in os.environ:
    os.environ["NUMBA_CPU_NAME"] = "generic"

if _nb_config.CPU_NAME in (None, "", "native"):
    _nb_config.CPU_NAME = os.environ.get("NUMBA_CPU_NAME", "generic")

if "NUMBA_CPU_FEATURES" not in os.environ:
    os.environ["NUMBA_CPU_FEATURES"] = ""

if _nb_config.CPU_FEATURES in (None, "", "native", "host"):
    _nb_config.CPU_FEATURES = os.environ.get("NUMBA_CPU_FEATURES", "")


def _safe_get_source_file(py_func):
    # 1) Prefer inspect-reported paths (may point to .py even if missing)
    try:
        path = inspect.getsourcefile(py_func)
    except Exception:
        path = None
    if path:
        return path

    try:
        path = inspect.getfile(py_func)
    except Exception:
        path = None
    if path:
        return path

    co = getattr(py_func, '__code__', None)
    if co is not None:
        fn = co.co_filename
        if fn:
            # If it's a .pyc, try mapping to .py
            if fn.endswith('.pyc'):
                try:
                    return importlib.util.source_from_cache(fn)
                except Exception:
                    pass
            return fn

    mod = sys.modules.get(py_func.__module__)
    mfile = getattr(mod, '__file__', None)
    if mfile:
        if mfile.endswith('.pyc'):
            try:
                return importlib.util.source_from_cache(mfile)
            except Exception:
                # Not a standard pyc path; guess alongside module file
                base = os.path.splitext(mfile)[0]
                return base + '.py'
        # Non-pyc: guess .py next to module file
        base = os.path.splitext(mfile)[0]
        return base + '.py'

    return None

def _from_function_allow_pyc(cls, py_func, source_path=None):
    py_file = None
    if source_path:
        py_file = source_path
    else:
        py_file = _safe_get_source_file(py_func)
    if not py_file:
        return  # let other locators try
    self = cls(py_func, py_file)
    try:
        self.ensure_cache_path()
    except OSError:
        return
    return self

caching._SourceFileBackedLocatorMixin.from_function = classmethod(_from_function_allow_pyc)

def _code_based_stamp(py_func):
    co = getattr(py_func, "__code__", None)
    if co is None:
        return (0, 0)
    blob = marshal.dumps(co)
    digest = hashlib.sha256(blob).digest()
    hi = int.from_bytes(digest[:8], "little", signed=False)
    lo = int.from_bytes(digest[8:16], "little", signed=False)
    return (hi, lo)

def _get_source_stamp_lenient(self):
    # Prefer a deterministic stamp derived from the function bytecode so that
    # caches remain valid even when .py sources are stripped from the image.
    try:
        return _code_based_stamp(self.py_func)
    except Exception:
        return (0, 0)

# Apply the lenient stamp getter
caching._SourceFileBackedLocatorMixin.get_source_stamp = _get_source_stamp_lenient

# Ensure we keep the original index loader (stamp checks now succeed because we
# return a stable, reproducible stamp from _get_source_stamp_lenient)
# Preserve earlier reference for completeness
_orig_load_index = IndexDataCacheFile._load_index

# ---- optional hard cache-only mode (no recompilation, no saving) -----------

if os.environ.get("NUMBA_CACHE_ONLY", "").lower() in ("1", "true", "yes"):
    # Keep a reference to the original numba compiler entrypoint
    _orig_compile_extra = _nb_compiler.compile_extra

    def _compile_extra_cache_only(*args, **kwargs):
        """Cache-only guard.
        - Always allow Numba/llvmlite internals to JIT (they compile tiny helper kernels).
        - Allow project code to JIT only when NUMBA_CACHE_WARMUP=1.
        Accepts both positional and keyword forms used across Numba versions.
        """
        func = kwargs.get('func')
        if func is None and len(args) >= 3:
            # Convention: (typingctx, targetctx, func, ...)
            func = args[2]
        modname = getattr(func, '__module__', '') or ''

        # 1) Allow Numba/llvmlite internals
        if modname.startswith('numba.') or modname.startswith('llvmlite.'):
            return _orig_compile_extra(*args, **kwargs)

        # 2) Allow warmup compiles for our package when explicitly enabled
        warmup = os.environ.get('NUMBA_CACHE_WARMUP', '').lower() in ('1', 'true', 'yes')
        if warmup and (modname.startswith('pyjamaz.') or modname == '__main__'):
            return _orig_compile_extra(*args, **kwargs)

        # 3) Otherwise, forbid
        qn = getattr(func, '__qualname__', getattr(func, '__name__', '<?>'))
        raise RuntimeError(
            f"NUMBA cache-only: cached overload not found for {modname}.{qn}")

    _nb_compiler.compile_extra = _compile_extra_cache_only

    # read-only cache: don't save new overloads unless warmup is enabled
    _orig_save_overload = getattr(caching.Cache, '_save_overload', None)
    def _no_save(self, sig, data):
        if os.environ.get('NUMBA_CACHE_WARMUP', '').lower() in ('1','true','yes'):
            if _orig_save_overload is not None:
                return _orig_save_overload(self, sig, data)
        return
    caching.Cache._save_overload = _no_save

# ---- make disable_compile a no-op during warmup ----------------------------

try:
    _orig_disable_compile = _nb_dispatcher._DispatcherBase.disable_compile
except Exception:
    _orig_disable_compile = None

def _disable_compile_guard(self, val=True):
    """During warmup (NUMBA_CACHE_WARMUP=1), never disable compilation.
    Otherwise, defer to Numba's original behavior.
    """
    warmup = os.environ.get('NUMBA_CACHE_WARMUP', '').lower() in ('1','true','yes')
    if warmup:
        # Force-enable compilation for warmup, ignore requests to disable
        self._can_compile = True
        return
    if _orig_disable_compile is not None:
        return _orig_disable_compile(self, val)

# Apply the guard
_nb_dispatcher._DispatcherBase.disable_compile = _disable_compile_guard
