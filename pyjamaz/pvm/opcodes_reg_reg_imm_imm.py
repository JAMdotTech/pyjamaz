from pvm.defs import pvm_X, read_uint, u32


def _fetch_reg_reg_imm_imm(vm):
    inst_index = vm.inst_pos[vm.pc]
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    r_b = min(12, vm.mv_code[vm.pc + 1] // 16)
    w_b = vm.reg[r_b]
    l_x = int(min(4, vm.mv_code[vm.pc + 2] % 8))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 3, l_x), l_x)
    l_y = int(min(4, max(0, vm.inst_arg_len[inst_index] - l_x - 2)))
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 3 + l_x, l_y), l_y)
    return r_a, r_b, w_b, v_x, v_y


def _op_load_imm_jump_ind(vm):
    r_a, r_b, w_b, v_x, v_y = _fetch_reg_reg_imm_imm(vm)
    vm.reg[r_a] = v_x
    vm.skip_len = vm.djump(u32(int(w_b) + int(v_y)))
    vm.log and vm.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": vm.skip_len})