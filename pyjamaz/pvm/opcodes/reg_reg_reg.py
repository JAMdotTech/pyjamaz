from pyjamaz.pvm.defs import u64, pvm_X, u32, pvm_Z, pvm_Z_inv, pvm_rtz_div, MASK32, pvm_smod, roli64, rotl32, rori64, rotr32, \
    MASK64


def _fetch_reg_reg_reg(vm):
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    r_b = min(12, vm.mv_code[vm.pc + 1] // 16)
    r_d = min(12, vm.mv_code[vm.pc + 2])
    a = vm.reg[r_a]
    b = vm.reg[r_b]
    return r_a, r_b, r_d, a, b


def _op_add_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a + b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_add_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a + b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_sub_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a + (1 << 32) - u32(b)), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_mul_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(u32(a * b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_div_u_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    else:
        vm.reg[r_d] = pvm_X(u32(a) // u32(b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_div_s_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s32 = pvm_Z(u32(a), 4)
    b_s32 = pvm_Z(u32(b), 4)
    if b_s32 == 0:
        vm.reg[r_d] = (1 << 64) - 1
    elif a_s32 == -(1 << 31) and b_s32 == -1:
        vm.reg[r_d] = pvm_Z_inv(a_s32, 8)
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_rtz_div(a_s32, b_s32), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rem_u_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if (b & MASK32) == 0:
        vm.reg[r_d] = pvm_X(a & MASK32, 4)
    else:
        vm.reg[r_d] = pvm_X((a & MASK32) % (b & MASK32), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rem_s_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s32 = pvm_Z(u32(a), 4)
    b_s32 = pvm_Z(u32(b), 4)
    if b_s32 == 0:
        vm.reg[r_d] = pvm_Z_inv(a_s32, 8)
    elif a_s32 == -(1 << 31) and b_s32 == -1:
        vm.reg[r_d] = 0
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_smod(a_s32, b_s32), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shlo_l_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X((a << (b & 31)) & MASK32, 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shlo_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X((a & MASK32) >> (b & 31), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shar_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    val_32 = a & MASK32
    if val_32 >= (1 << 31):
        val_32 = val_32 - (1 << 32)
    result = val_32 >> (b & 31)
    if result < 0:
        result = result + (1 << 64)
    vm.reg[r_d] = pvm_Z_inv(result, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_sub_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a + (1 << 64) - b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_mul_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a * b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_div_u_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    else:
        vm.reg[r_d] = a // b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_div_s_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = (1 << 64) - 1
    elif pvm_Z(a, 8) == -(1 << 63) and pvm_Z(b, 8) == -1:
        vm.reg[r_d] = a
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_rtz_div(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rem_u_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = a
    else:
        vm.reg[r_d] = a % b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rem_s_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    a_s64 = pvm_Z(a, 8)
    b_s64 = pvm_Z(b, 8)
    if b == 0:
        vm.reg[r_d] = a
    elif a_s64 == -(1 << 63) and b_s64 == -1:
        vm.reg[r_d] = 0
    else:
        vm.reg[r_d] = pvm_Z_inv(pvm_smod(a_s64, b_s64), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shlo_l_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a << (b & 63))
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shlo_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a >> (b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_shar_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    signed_val = pvm_Z(a, 8)
    shifted = signed_val >> (b & 63)
    vm.reg[r_d] = pvm_Z_inv(shifted, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_and(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a & b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_xor(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a ^ b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_or(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a | b
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_mul_upper_s_s(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv((pvm_Z(a, 8) * pvm_Z(b, 8)) >> 64, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_mul_upper_u_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = (a * b) >> 64
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_mul_upper_s_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv((pvm_Z(a, 8) * b) >> 64, 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_set_lt_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(a < b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_set_lt_s(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = u64(pvm_Z(a, 8) < pvm_Z(b, 8))
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_cmov_iz(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b == 0:
        vm.reg[r_d] = a
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_cmov_nz(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    if b != 0:
        vm.reg[r_d] = a
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rot_l_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = roli64(a, b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rot_l_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(rotl32(a, b), 4)
    vm.log and vm.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rot_r_64(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = rori64(a, b & 63)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_rot_r_32(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_X(rotr32(a, b), 4)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_and_inv(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a & u64(~b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_or_inv(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = a | u64(~b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_xnor(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = ~(a ^ b) & MASK64
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_max(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(max(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_max_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = max(a, b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_min(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(min(pvm_Z(a, 8), pvm_Z(b, 8)), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})

def _op_min_u(vm):
    r_a, r_b, r_d, a, b = _fetch_reg_reg_reg(vm)
    vm.reg[r_d] = min(a, b)
    vm.log and vm.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": vm.reg[r_d]})
