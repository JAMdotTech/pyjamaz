#!/usr/bin/env python3
"""Execute a small PVM program using only the image's prebuilt Numba cache."""

import os
from pathlib import Path
import sys


def main():
    # Set these before importing pyjamaz or Numba, including when the parent
    # process has inherited build-time warmup or disabled-JIT settings.
    os.environ.update({
        "PVM_INTERPRETER": "NUMBA_AOT",
        "NUMBA_CACHE_ONLY": "1",
        "NUMBA_CACHE_WARMUP": "0",
        "NUMBA_CPU_NAME": "generic",
        "NUMBA_CPU_FEATURES": "",
        "NUMBA_DISABLE_JIT": "0",
    })
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from jamcodec.base import JamBytes

    from pyjamaz.pvm import PVMInterpreter, PVMMemory
    from pyjamaz.pvm.constants import ExitReason
    from pyjamaz.pvm.interpreters.numba.interpreter_numba_jit import invoke_native
    from pyjamaz.pvm.types import PVMCode, PVMProgram

    if PVMInterpreter.__module__ != "pyjamaz.pvm.interpreters.numba.interpreter_numba_jit":
        raise RuntimeError("Cache smoke check requires the Numba PVM interpreter")

    # load_imm_64 r7, 0xDEADBEEFDEADBEEF; trap. Include the complete PVM
    # code blob (header, instruction bytes, and opcode bitmask) so this check
    # also works in the final image, which does not contain test fixtures.
    code_blob = bytes.fromhex("00 00 0b 14 07 ef be ad de ef be ad de 00 01 04")
    code = PVMCode.from_jam_bytes(JamBytes(code_blob))
    pvm = PVMInterpreter(PVMProgram(code, [0] * 13, PVMMemory()))
    pvm.invoke(0, 10000)

    expected_registers = [0] * 13
    expected_registers[7] = 0xDEADBEEFDEADBEEF
    actual = (pvm.get_registers(), int(pvm.pc), int(pvm.gas), pvm.status)
    expected = (expected_registers, 10, 9998, ExitReason.panic.value)
    if actual != expected:
        raise RuntimeError(f"Cached PVM execution mismatch: {actual!r} != {expected!r}")

    cache_hits = sum(invoke_native.stats.cache_hits.values())
    if cache_hits < 1:
        raise RuntimeError("PVM interpreter did not load an invoke_native overload from cache")
    print(f"Numba cache-only PVM smoke check passed ({cache_hits} interpreter cache hit(s))")


if __name__ == "__main__":
    main()
