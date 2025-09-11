from pyjamaz import settings
#
# if settings.PVM_INTERPRETER == "PVM_GP":
#     from .interpreter_gp import PVMInterpreter
# else:
#     from .interpreter_cpython import PVMInterpreter

if settings.PVM_INTERPRETER == "CPYTHON":
    from .cpython.defs import *
    from .cpython.types import *
    from .cpython.interpreter_cpython import *
elif settings.PVM_INTERPRETER == "NUMBA":
    from .numba.defs import *
    from .numba.types import *
    from .numba.types import *
    from .numba.interpreter_numba import *
    # Warm up JIT
    from .numba.interpreter_numba import invoke_native
    import numpy as np
    from numba.typed import List, Dict
    from numba import types

    # Minimal structures to trigger compilation
    code = np.zeros(1, dtype=np.uint8)
    code_size = np.uint32(1)
    inst_pos_keys = np.array([], dtype=np.int32)
    inst_pos_vals = np.array([], dtype=np.int32)
    inst_arg_len = np.array([], dtype=np.int32)
    pc_to_inst_index = np.full(1, -1, dtype=np.int32)
    opcode_scheme = np.full(256, 255, dtype=np.int32)
    jump_table = np.array([], dtype=np.int32)
    mem_ops_read = np.zeros(256, dtype=np.bool_)
    mem_ops_write = np.zeros(256, dtype=np.bool_)
    mem_ops_bytes = np.zeros(256, dtype=np.uint8)
    section_starts = np.array([], dtype=np.uint64)
    section_ends = np.array([], dtype=np.uint64)
    section_arrays = List.empty_list(types.uint8[::1])
    acl_dict = Dict.empty(key_type=types.int64, value_type=types.int64)
    heap_info = np.array([0, np.uint64(0xFFFFFFFF), 2], dtype=np.uint64)
    registers_in = np.zeros(13, dtype=np.uint64)
    opcode_names = Dict.empty(key_type=types.int64, value_type=types.unicode_type)
    registers_out = np.zeros(13, dtype=np.uint64)
    status_out = np.array([0], dtype=np.int32)
    exit_value_out = np.array([0], dtype=np.int64)
    pc_out = np.array([0], dtype=np.uint32)
    gas_out = np.array([0], dtype=np.int64)
    inst_nr_out = np.array([0], dtype=np.uint32)
    skip_len_out = np.array([0], dtype=np.int64)
    heap_grew_out = np.array([0], dtype=np.int32)

    # Call once to compile
    invoke_native(
        np.uint32(0), np.int64(0), np.uint32(0), np.int64(0),
        code, code_size,
        inst_pos_keys, inst_pos_vals, inst_arg_len, pc_to_inst_index,
        opcode_scheme, jump_table,
        mem_ops_read, mem_ops_write, mem_ops_bytes,
        section_starts, section_ends, section_arrays, acl_dict,
        heap_info,
        registers_in,
        opcode_names,
        registers_out, status_out, exit_value_out,
        pc_out, gas_out, inst_nr_out, skip_len_out, heap_grew_out
    )

else:
    raise Exception(f"Unknow PVM interpreter: {settings.PVM_INTERPRETER}")
