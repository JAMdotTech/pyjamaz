from enum import Enum

import numpy as np

# Instruction argument length bitmask
BITMASK_MAX = 24

class InstructionType(Enum):
    """
    This enum serves as classification for how instructions should be decoded
    """
    none: np.uint8                                      = np.uint8(0)
    reg_imm: np.uint8                                   = np.uint8(1)
    reg_imm_offset: np.uint8                            = np.uint8(2)
    reg_imm_imm: np.uint8                               = np.uint8(3)
    reg_reg_imm: np.uint8                               = np.uint8(4)
    reg_reg_offset: np.uint8                            = np.uint8(5)
    reg_reg_reg: np.uint8                               = np.uint8(6)
    offset: np.uint8                                    = np.uint8(7)
    imm: np.uint8                                       = np.uint8(8)
    imm_imm: np.uint8                                   = np.uint8(9)
    reg_reg: np.uint8                                   = np.uint8(10)
    reg_reg_imm_imm: np.uint8                           = np.uint8(11)


class Opcode(Enum):
    """
    This enum serves as a readable lookup for the different opcodes defined in gp::
    TODO: gp ref
    """
    # Instructions with args: none
    trap: np.uint8                                      = np.uint8(0)
    fallthrough: np.uint8                               = np.uint8(17)

    # Instructions with args: reg, imm
    jump_indirect: np.uint8                             = np.uint8(19)
    load_imm: np.uint8                                  = np.uint8(4)
    load_u8: np.uint8                                   = np.uint8(60)
    load_i8: np.uint8                                   = np.uint8(74)
    load_u16: np.uint8                                  = np.uint8(76)
    load_i16: np.uint8                                  = np.uint8(66)
    load_u32: np.uint8                                  = np.uint8(10)
    store_u8: np.uint8                                  = np.uint8(71)
    store_u16: np.uint8                                 = np.uint8(69)
    store_u32: np.uint8                                 = np.uint8(22)

    # Instructions with args: reg, imm, offset
    load_imm_and_jump: np.uint8                         = np.uint8(6)
    branch_eq_imm: np.uint8                             = np.uint8(7)
    branch_not_eq_imm: np.uint8                         = np.uint8(15)
    branch_less_unsigned_imm: np.uint8                  = np.uint8(44)
    branch_less_signed_imm: np.uint8                    = np.uint8(32)
    branch_greater_or_equal_unsigned_imm: np.uint8      = np.uint8(52)
    branch_greater_or_equal_signed_imm: np.uint8        = np.uint8(45)
    branch_less_or_equal_signed_imm: np.uint8           = np.uint8(46)
    branch_less_or_equal_unsigned_imm: np.uint8         = np.uint8(59)
    branch_greater_signed_imm: np.uint8                 = np.uint8(53)
    branch_greater_unsigned_imm: np.uint8               = np.uint8(50)

    store_imm_indirect_u8: np.uint8                     = np.uint8(26)
    store_imm_indirect_u16: np.uint8                    = np.uint8(54)
    store_imm_indirect_u32: np.uint8                    = np.uint8(13)

    # Instructions with args: reg, imm, imm
    store_indirect_u8: np.uint8                         = np.uint8(16)
    store_indirect_u16: np.uint8                        = np.uint8(29)
    store_indirect_u32: np.uint8                        = np.uint8(3)
    load_indirect_u8: np.uint8                          = np.uint8(11)
    load_indirect_i8: np.uint8                          = np.uint8(21)
    load_indirect_u16: np.uint8                         = np.uint8(37)
    load_indirect_i16: np.uint8                         = np.uint8(33)
    load_indirect_u32: np.uint8                         = np.uint8(1)
    add_imm: np.uint8                                   = np.uint8(2)
    and_imm: np.uint8                                   = np.uint8(18)
    xor_imm: np.uint8                                   = np.uint8(31)
    or_imm: np.uint8                                    = np.uint8(49)
    mul_imm: np.uint8                                   = np.uint8(35)
    mul_upper_signed_signed_imm: np.uint8               = np.uint8(65)
    mul_upper_unsigned_unsigned_imm: np.uint8           = np.uint8(63)
    set_less_than_unsigned_imm: np.uint8                = np.uint8(27)
    set_less_than_signed_imm: np.uint8                  = np.uint8(56)
    shift_logical_left_imm: np.uint8                    = np.uint8(9)
    shift_logical_right_imm: np.uint8                   = np.uint8(14)
    shift_arithmetic_right_imm: np.uint8                = np.uint8(25)
    negate_and_add_imm: np.uint8                        = np.uint8(40)
    set_greater_than_unsigned_imm: np.uint8             = np.uint8(39)
    set_greater_than_signed_imm: np.uint8               = np.uint8(61)
    shift_logical_right_imm_alt: np.uint8               = np.uint8(72)
    shift_arithmetic_right_imm_alt: np.uint8            = np.uint8(80)
    shift_logical_left_imm_alt: np.uint8                = np.uint8(75)

    # Instructions with args: reg, reg, imm
    cmov_if_zero_imm: np.uint8                          = np.uint8(85)
    cmov_if_not_zero_imm: np.uint8                      = np.uint8(86)

    # Instructions with args: reg, reg, offset
    branch_eq: np.uint8                                 = np.uint8(24)
    branch_not_eq: np.uint8                             = np.uint8(30)
    branch_less_unsigned: np.uint8                      = np.uint8(47)
    branch_less_signed: np.uint8                        = np.uint8(48)
    branch_greater_or_equal_unsigned: np.uint8          = np.uint8(41)
    branch_greater_or_equal_signed: np.uint8            = np.uint8(43)

    # Instructions with args: reg, reg, reg
    add: np.uint8                                       = np.uint8(8)
    sub: np.uint8                                       = np.uint8(20)
    _and: np.uint8                                      = np.uint8(23)
    xor: np.uint8                                       = np.uint8(28)
    _or: np.uint8                                       = np.uint8(12)
    mul: np.uint8                                       = np.uint8(34)
    mul_upper_signed_signed: np.uint8                   = np.uint8(67)
    mul_upper_unsigned_unsigned: np.uint8               = np.uint8(57)
    mul_upper_signed_unsigned: np.uint8                 = np.uint8(81)
    set_less_than_unsigned: np.uint8                    = np.uint8(36)
    set_less_than_signed: np.uint8                      = np.uint8(58)
    shift_logical_left: np.uint8                        = np.uint8(55)
    shift_logical_right: np.uint8                       = np.uint8(51)
    shift_arithmetic_right: np.uint8                    = np.uint8(77)
    div_unsigned: np.uint8                              = np.uint8(68)
    div_signed: np.uint8                                = np.uint8(64)
    rem_unsigned: np.uint8                              = np.uint8(73)
    rem_signed: np.uint8                                = np.uint8(70)

    cmov_if_zero: np.uint8                              = np.uint8(83)
    cmov_if_not_zero: np.uint8                          = np.uint8(84)

    # Instructions with args: offset
    jump: np.uint8                                      = np.uint8(5)

    # Instructions with args: imm
    ecalli: np.uint8                                    = np.uint8(78)

    # Instructions with args: imm, imm
    store_imm_u8: np.uint8                              = np.uint8(62)
    store_imm_u16: np.uint8                             = np.uint8(79)
    store_imm_u32: np.uint8                             = np.uint8(38)

    # Instructions with args: reg, reg
    move_reg: np.uint8                                  = np.uint8(82)
    sbrk: np.uint8                                      = np.uint8(87)

    # Instructions with args: reg, reg, imm, imm
    load_imm_and_jump_indirect: np.uint8                = np.uint8(42)


"""
This enum serves as a lookup for the instruction decoding scheme we should apply for a given opcode
"""
it = InstructionType
op = Opcode

OpcodeScheme = {
    # Instructions with args: none
    op.trap.value                                             : it.none,    #riscv:??? zoek dit opcode nr op
    op.fallthrough.value                                      : it.none,    #riscv:???

    # Instructions with args: reg, imm
    op.jump_indirect.value                                    : it.reg_imm, #X
    op.load_imm.value                                         : it.reg_imm, #riscv:li
    op.load_u8.value                                          : it.reg_imm, #riscv:lbu
    op.load_i8.value                                          : it.reg_imm, #X riscv:lb
    op.load_u16.value                                         : it.reg_imm, #X riscv:lhu
    op.load_i16.value                                         : it.reg_imm, #X riscv:lh
    op.load_u32.value                                         : it.reg_imm, #X riscv:lw
    op.store_u8.value                                         : it.reg_imm, #riscv:sb
    op.store_u16.value                                        : it.reg_imm, #riscv:sh
    op.store_u32.value                                        : it.reg_imm, #riscv:sw

    # Instructions with args: reg, imm, offset
    op.load_imm_and_jump.value                                : it.reg_imm_offset, #X
    op.branch_eq_imm.value                                    : it.reg_imm_offset, #riscv:beq
    op.branch_not_eq_imm.value                                : it.reg_imm_offset, #riscv:bne

    op.branch_less_unsigned_imm.value                         : it.reg_imm_offset, #riscv:bltu
    op.branch_greater_or_equal_unsigned_imm.value             : it.reg_imm_offset, #riscv:
    op.branch_less_or_equal_unsigned_imm.value                : it.reg_imm_offset, #riscv:
    op.branch_greater_unsigned_imm.value                      : it.reg_imm_offset, #riscv:

    op.branch_less_signed_imm.value                           : it.reg_imm_offset, #riscv:
    op.branch_greater_or_equal_signed_imm.value               : it.reg_imm_offset, #riscv:
    op.branch_less_or_equal_signed_imm.value                  : it.reg_imm_offset, #riscv:
    op.branch_greater_signed_imm.value                        : it.reg_imm_offset, #riscv:

    # Instructions with args: reg, imm, imm
    op.store_imm_indirect_u8.value                            : it.reg_imm_imm, #X
    op.store_imm_indirect_u16.value                           : it.reg_imm_imm, #X
    op.store_imm_indirect_u32.value                           : it.reg_imm_imm, #X

    # Instructions with args: reg, reg, imm
    op.store_indirect_u8.value                                : it.reg_reg_imm, #X
    op.store_indirect_u16.value                               : it.reg_reg_imm, #X
    op.store_indirect_u32.value                               : it.reg_reg_imm, #X
    op.load_indirect_u8.value                                 : it.reg_reg_imm, #X
    op.load_indirect_i8.value                                 : it.reg_reg_imm, #X
    op.load_indirect_u16.value                                : it.reg_reg_imm, #X
    op.load_indirect_i16.value                                : it.reg_reg_imm, #X
    op.load_indirect_u32.value                                : it.reg_reg_imm, #X
    op.add_imm.value                                          : it.reg_reg_imm, #riscv:addi
    op.and_imm.value                                          : it.reg_reg_imm, #riscv:andi
    op.xor_imm.value                                          : it.reg_reg_imm, #riscv:xori
    op.or_imm.value                                           : it.reg_reg_imm, #riscv:ori
    op.mul_imm.value                                          : it.reg_reg_imm, #riscv:muli
    op.mul_upper_signed_signed_imm.value                      : it.reg_reg_imm, #X
    op.mul_upper_unsigned_unsigned_imm.value                  : it.reg_reg_imm, #X
    op.set_less_than_unsigned_imm.value                       : it.reg_reg_imm, #riscv:
    op.set_less_than_signed_imm.value                         : it.reg_reg_imm, #riscv:
    op.shift_logical_left_imm.value                           : it.reg_reg_imm, #riscv:
    op.shift_logical_right_imm.value                          : it.reg_reg_imm, #riscv:
    op.shift_arithmetic_right_imm.value                       : it.reg_reg_imm, #riscv:
    op.negate_and_add_imm.value                               : it.reg_reg_imm, #riscv:
    op.set_greater_than_unsigned_imm.value                    : it.reg_reg_imm, #riscv:
    op.set_greater_than_signed_imm.value                      : it.reg_reg_imm, #riscv:
    op.shift_logical_right_imm_alt.value                      : it.reg_reg_imm, #riscv:
    op.shift_arithmetic_right_imm_alt.value                   : it.reg_reg_imm, #riscv:
    op.shift_logical_left_imm_alt.value                       : it.reg_reg_imm, #riscv:

    op.cmov_if_zero_imm.value                                 : it.reg_reg_imm, #riscv:
    op.cmov_if_not_zero_imm.value                             : it.reg_reg_imm, #riscv:

    # Instructions with args: reg, reg, offset
    op.branch_eq.value                                        : it.reg_reg_offset,  #riscv:
    op.branch_not_eq.value                                    : it.reg_reg_offset,  #riscv:
    op.branch_less_unsigned.value                             : it.reg_reg_offset,  #riscv:
    op.branch_less_signed.value                               : it.reg_reg_offset,  #riscv:
    op.branch_greater_or_equal_unsigned.value                 : it.reg_reg_offset,  #riscv:
    op.branch_greater_or_equal_signed.value                   : it.reg_reg_offset,  #riscv:

    # Instructions with args: reg, reg, reg
    op.add.value                                              : it.reg_reg_reg, #riscv:add
    op.sub.value                                              : it.reg_reg_reg, #riscv:sub
    op._and.value                                             : it.reg_reg_reg, #riscv:and
    op.xor.value                                              : it.reg_reg_reg, #riscv:xor
    op._or.value                                              : it.reg_reg_reg, #riscv:or
    op.mul.value                                              : it.reg_reg_reg, #riscv:mul
    op.mul_upper_signed_signed.value                          : it.reg_reg_reg, #X
    op.mul_upper_unsigned_unsigned.value                      : it.reg_reg_reg, #X
    op.mul_upper_signed_unsigned.value                        : it.reg_reg_reg, #X
    op.set_less_than_unsigned.value                           : it.reg_reg_reg, #riscv:sltu
    op.set_less_than_signed.value                             : it.reg_reg_reg, #riscv:slt
    op.shift_logical_left.value                               : it.reg_reg_reg, #riscv:sll
    op.shift_logical_right.value                              : it.reg_reg_reg, #riscv:srl
    op.shift_arithmetic_right.value                           : it.reg_reg_reg, #riscv:sra
    op.div_unsigned.value                                     : it.reg_reg_reg, #riscv:divu
    op.div_signed.value                                       : it.reg_reg_reg, #riscv:div
    op.rem_unsigned.value                                     : it.reg_reg_reg, #riscv:remu
    op.rem_signed.value                                       : it.reg_reg_reg, #riscv:rem

    op.cmov_if_zero.value                                     : it.reg_reg_reg, #riscv:https://stackoverflow.com/questions/72340698/riscv-branchless-coding
    op.cmov_if_not_zero.value                                 : it.reg_reg_reg, #X

    # Instructions with args: offset
    op.jump.value                                             : it.offset,

    # Instructions with args: imm
    op.ecalli.value                                           : it.imm,

    # Instructions with args: imm, imm
    op.store_imm_u8.value                                     : it.imm_imm,
    op.store_imm_u16.value                                    : it.imm_imm,
    op.store_imm_u32.value                                    : it.imm_imm,

    # Instructions with args: reg, reg
    op.move_reg.value                                         : it.reg_reg, #riscv:
    op.sbrk.value                                             : it.reg_reg, #X

    # Instructions with args: reg, reg, imm, im:
    op.load_imm_and_jump_indirect.value                       : it.reg_reg_imm_imm,
}
