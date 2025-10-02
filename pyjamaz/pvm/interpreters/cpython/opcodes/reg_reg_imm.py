from pyjamaz.pvm.constants import op_store_ind_u8, op_store_ind_u16, op_store_ind_u32, op_store_ind_u64, op_load_ind_u8, \
    op_load_ind_i8, op_load_ind_u16, op_load_ind_i16, op_load_ind_u32, op_load_ind_i32, op_load_ind_u64
from ..defs import pvm_X, read_uint, u32, u8, u16, pvm_Z_inv, pvm_Z, MASK32, u64, MASK64, rori64, rori32


def _fetch_reg_reg_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    r_b = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    inst_index = vm.inst_pos[vm.pc]
    l_x = min(4, max(0, vm.mv_inst_arg_len[inst_index] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    return r_a, r_b, w_a, w_b, v_x


def _op_store_ind_u8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u8, u32(w_b + v_x), u8(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u8(w_a), "w_b": w_b})

def _op_store_ind_u16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u16, u32(w_b + v_x), u16(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u16(w_a), "w_b": w_b})

def _op_store_ind_u32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u32, u32(w_b + v_x), u32(w_a))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": u32(w_a), "w_b": w_b})

def _op_store_ind_u64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.mem_write(op_store_ind_u64, u32(w_b + v_x), w_a)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_u8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u8, u32(w_b + v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_i8(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i8, u32(w_b + v_x)), 1), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_u16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u16, u32(w_b + v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_i16(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i16, u32(w_b + v_x)), 2), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_u32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u32, u32(w_b + v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_i32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(vm.mem_read(op_load_ind_i32, u32(w_b + v_x)), 4), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_load_ind_u64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_ind_u64, u32(w_b + v_x))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

def _op_add_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(w_b + v_x), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_and_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b & v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_xor_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b ^ v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_or_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = w_b | v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_mul_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(w_b * v_x), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_set_lt_u_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if w_b < v_x else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_set_lt_s_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if pvm_Z(w_b, 8) < pvm_Z(v_x, 8) else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_shlo_l_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(w_b << (v_x & 31)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_shlo_r_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(w_b) >> (v_x & 31), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

def _op_shar_r_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(w_b & MASK32, 4) >> (v_x & 31), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_neg_add_imm_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(v_x + (1 << 32) - w_b), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_set_gt_u_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if w_b > v_x else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_set_gt_s_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = 1 if pvm_Z(w_b, 8) > pvm_Z(v_x, 8) else 0
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_l_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(v_x << (w_b & 31)), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_r_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(u32(v_x) >> (w_b & 31), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shar_r_imm_alt_32(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    shift = w_b & 31
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(v_x & 0xFFFFFFFF, 4) >> shift, 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_cmov_iz_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    if w_b == 0:
        vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_cmov_nz_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    if w_b != 0:
        vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_add_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = u64(w_b + v_x)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_mul_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = u64(w_b * v_x)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_l_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X((w_b << (v_x & 63)), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_r_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(w_b >> (v_x & 63), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shar_r_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_Z_inv(pvm_Z(w_b, 8) >> (v_x & 63), 8)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_neg_add_imm_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = ((v_x + (1 << 64) - w_b) & MASK64)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_l_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = (v_x << (w_b & 63)) & MASK64
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shlo_r_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = v_x >> (w_b & 63)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_shar_r_imm_alt_64(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    signed_val = pvm_Z(v_x, 8)
    shift_amount = w_b & 63
    shifted = signed_val >> shift_amount
    if shifted < 0:
        shifted = shifted + (1 << 64)
    vm.reg[r_a] = shifted & MASK64
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_rot_r_64_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = rori64(w_b, v_x)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_rot_r_64_imm_alt(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = rori64(v_x, w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_rot_r_32_imm(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(rori32(w_b, v_x), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})

def _op_rot_r_32_imm_alt(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_imm(vm)
    vm.reg[r_a] = pvm_X(rori32(v_x, w_b), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": vm.reg[r_a]})
