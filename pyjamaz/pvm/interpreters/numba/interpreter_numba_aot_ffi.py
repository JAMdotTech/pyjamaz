"""Warm the disk cache used by the NUMBA_AOT interpreter.

The interpreter and its helpers declare explicit, cached @njit signatures.
Importing them eagerly compiles those canonical signatures; keeping a second
list here lets the build drift from the runtime interface.
"""

from . import interpreter_numba_aot_patch  # noqa: F401; apply cache/CPU patches first
from .interpreter_numba_jit import invoke_native


if __name__ == "__main__":
    if not invoke_native.nopython_signatures:
        raise RuntimeError("Numba interpreter cache warmup produced no compiled signatures")
    print("Numba interpreter cache warmed using canonical @njit signatures")
