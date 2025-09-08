from pyjamaz.pvm.defs import pvm_Z, read_uint


def _fetch_offset(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = min(4, vm.inst_arg_len[inst_index])
    v_x = pvm_Z(read_uint(vm.mv_code, vm.pc + 1, l_x), l_x)
    return v_x


def _op_jump(vm):
    v_x = _fetch_offset(vm)
    vm.skip_len = v_x
    vm.log and vm.log(off1=v_x, context={"skip_len": v_x})
