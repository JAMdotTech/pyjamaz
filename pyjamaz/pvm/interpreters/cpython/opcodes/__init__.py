from pyjamaz.pvm.constants import (
    op_trap, op_fallthrough, op_ecalli, op_load_imm_64, op_store_imm_u8, op_store_imm_u16,
    op_store_imm_u32, op_store_imm_u64, op_jump, op_jump_ind, op_load_imm, op_load_u8,
    op_load_i8, op_load_u16, op_load_i16, op_load_u32, op_load_i32, op_load_u64,
    op_store_u8, op_store_u16, op_store_u32, op_store_u64, op_store_imm_ind_u8,
    op_store_imm_ind_u16, op_store_imm_ind_u32, op_store_imm_ind_u64, op_load_imm_jump,
    op_branch_eq_imm, op_branch_ne_imm, op_branch_lt_u_imm, op_branch_le_u_imm,
    op_branch_ge_u_imm, op_branch_gt_u_imm, op_branch_lt_s_imm, op_branch_le_s_imm,
    op_branch_ge_s_imm, op_branch_gt_s_imm, op_move_reg, op_sbrk, op_count_set_bits_64,
    op_count_set_bits_32, op_leading_zero_bits_64, op_leading_zero_bits_32,
    op_trailing_zero_bits_64, op_trailing_zero_bits_32, op_sign_extend_8, op_sign_extend_16,
    op_zero_extend_16, op_reverse_bytes, op_store_ind_u8, op_store_ind_u16,
    op_store_ind_u32, op_store_ind_u64, op_load_ind_u8, op_load_ind_i8, op_load_ind_u16,
    op_load_ind_i16, op_load_ind_u32, op_load_ind_i32, op_load_ind_u64, op_add_imm_32,
    op_and_imm, op_xor_imm, op_or_imm, op_mul_imm_32, op_set_lt_u_imm, op_set_lt_s_imm,
    op_shlo_l_imm_32, op_shlo_r_imm_32, op_shar_r_imm_32, op_neg_add_imm_32,
    op_set_gt_u_imm, op_set_gt_s_imm, op_shlo_l_imm_alt_32, op_shlo_r_imm_alt_32,
    op_shar_r_imm_alt_32, op_cmov_iz_imm, op_cmov_nz_imm, op_add_imm_64, op_mul_imm_64,
    op_shlo_l_imm_64, op_shlo_r_imm_64, op_shar_r_imm_64, op_neg_add_imm_64,
    op_shlo_l_imm_alt_64, op_shlo_r_imm_alt_64, op_shar_r_imm_alt_64, op_rot_r_64_imm,
    op_rot_r_64_imm_alt, op_rot_r_32_imm, op_rot_r_32_imm_alt, op_branch_eq, op_branch_ne,
    op_branch_lt_u, op_branch_lt_s, op_branch_ge_u, op_branch_ge_s, op_load_imm_jump_ind,
    op_add_32, op_sub_32, op_mul_32, op_div_u_32, op_div_s_32, op_rem_u_32, op_rem_s_32,
    op_shlo_l_32, op_shlo_r_32, op_shar_r_32, op_add_64, op_sub_64, op_mul_64,
    op_div_u_64, op_div_s_64, op_rem_u_64, op_rem_s_64, op_shlo_l_64, op_shlo_r_64,
    op_shar_r_64, op_and, op_xor, op_or, op_mul_upper_s_s, op_mul_upper_u_u,
    op_mul_upper_s_u, op_set_lt_u, op_set_lt_s, op_cmov_iz, op_cmov_nz, op_rot_l_64,
    op_rot_l_32, op_rot_r_64, op_rot_r_32, op_and_inv, op_or_inv, op_xnor, op_max,
    op_max_u, op_min, op_min_u,
)

from ..opcodes.imm import _op_ecalli
from ..opcodes.imm_imm import _op_store_imm_u8, _op_store_imm_u16, _op_store_imm_u32, _op_store_imm_u64
from ..opcodes.none import _op_fallthrough, _op_invalid, _op_trap
from ..opcodes.offset import _op_jump
from ..opcodes.reg_ext_imm import _op_load_imm_64
from ..opcodes.reg_imm import _op_jump_ind, _op_load_imm, _op_load_u8, _op_load_i8, _op_load_u16, _op_load_i16, \
    _op_load_u32, _op_load_i32, _op_load_u64, _op_store_u8, _op_store_u16, _op_store_u32, _op_store_u64
from ..opcodes.reg_imm_imm import _op_store_imm_ind_u8, _op_store_imm_ind_u16, _op_store_imm_ind_u32, \
    _op_store_imm_ind_u64
from ..opcodes.reg_imm_offset import _op_load_imm_jump, _op_branch_eq_imm, _op_branch_ne_imm, _op_branch_lt_u_imm, \
    _op_branch_le_u_imm, _op_branch_ge_u_imm, _op_branch_gt_u_imm, _op_branch_lt_s_imm, _op_branch_le_s_imm, \
    _op_branch_ge_s_imm, _op_branch_gt_s_imm
from ..opcodes.reg_reg import _op_move_reg, _op_sbrk, _op_count_set_bits_64, _op_count_set_bits_32, \
    _op_leading_zero_bits_64, _op_leading_zero_bits_32, _op_trailing_zero_bits_64, _op_trailing_zero_bits_32, \
    _op_sign_extend_8, _op_sign_extend_16, _op_zero_extend_16, _op_reverse_bytes
from ..opcodes.reg_reg_imm import _op_store_ind_u8, _op_store_ind_u16, _op_store_ind_u32, _op_store_ind_u64, \
    _op_load_ind_u8, _op_load_ind_i8, _op_load_ind_u16, _op_load_ind_i16, _op_load_ind_u32, _op_load_ind_i32, \
    _op_load_ind_u64, _op_add_imm_32, _op_and_imm, _op_xor_imm, _op_or_imm, _op_mul_imm_32, _op_set_lt_u_imm, \
    _op_set_lt_s_imm, _op_shlo_l_imm_32, _op_shlo_r_imm_32, _op_shar_r_imm_32, _op_neg_add_imm_32, _op_set_gt_u_imm, \
    _op_set_gt_s_imm, _op_shlo_l_imm_alt_32, _op_shlo_r_imm_alt_32, _op_shar_r_imm_alt_32, _op_cmov_iz_imm, \
    _op_cmov_nz_imm, _op_add_imm_64, _op_mul_imm_64, _op_shlo_l_imm_64, _op_shlo_r_imm_64, _op_shar_r_imm_64, \
    _op_neg_add_imm_64, _op_shlo_l_imm_alt_64, _op_shlo_r_imm_alt_64, _op_shar_r_imm_alt_64, _op_rot_r_64_imm, \
    _op_rot_r_64_imm_alt, _op_rot_r_32_imm, _op_rot_r_32_imm_alt
from ..opcodes.reg_reg_imm_imm import _op_load_imm_jump_ind
from ..opcodes.reg_reg_offset import _op_branch_eq, _op_branch_ne, _op_branch_lt_u, _op_branch_lt_s, _op_branch_ge_u, \
    _op_branch_ge_s
from ..opcodes.reg_reg_reg import _op_add_64, _op_add_32, _op_sub_32, _op_mul_32, _op_div_u_32, _op_div_s_32, \
    _op_rem_u_32, _op_rem_s_32, _op_shlo_l_32, _op_shlo_r_32, _op_shar_r_32, _op_sub_64, _op_mul_64, _op_div_u_64, \
    _op_div_s_64, _op_rem_u_64, _op_rem_s_64, _op_shlo_l_64, _op_shlo_r_64, _op_shar_r_64, _op_and, _op_xor, _op_or, \
    _op_mul_upper_s_s, _op_mul_upper_u_u, _op_mul_upper_s_u, _op_set_lt_u, _op_set_lt_s, _op_cmov_iz, _op_cmov_nz, \
    _op_rot_l_64, _op_rot_l_32, _op_rot_r_64, _op_rot_r_32, _op_and_inv, _op_or_inv, _op_xnor, _op_max, _op_max_u, \
    _op_min, _op_min_u


def _opcode_lut():
    O = [_op_invalid] * 256

    # None
    O[op_trap] = _op_trap
    O[op_fallthrough] = _op_fallthrough

    # imm
    O[op_ecalli] = _op_ecalli

    # reg_ext_imm
    O[op_load_imm_64] = _op_load_imm_64

    # offset
    O[op_jump] = _op_jump

    # reg_imm_offset
    O[op_load_imm_jump] = _op_load_imm_jump
    O[op_branch_eq_imm] = _op_branch_eq_imm
    O[op_branch_ne_imm] = _op_branch_ne_imm
    O[op_branch_lt_u_imm] = _op_branch_lt_u_imm
    O[op_branch_le_u_imm] = _op_branch_le_u_imm
    O[op_branch_ge_u_imm] = _op_branch_ge_u_imm
    O[op_branch_gt_u_imm] = _op_branch_gt_u_imm
    O[op_branch_lt_s_imm] = _op_branch_lt_s_imm
    O[op_branch_le_s_imm] = _op_branch_le_s_imm
    O[op_branch_ge_s_imm] = _op_branch_ge_s_imm
    O[op_branch_gt_s_imm] = _op_branch_gt_s_imm

    # reg_imm
    O[op_jump_ind] = _op_jump_ind
    O[op_load_imm] = _op_load_imm
    O[op_load_u8] = _op_load_u8
    O[op_load_i8] = _op_load_i8
    O[op_load_u16] = _op_load_u16
    O[op_load_i16] = _op_load_i16
    O[op_load_u32] = _op_load_u32
    O[op_load_i32] = _op_load_i32
    O[op_load_u64] = _op_load_u64
    O[op_store_u8] = _op_store_u8
    O[op_store_u16] = _op_store_u16
    O[op_store_u32] = _op_store_u32
    O[op_store_u64] = _op_store_u64

    # reg_reg
    O[op_move_reg] = _op_move_reg
    O[op_sbrk] = _op_sbrk
    O[op_count_set_bits_64] = _op_count_set_bits_64
    O[op_count_set_bits_32] = _op_count_set_bits_32
    O[op_leading_zero_bits_64] = _op_leading_zero_bits_64
    O[op_leading_zero_bits_32] = _op_leading_zero_bits_32
    O[op_trailing_zero_bits_64] = _op_trailing_zero_bits_64
    O[op_trailing_zero_bits_32] = _op_trailing_zero_bits_32
    O[op_sign_extend_8] = _op_sign_extend_8
    O[op_sign_extend_16] = _op_sign_extend_16
    O[op_zero_extend_16] = _op_zero_extend_16
    O[op_reverse_bytes] = _op_reverse_bytes

    # imm_imm
    O[op_store_imm_u8] = _op_store_imm_u8
    O[op_store_imm_u16] = _op_store_imm_u16
    O[op_store_imm_u32] = _op_store_imm_u32
    O[op_store_imm_u64] = _op_store_imm_u64

    # reg_imm_imm
    O[op_store_imm_ind_u8] = _op_store_imm_ind_u8
    O[op_store_imm_ind_u16] = _op_store_imm_ind_u16
    O[op_store_imm_ind_u32] = _op_store_imm_ind_u32
    O[op_store_imm_ind_u64] = _op_store_imm_ind_u64

    # reg_reg_reg
    O[op_add_64] = _op_add_64
    O[op_add_32] = _op_add_32
    O[op_sub_32] = _op_sub_32
    O[op_mul_32] = _op_mul_32
    O[op_div_u_32] = _op_div_u_32
    O[op_div_s_32] = _op_div_s_32
    O[op_rem_u_32] = _op_rem_u_32
    O[op_rem_s_32] = _op_rem_s_32
    O[op_shlo_l_32] = _op_shlo_l_32
    O[op_shlo_r_32] = _op_shlo_r_32
    O[op_shar_r_32] = _op_shar_r_32
    O[op_sub_64] = _op_sub_64
    O[op_mul_64] = _op_mul_64
    O[op_div_u_64] = _op_div_u_64
    O[op_div_s_64] = _op_div_s_64
    O[op_rem_u_64] = _op_rem_u_64
    O[op_rem_s_64] = _op_rem_s_64
    O[op_shlo_l_64] = _op_shlo_l_64
    O[op_shlo_r_64] = _op_shlo_r_64
    O[op_shar_r_64] = _op_shar_r_64
    O[op_and] = _op_and
    O[op_xor] = _op_xor
    O[op_or] = _op_or
    O[op_mul_upper_s_s] = _op_mul_upper_s_s
    O[op_mul_upper_u_u] = _op_mul_upper_u_u
    O[op_mul_upper_s_u] = _op_mul_upper_s_u
    O[op_set_lt_u] = _op_set_lt_u
    O[op_set_lt_s] = _op_set_lt_s
    O[op_cmov_iz] = _op_cmov_iz
    O[op_cmov_nz] = _op_cmov_nz
    O[op_rot_l_64] = _op_rot_l_64
    O[op_rot_l_32] = _op_rot_l_32
    O[op_rot_r_64] = _op_rot_r_64
    O[op_rot_r_32] = _op_rot_r_32
    O[op_and_inv] = _op_and_inv
    O[op_or_inv] = _op_or_inv
    O[op_xnor] = _op_xnor
    O[op_max] = _op_max
    O[op_max_u] = _op_max_u
    O[op_min] = _op_min
    O[op_min_u] = _op_min_u

    # reg_reg_imm_imm
    O[op_load_imm_jump_ind] = _op_load_imm_jump_ind

    # reg_reg_offset
    O[op_branch_eq] = _op_branch_eq
    O[op_branch_ne] = _op_branch_ne
    O[op_branch_lt_u] = _op_branch_lt_u
    O[op_branch_lt_s] = _op_branch_lt_s
    O[op_branch_ge_u] = _op_branch_ge_u
    O[op_branch_ge_s] = _op_branch_ge_s

    # reg_reg_imm
    O[op_store_ind_u8] = _op_store_ind_u8
    O[op_store_ind_u16] = _op_store_ind_u16
    O[op_store_ind_u32] = _op_store_ind_u32
    O[op_store_ind_u64] = _op_store_ind_u64
    O[op_load_ind_u8] = _op_load_ind_u8
    O[op_load_ind_i8] = _op_load_ind_i8
    O[op_load_ind_u16] = _op_load_ind_u16
    O[op_load_ind_i16] = _op_load_ind_i16
    O[op_load_ind_u32] = _op_load_ind_u32
    O[op_load_ind_i32] = _op_load_ind_i32
    O[op_load_ind_u64] = _op_load_ind_u64
    O[op_add_imm_32] = _op_add_imm_32
    O[op_and_imm] = _op_and_imm
    O[op_xor_imm] = _op_xor_imm
    O[op_or_imm] = _op_or_imm
    O[op_mul_imm_32] = _op_mul_imm_32
    O[op_set_lt_u_imm] = _op_set_lt_u_imm
    O[op_set_lt_s_imm] = _op_set_lt_s_imm
    O[op_shlo_l_imm_32] = _op_shlo_l_imm_32
    O[op_shlo_r_imm_32] = _op_shlo_r_imm_32
    O[op_shar_r_imm_32] = _op_shar_r_imm_32
    O[op_neg_add_imm_32] = _op_neg_add_imm_32
    O[op_set_gt_u_imm] = _op_set_gt_u_imm
    O[op_set_gt_s_imm] = _op_set_gt_s_imm
    O[op_shlo_l_imm_alt_32] = _op_shlo_l_imm_alt_32
    O[op_shlo_r_imm_alt_32] = _op_shlo_r_imm_alt_32
    O[op_shar_r_imm_alt_32] = _op_shar_r_imm_alt_32
    O[op_cmov_iz_imm] = _op_cmov_iz_imm
    O[op_cmov_nz_imm] = _op_cmov_nz_imm
    O[op_add_imm_64] = _op_add_imm_64
    O[op_mul_imm_64] = _op_mul_imm_64
    O[op_shlo_l_imm_64] = _op_shlo_l_imm_64
    O[op_shlo_r_imm_64] = _op_shlo_r_imm_64
    O[op_shar_r_imm_64] = _op_shar_r_imm_64
    O[op_neg_add_imm_64] = _op_neg_add_imm_64
    O[op_shlo_l_imm_alt_64] = _op_shlo_l_imm_alt_64
    O[op_shlo_r_imm_alt_64] = _op_shlo_r_imm_alt_64
    O[op_shar_r_imm_alt_64] = _op_shar_r_imm_alt_64
    O[op_rot_r_64_imm] = _op_rot_r_64_imm
    O[op_rot_r_64_imm_alt] = _op_rot_r_64_imm_alt
    O[op_rot_r_32_imm] = _op_rot_r_32_imm
    O[op_rot_r_32_imm_alt] = _op_rot_r_32_imm_alt

    return O
