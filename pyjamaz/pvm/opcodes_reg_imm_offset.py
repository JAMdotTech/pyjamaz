from pyjamaz.pvm.defs import pvm_X, read_uint, pvm_Z


def _fetch_reg_imm_offset(vm):
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = int(min(4, (vm.mv_code[vm.pc + 1] // 16) % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1)))
    v_y = pvm_Z(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    return r_a, w_a, v_x, v_y


def _op_load_imm_jump(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    # Parity with legacy: set skip_len directly and then write reg
    vm.skip_len = v_y
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_eq_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a == v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_ne_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a != v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_lt_u_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a < v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_le_u_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a <= v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_ge_u_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a >= v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_gt_u_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, w_a > v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_lt_s_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, pvm_Z(w_a, 8) < pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_le_s_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, pvm_Z(w_a, 8) <= pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_ge_s_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, pvm_Z(w_a, 8) >= pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

def _op_branch_gt_s_imm(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_offset(vm)
    vm.branch(v_y, pvm_Z(w_a, 8) > pvm_Z(v_x, 8))
    vm.log and vm.log(reg1=r_a, imm1=v_x, off1=v_y)

