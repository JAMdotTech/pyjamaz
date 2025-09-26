from pyjamaz.pvm.constants import op_load_u8, op_load_i8, op_load_u16, op_load_i16, op_load_u32, op_load_i32, op_load_u64, \
    op_store_u8, op_store_u16, op_store_u32, op_store_u64
from ..defs import pvm_X, read_uint, u32, u8, u16


def _fetch_reg_imm(vm):
    r_a = min(12, vm.mv_code[vm.pc + 1] % 16)
    l_x = min(4, max(0, vm.mv_inst_arg_len[vm.inst_pos[vm.pc]] - 1))
    v_x = pvm_X(read_uint(vm.mv_code, vm.pc + 2, l_x), l_x)
    return r_a, v_x


def _op_jump_ind(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.skip_len = vm.djump(u32(vm.reg[r_a] + v_x))
    vm.log and vm.log(reg1=r_a, imm1=v_x, context={"skip_len": vm.skip_len})

def _op_load_imm(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = v_x
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_u8(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_u8, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_i8(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i8, v_x), 1)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_u16(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_u16, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)


def _op_load_i16(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i16, v_x), 2)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_u32(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_u32, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_i32(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = pvm_X(vm.mem_read(op_load_i32, v_x), 4)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_load_u64(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.reg[r_a] = vm.mem_read(op_load_u64, v_x)
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_store_u8(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.mem_write(op_store_u8, v_x, u8(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_store_u16(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.mem_write(op_store_u16, v_x, u16(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_store_u32(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.mem_write(op_store_u32, v_x, u32(vm.reg[r_a]))
    vm.log and vm.log(reg1=r_a, imm1=v_x)

def _op_store_u64(vm):
    r_a, v_x = _fetch_reg_imm(vm)
    vm.mem_write(op_store_u64, v_x, vm.reg[r_a])
    vm.log and vm.log(reg1=r_a, imm1=v_x)
