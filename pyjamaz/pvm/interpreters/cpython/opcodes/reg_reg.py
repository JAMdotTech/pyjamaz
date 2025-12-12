from ..defs import count_leading_zeroes, count_trailing_zeroes, pvm_Z_inv, pvm_Z, u16, u8, reverse_bytes


def _fetch_reg_reg(vm):
    r_d = min(12, vm.code[vm.pc + 1] % 16)
    r_a = min(12, vm.code[vm.pc + 1] // 16)
    w_a = vm.reg[r_a]
    return r_d, r_a, w_a


def _op_move_reg(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = w_a
    vm.log and vm.log(reg1=r_d, reg2=r_a)

def _op_sbrk(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = vm._sbrk(w_a)
    vm.log and vm.log(reg1=r_d, reg2=r_a)

def _op_count_set_bits_64(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = w_a.bit_count()
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_count_set_bits_32(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = (w_a & 0xFFFFFFFF).bit_count()
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_leading_zero_bits_64(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = count_leading_zeroes(w_a, 64)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_leading_zero_bits_32(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = count_leading_zeroes(w_a, 32)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_trailing_zero_bits_64(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = count_trailing_zeroes(w_a, 64)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_trailing_zero_bits_32(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = count_trailing_zeroes(w_a, 32)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_sign_extend_8(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(pvm_Z(u8(w_a), 1), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_sign_extend_16(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = pvm_Z_inv(pvm_Z(u16(w_a), 2), 8)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_zero_extend_16(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = u16(w_a)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})

def _op_reverse_bytes(vm):
    r_d, r_a, w_a = _fetch_reg_reg(vm)
    vm.reg[r_d] = reverse_bytes(w_a)
    vm.log and vm.log(reg1=r_d, reg2=r_a, context={"w'_d": vm.reg[r_d]})
