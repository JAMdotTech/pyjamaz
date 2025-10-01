# Minimal AOT wrapper that pre compiled interpreter_numba_jit

from numba import types, int32, int64, uint32, uint8, uint64, boolean
from numba.pycc import CC

# ---- Export container ----
cc = CC('interpreter_numba_aot')


u8_array_1d = types.Array(uint8, 1, 'C')
u8_array_list = types.ListType(u8_array_1d)
u64_array_1d = types.Array(uint64, 1, 'C')
u64_array_list = types.ListType(u64_array_1d)
int32_array_1d = types.Array(int32, 1, 'C')


from .interpreter_numba_jit import (
    invoke_native as invoke_native_jit,
)


# Note: keep signature the same as invoke_jit
@cc.export(
    'invoke_native',
    int32(
        uint32,  # pc
        int64,  # gas
        uint32,  # inst_nr
        uint32,  # skip_len

        uint8[::1],  # code
        uint32,  # code_size
        int32[::1],  # inst_arg_len_array
        int32[::1],  # pc_to_inst_index
        int32[::1],  # opcode_scheme_array (len 256)
        int32[::1],  # jump_table_array

        uint64[::1],  # mem_section_starts
        uint64[::1],  # mem_section_ends
        u8_array_list,  # section_arrays : List[uint8[:]]
        u64_array_list,  # acl_bitmaps
        int32[::1],  # section_access
        uint64[::1],  # heap_info (len 3)

        uint64[::1],  # reg (len 13)

        boolean,  # logging_enabled
        types.ListType(types.unicode_type),  # opcode_names list

        uint64[::1],  # registers_out
        int64[::1],  # state_out
        int64[::1],  # heap_grew_out
    )
)
def invoke_native(
        pc_start,
        gas_start,
        inst_start,
        initial_skip_len,

        code,
        code_size,
        inst_arg_len,
        pc_to_inst_index,
        opcode_scheme,
        jump_table,

        mem_section_starts,
        mem_section_ends,
        section_arrays,
        acl_bitmaps,
        section_access,
        heap_info,  # [current_heap_end, next_section_start, mem_writable_value]

        registers_in,

        logging,
        opcode_names,

        registers_out,
        state_out,
        heap_grew_out):

    # Delegate to the JIT implementation. Ensure dtypes at the call-site match this signature.
    return invoke_native_jit(
        pc_start,
        gas_start,
        inst_start,
        initial_skip_len,

        code,
        code_size,
        inst_arg_len,
        pc_to_inst_index,
        opcode_scheme,
        jump_table,

        mem_section_starts,
        mem_section_ends,
        section_arrays,
        acl_bitmaps,
        section_access,
        heap_info,  # [current_heap_end, next_section_start, mem_writable_value]

        registers_in,

        logging,
        opcode_names,

        registers_out,
        state_out,
        heap_grew_out
    )


if __name__ == '__main__':
    cc.compile()