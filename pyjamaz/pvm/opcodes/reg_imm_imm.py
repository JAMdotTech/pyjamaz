from pyjamaz.pvm.constants import op_store_imm_ind_u8, op_store_imm_ind_u16, op_store_imm_ind_u32, op_store_imm_ind_u64
from pyjamaz.pvm.defs import pvm_X, read_uint, u32, u16, u8


def _fetch_reg_imm_imm(vm):
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    w_a = vm.reg[r_a]
    l_x = min(4, (vm.mv_code[vm.pc + 1] // 16) % 8)
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    l_y = min(4, max(0, vm.mv_inst_arg_len[vm.inst_pos[vm.pc]] - l_x - 1))
    v_y = pvm_X(read_uint(vm.mv_code, vm.pc + 2 + l_x, l_y), l_y)
    return r_a, w_a, v_x, v_y


def _op_store_imm_ind_u8(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = u32(w_a + v_x)
    vm.mem_write(op_store_imm_ind_u8, addr, u8(v_y))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 1)})

def _op_store_imm_ind_u16(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = u32(w_a + v_x)
    vm.mem_write(op_store_imm_ind_u16, addr, u16(v_y))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 2)})

def _op_store_imm_ind_u32(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = u32(w_a + v_x)
    vm.mem_write(op_store_imm_ind_u32, addr, u32(v_y))
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 4)})

def _op_store_imm_ind_u64(vm):
    r_a, w_a, v_x, v_y = _fetch_reg_imm_imm(vm)
    addr = u32(w_a + v_x)
    vm.mem_write(op_store_imm_ind_u64, addr, v_y)
    vm.log and vm.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_(vx+wa)": vm._mem_read_int(addr, 8)})
