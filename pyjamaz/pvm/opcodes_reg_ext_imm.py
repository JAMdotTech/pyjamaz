from pvm.defs import read_uint


def _fetch_reg_ext_imm(vm):
    r_a = min(12, vm.code[vm.pc + 1] % 16)
    v_x = read_uint(vm.mv_code, vm.pc + 2, 8)
    return r_a, v_x


def _op_load_imm_64(vm):
    r_a, v_x = _fetch_reg_ext_imm(vm)
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x)