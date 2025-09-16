import numpy as np

from numba import types
from numba import uint8, uint32, int32, uint64, int64, boolean
from numba.typed import Dict, List
from numba import config as numba_config

u8_array_1d = types.Array(uint8, 1, 'C')
u8_array_list = types.ListType(u8_array_1d)
acl_dict_type = types.DictType(uint64, int32)

from .interpreter_numba import (
        umul64wide,
        imul64wide,
        smul_u64wide,
        rori64_jit,
        roli64_jit,
        rori32_jit,
        roli32_jit,
        pvm_smod_jit,
        pvm_rtz_div_jit,
        pvm_X_jit,
        pvm_Z_jit,
        count_leading_zeroes_jit,
        count_trailing_zeroes_jit,
        reverse_bytes_jit,
        riscv_div_jit,
        pvm_Z_inv_jit,
        read_uint_jit,
        mem_write_jit,
        mem_read_jit,
        sync_state_and_return,
        sbrk_jit,
        branch_jit,
        djump_jit,
        invoke_native
    )


if not numba_config.DISABLE_JIT:
    # dummy inputs for invoke_native to trigger compilation
    dummy_pc = np.uint32(0)
    dummy_gas = np.int64(0)
    dummy_inst_nr = np.uint32(0)
    dummy_skip_len = np.uint32(0)

    dummy_code = np.zeros(1, dtype=np.uint8)
    dummy_code_size = np.uint32(dummy_code.size)
    dummy_inst_pos_keys = np.zeros(1, dtype=np.int32)
    dummy_inst_pos_vals = np.zeros(1, dtype=np.int32)
    dummy_inst_arg_len_array = np.zeros(1, dtype=np.int32)
    dummy_pc_to_inst_index = np.zeros(1, dtype=np.int32)
    dummy_opcode_scheme_array = np.zeros(256, dtype=np.int32)
    dummy_jump_table_array = np.zeros(1, dtype=np.int32)

    dummy_mem_ops_read = np.zeros(1, dtype=np.int64)
    dummy_mem_ops_write = np.zeros(1, dtype=np.int64)
    dummy_mem_ops_bytes = np.zeros(1, dtype=np.int64)

    dummy_mem_section_starts = np.zeros(1, dtype=np.uint64)
    dummy_mem_section_ends = np.zeros(1, dtype=np.uint64)
    dummy_section_arrays = List.empty_list(u8_array_1d)
    dummy_acl_dict = Dict.empty(key_type=int64, value_type=int64)

    dummy_heap_info = np.zeros(3, dtype=np.uint64)
    dummy_reg = np.zeros(13, dtype=np.uint64)
    dummy_opcode_names = Dict.empty(key_type=int64, value_type=types.unicode_type)

    dummy_registers_out = np.zeros(13, dtype=np.uint64)
    dummy_state_out = np.zeros(5, dtype=np.int64)
    dummy_heap_grew_out = np.zeros(1, dtype=np.int32)

    umul64wide._can_compile =True
    imul64wide._can_compile =True
    smul_u64wide._can_compile =True
    rori64_jit._can_compile =True
    roli64_jit._can_compile =True
    rori32_jit._can_compile =True
    roli32_jit._can_compile =True
    pvm_smod_jit._can_compile =True
    pvm_rtz_div_jit._can_compile =True
    pvm_X_jit._can_compile =True
    pvm_Z_jit._can_compile =True
    count_leading_zeroes_jit._can_compile =True
    count_trailing_zeroes_jit._can_compile =True
    reverse_bytes_jit._can_compile =True
    riscv_div_jit._can_compile =True
    pvm_Z_inv_jit._can_compile =True
    read_uint_jit._can_compile =True
    mem_write_jit._can_compile =True
    mem_read_jit._can_compile =True
    sync_state_and_return._can_compile =True
    sbrk_jit._can_compile =True
    branch_jit._can_compile =True
    djump_jit._can_compile =True
    invoke_native._can_compile =True


    umul64wide.compile(types.UniTuple(uint64, 2)(uint64, uint64))
    imul64wide.compile(types.UniTuple(uint64, 2)(int64, int64))
    smul_u64wide.compile(types.UniTuple(uint64, 2)(int64, uint64))
    rori64_jit.compile(uint64(uint64, uint64))
    roli64_jit.compile(uint64(uint64, uint64))
    rori32_jit.compile(uint32(uint32, uint32))
    roli32_jit.compile(uint32(uint32, uint32))
    pvm_smod_jit.compile(int64(int64, int64))
    pvm_rtz_div_jit.compile(int64(int64, int64))
    pvm_X_jit.compile(uint64(uint64, uint64))
    pvm_Z_jit.compile(int64(uint64, uint64))
    count_leading_zeroes_jit.compile(uint64(uint64, uint8))
    count_trailing_zeroes_jit.compile(uint64(uint64, uint8))
    reverse_bytes_jit.compile(uint64(uint64,))
    riscv_div_jit.compile(int64(int64, int64))
    pvm_Z_inv_jit.compile(uint64(int64, uint8))
    read_uint_jit.compile(uint64(uint8[::1], uint32, uint8))

    mem_write_jit.compile(int32(
        uint64,   # addr
        uint64,         # value
        uint8,          # bytes_to_write
        uint32[::1],    # section_starts
        uint32[::1],    # section_ends
        u8_array_list,  # section_arrays
        acl_dict_type   # acl_dict
    ))

    mem_read_jit.compile(types.Tuple((int32, uint64))(
        uint64,  # addr
        uint8,  # bytes_to_write
        uint32[::1],  # section_starts
        uint32[::1],  # section_ends
        u8_array_list,  # section_arrays
        acl_dict_type  # acl_dict
    ))

    sync_state_and_return.compile(uint32(
        uint64[::1],   # reg
        uint64[::1],   # registers_out
        int64[::1],    # state_out
        int64,         # status
        int64,         # pc
        int64,         # gas
        int64,         # inst_nr
        int64,         # exit_value
        uint32,        # skip_len
        uint32,        # error_code
    ))

    sbrk_jit.compile(types.Tuple((uint64, int32))(
        uint64,         # size
        uint64,         # current_heap_ptr
        uint64,         # next_section_start
        acl_dict_type,  # Dict[uint64 -> int32]
        int64,          # mem_writable
        u8_array_list,  # List[uint8[:]]
        uint32[::1],    # section_starts
    ))

    branch_jit.compile(int32(
        uint32,       # pc
        int64,        # offset
        boolean,      # condition
        int32[::1],   # pc_to_inst_index
    ))

    djump_jit.compile(int32(
        uint32,       # a
        uint32[::1],  # jump_table (PC targets)
        uint32,       # pc
        int32[::1],   # pc_to_inst_index (dense map)
    ))

    invoke_native.compile(int32(
        # core state
        uint32,          # pc
        int64,           # gas
        uint32,          # inst_nr
        uint32,          # skip_len

        # code + index structures
        uint8[::1],      # code
        uint32,          # code_size
        int32[::1],      # inst_pos_keys
        int32[::1],      # inst_pos_vals
        int32[::1],      # inst_arg_len_array
        int32[::1],      # pc_to_inst_index
        int32[::1],      # opcode_scheme_array (len 256)
        int32[::1],      # jump_table_array

        # mem-op counters (pass as 1-D arrays so they can be updated in-place)
        int64[::1],      # mem_ops_read
        int64[::1],      # mem_ops_write
        int64[::1],      # mem_ops_bytes

        # memory sections + ACL
        uint64[::1],     # mem_section_starts
        uint64[::1],     # mem_section_ends
        u8_array_list,   # section_arrays : List[uint8[:]]
        types.DictType(int64, int64),  # acl_dict

        # heap + regs + names
        uint64[::1],     # heap_info (len 3)
        uint64[::1],     # reg (len 13)
        types.DictType(int64, types.unicode_type),  # opcode_names

        # outputs
        uint64[::1],     # registers_out
        int64[::1],      # state_out
        int32[::1],      # heap_grew_out
    ))
    invoke_native(
        dummy_pc,
        dummy_gas,
        dummy_inst_nr,
        dummy_skip_len,
        dummy_code,
        dummy_code_size,
        dummy_inst_pos_keys,
        dummy_inst_pos_vals,
        dummy_inst_arg_len_array,
        dummy_pc_to_inst_index,
        dummy_opcode_scheme_array,
        dummy_jump_table_array,
        dummy_mem_ops_read,
        dummy_mem_ops_write,
        dummy_mem_ops_bytes,
        dummy_mem_section_starts,
        dummy_mem_section_ends,
        dummy_section_arrays,
        dummy_acl_dict,
        dummy_heap_info,
        dummy_reg,
        dummy_opcode_names,
        dummy_registers_out,
        dummy_state_out,
        dummy_heap_grew_out,
    )

    print("COMPILLLEEEEEEEEDDD")