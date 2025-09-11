from pyjamaz.pvm.constants import op_store_imm_u8, op_store_imm_u16, op_store_imm_u32, op_store_imm_u64
from pyjamaz.pvm.defs import pvm_X, read_uint, u32


def _fetch_imm_imm(vm):
    inst_index = vm.inst_pos[vm.pc]
    l_x = min(4, vm.mv_code[vm.pc + 1] % 8)
    l_y = min(4, max(0, vm.mv_inst_arg_len[inst_index] - l_x - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    return v_x, v_y


def _op_store_imm_u8(vm):
    v_x, v_y = _fetch_imm_imm(vm)
    vm.mem_write(op_store_imm_u8, v_x, v_y % 2 ** 8)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 1)})

def _op_store_imm_u16(vm):
    v_x, v_y = _fetch_imm_imm(vm)
    vm.mem_write(op_store_imm_u16, v_x, v_y % 2 ** 16)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 2)})

def _op_store_imm_u32(vm):
    v_x, v_y = _fetch_imm_imm(vm)
    vm.mem_write(op_store_imm_u32, v_x, u32(v_y))
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 4)})

def _op_store_imm_u64(vm):
    v_x, v_y = _fetch_imm_imm(vm)
    vm.mem_write(op_store_imm_u64, v_x, v_y)
    vm.log and vm.log(imm1=v_x, imm2=v_y, context={"u'_vx": vm._mem_read_int(v_x, 8)})
