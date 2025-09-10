from pyjamaz.pvm.defs import pvm_Z, read_uint


def _fetch_reg_reg_offset(vm):
    inst_index = vm.inst_pos[vm.pc]
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    r_b = min(12, vm.mv_code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    w_b = vm.reg[r_b]
    l_x = min(4, max(0, vm.mv_inst_arg_len[inst_index] - 1))
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    return r_a, r_b, w_a, w_b, v_x


def _op_branch_eq(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, w_a == w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)

def _op_branch_ne(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, w_a != w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)

def _op_branch_lt_u(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, w_a < w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)

def _op_branch_lt_s(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, pvm_Z(w_a, 8) < pvm_Z(w_b, 8))
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)

def _op_branch_ge_u(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, w_a >= w_b)
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)

def _op_branch_ge_s(vm):
    r_a, r_b, w_a, w_b, v_x = _fetch_reg_reg_offset(vm)
    vm.branch(v_x, pvm_Z(w_a, 8) >= pvm_Z(w_b, 8))
    vm.log and vm.log(reg1=r_a, reg2=r_b, off1=v_x)
