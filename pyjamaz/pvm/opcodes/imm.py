from pyjamaz.pvm.constants import ExitReason
from pyjamaz.pvm.defs import pvm_X, read_uint


def _fetch_imm(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = min(4, vm.mv_inst_arg_len[inst_index])
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 1, l_x), l_x)
    return v_x


def _op_ecalli(vm):
    v_x = _fetch_imm(vm)
    vm.status = ExitReason.host_halt.value
    vm.exit_value = v_x
    vm.log and vm.log(imm1=v_x)
