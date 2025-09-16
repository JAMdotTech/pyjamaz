# # Minimal AOT wrapper that relies on interpreter_numba_jit for implementations.
# # Build with:  python -m pyjamaz.pvm.numba.interpreter_numba_aot2
# # Produces:    interpreter_numba_aot2.* (shared object next to this file)
#
# from numba import types
# from numba.pycc import CC
#
# # ---- Export container ----
# cc = CC('interpreter_numba_aot2')
#
# # ---- Type aliases ----
# U8   = types.uint8
# U32  = types.uint32
# U64  = types.uint64
# I32  = types.int32
# I64  = types.int64
#
# U8_A1   = U8[::1]
# U32_A1  = U32[::1]
# U64_A1  = U64[::1]
# I32_A1  = I32[::1]
# I64_A1  = I64[::1]
#
# # Containers
# U8_LIST        = types.ListType(U8_A1)                     # List[uint8[:]]
# ACL_DICT_T     = types.DictType(U32, I32)                  # Dict[uint32 -> int32]
# NAMES_DICT_T   = types.DictType(I64, types.unicode_type)   # Dict[int64  -> unicode]
#
# # ---- Import JIT implementations (the real logic lives here) ----
# from .interpreter_numba_jit import (
#     invoke_native_jit,
# )
#
# # =========================
# # Minimal required exports
# # =========================
#
# # Export only the main entry point for the interpreter. The body delegates to the JIT function.
# # Keep this signature EXACTLY in sync with your JIT signature.
# @cc.export(
#     'invoke_native',
#     I32(                     # return: int32 error_code
#         U32, I64, U32, U32,  # pc, gas, inst_nr, skip_len
#         U8_A1, U32,          # code, code_size
#         I32_A1, I32_A1, I32_A1, I32_A1, I32_A1, I32_A1,  # inst_pos_keys/vals, inst_arg_len, pc->inst, opcode_scheme, jump_table
#         I64_A1, I64_A1, I64_A1,                          # mem_ops_read/write/bytes
#         U64_A1, U64_A1,                                  # mem_section_starts/ends  (64-bit bounds)
#         U8_LIST,                                          # section_arrays : List[uint8[:]]
#         ACL_DICT_T,                                       # acl_dict      : Dict[uint32,int32]
#         U64_A1, U64_A1,                                   # heap_info, registers_in
#         NAMES_DICT_T,                                     # opcode_names  : Dict[int64, unicode]
#         U64_A1, I64_A1, I32_A1                            # registers_out, state_out, heap_grew_out
#     )
# )
# def invoke_native(
#     pc, gas, inst_nr, skip_len,
#     code, code_size,
#     inst_pos_keys, inst_pos_vals, inst_arg_len_array, pc_to_inst_index, opcode_scheme_array, jump_table_array,
#     mem_ops_read, mem_ops_write, mem_ops_bytes,
#     mem_section_starts, mem_section_ends, section_arrays, acl_dict,
#     heap_info, reg, opcode_names,
#     registers_out, state_out, heap_grew_out
# ):
#     # Delegate to the JIT implementation. Ensure dtypes at the call-site match this signature.
#     return invoke_native_jit(
#         pc, gas, inst_nr, skip_len,
#         code, code_size,
#         inst_pos_keys, inst_pos_vals, inst_arg_len_array, pc_to_inst_index, opcode_scheme_array, jump_table_array,
#         mem_ops_read, mem_ops_write, mem_ops_bytes,
#         mem_section_starts, mem_section_ends, section_arrays, acl_dict,
#         heap_info, reg, opcode_names,
#         registers_out, state_out, heap_grew_out
#     )
#
#
# if __name__ == '__main__':
#     # Build the extension module
#     cc.compile()