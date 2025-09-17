from numba import types
from numba.pycc import CC

#https://numba.readthedocs.io/en/stable/reference/aot-compilation.html
#https://numba.readthedocs.io/en/stable/cuda/caching.html

cc = CC('interpreter_numba_aot_ffi')

# ---- Type aliases ----
U8   = types.uint8
U32  = types.uint32
U64  = types.uint64
I32  = types.int32
I64  = types.int64
F64  = types.float64

U8_A1   = U8[::1]
U32_A1  = U32[::1]
U64_A1  = U64[::1]
I32_A1  = I32[::1]
I64_A1  = I64[::1]
F64_A1  = F64[::1]

U8_LIST        = types.ListType(U8_A1)                     # List[uint8[:]]
ACL_DICT_T     = types.DictType(U32, I32)                  # Dict[uint32 -> int32]
NAMES_DICT_T   = types.DictType(I64, types.unicode_type)   # Dict[int64  -> unicode]


from .interpreter_numba_jit import invoke_native_jit


@cc.export(
    'invoke_native',
    I32(                     # return: int32 error_code
        U32, I64, U32, U32,  # pc, gas, inst_nr, skip_len
        U8_A1, U32,          # code, code_size
        I32_A1, I32_A1, I32_A1, I32_A1, I32_A1, I32_A1,  # inst_pos_keys/vals, inst_arg_len, pc->inst, opcode_scheme, jump_table
        I64_A1, I64_A1, I64_A1,                          # mem_ops_read/write/bytes
        U64_A1, U64_A1,                                  # mem_section_starts/ends
        U8_LIST,                                          # section_arrays : List[uint8[:]]
        ACL_DICT_T,                                       # acl_dict      : Dict[uint32,int32]
        U64_A1, U64_A1,                                   # heap_info, registers_in
        NAMES_DICT_T,                                     # opcode_names  : Dict[int64, unicode]
        U64_A1, I64_A1, I32_A1,                           # registers_out, state_out, heap_grew_out
        I64_A1, F64_A1, F64_A1, F64_A1, I64_A1            # timing stats outputs
    )
)
def invoke_native(
    pc, gas, inst_nr, skip_len,
    code, code_size,
    inst_pos_keys, inst_pos_vals, inst_arg_len_array, pc_to_inst_index, opcode_scheme_array, jump_table_array,
    mem_ops_read, mem_ops_write, mem_ops_bytes,
    mem_section_starts, mem_section_ends, section_arrays, acl_dict,
    heap_info, reg, opcode_names,
    registers_out, state_out, heap_grew_out,
    opcode_counts_out, opcode_time_total_out, opcode_time_min_out, opcode_time_max_out, total_iterations_out
):
    return invoke_native_jit(
        pc, gas, inst_nr, skip_len,
        code, code_size,
        inst_pos_keys, inst_pos_vals, inst_arg_len_array, pc_to_inst_index, opcode_scheme_array, jump_table_array,
        mem_ops_read, mem_ops_write, mem_ops_bytes,
        mem_section_starts, mem_section_ends, section_arrays, acl_dict,
        heap_info, reg, opcode_names,
        registers_out, state_out, heap_grew_out,
        opcode_counts_out, opcode_time_total_out, opcode_time_min_out, opcode_time_max_out, total_iterations_out
    )

if __name__ == '__main__':
    cc.compile()
