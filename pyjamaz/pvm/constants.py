from enum import Enum

import numpy as np


class ExitCondition(Enum):
    none:int            = 0
    panic:int           = 1
    halt:int            = 2
    out_of_gas:int      = 3
    page_fault:int      = 4
    host_halt:int       = 5


class InstructionType(Enum):
    """
    This enum serves as classification for how instructions should be decoded
    """
    none: np.uint8                                      = np.uint8(0)   #GP_A.5.1
    imm: np.uint8                                       = np.uint8(1)   #GP_A.5.2
    reg_ext_imm: np.uint8                               = np.uint8(2)   #GP_A.5.3
    imm_imm: np.uint8                                   = np.uint8(3)   #GP_A.5.4
    offset: np.uint8                                    = np.uint8(4)   #GP_A.5.5
    reg_imm: np.uint8                                   = np.uint8(5)   #GP_A.5.6
    reg_imm_imm: np.uint8                               = np.uint8(6)   #GP_A.5.7
    reg_imm_offset: np.uint8                            = np.uint8(7)   #GP_A.5.8
    reg_reg: np.uint8                                   = np.uint8(8)   #GP_A.5.9
    reg_reg_imm: np.uint8                               = np.uint8(9)   #GP_A.5.10
    reg_reg_offset: np.uint8                            = np.uint8(10)  #GP_A.5.11
    reg_reg_imm_imm: np.uint8                           = np.uint8(11)  #GP_A.5.12
    reg_reg_reg: np.uint8                               = np.uint8(12)  #GP_A.5.13


class Opcode(Enum):
    """
    This enum serves as a readable lookup for the different opcodes defined in gp::
    """
    # GP_A.5.1
    # Instructions without Arguments (none)
    trap: np.uint8                                      = np.uint8(0)
    fallthrough: np.uint8                               = np.uint8(1)

    # GP_A.5.2
    # Instructions with Arguments of One Immediate (imm)
    ecalli: np.uint8                                    = np.uint8(10)

    # GP_A.5.3
    # Instructions with Arguments of One Register and One Extended Width Immediate (reg_ext_imm)
    load_imm_64: np.uint8                              = np.uint8(20)   #TODO:NEW->TEST

    # GP_A.5.4
    # Instructions with Arguments of two Immediates (imm_imm)
    store_imm_u8: np.uint8                              = np.uint8(30)
    store_imm_u16: np.uint8                             = np.uint8(31)
    store_imm_u32: np.uint8                             = np.uint8(32)
    store_imm_u64: np.uint8                             = np.uint8(33)  #TODO:NEW->TEST

    # GP_A.5.5
    # Instructions with Arguments of One Offset (offset)
    jump: np.uint8                                      = np.uint8(40)

    # GP_A.5.6
    # Instructions with Arguments Of One Register & One Immediate (reg_imm)
    jump_ind: np.uint8                                  = np.uint8(50)
    load_imm: np.uint8                                  = np.uint8(51)
    load_u8: np.uint8                                   = np.uint8(52)
    load_i8: np.uint8                                   = np.uint8(53)
    load_u16: np.uint8                                  = np.uint8(54)
    load_i16: np.uint8                                  = np.uint8(55)
    load_u32: np.uint8                                  = np.uint8(56)
    load_i32: np.uint8                                  = np.uint8(57)  #TODO:NEW->TEST
    load_u64: np.uint8                                  = np.uint8(58)  #TODO:NEW->TEST
    store_u8: np.uint8                                  = np.uint8(59)
    store_u16: np.uint8                                 = np.uint8(60)
    store_u32: np.uint8                                 = np.uint8(61)
    store_u64: np.uint8                                 = np.uint8(62)  #TODO:NEW->TEST

    # GP_A.5.7
    # Instructions with Arguments Of One Register & Two Immediates (reg_imm_imm)
    store_imm_ind_u8: np.uint8                          = np.uint8(70)
    store_imm_ind_u16: np.uint8                         = np.uint8(71)
    store_imm_ind_u32: np.uint8                         = np.uint8(72)
    store_imm_ind_u64: np.uint8                         = np.uint8(73)  #TODO:NEW->TEST

    # GP_A.5.8
    # Instructions with Arguments Of One Register, One Immediate and One Offset (reg_imm_offset)
    load_imm_jump: np.uint8                             = np.uint8(80)
    branch_eq_imm: np.uint8                             = np.uint8(81)
    branch_ne_imm: np.uint8                             = np.uint8(82)
    branch_lt_u_imm: np.uint8                           = np.uint8(83)
    branch_le_u_imm: np.uint8                           = np.uint8(84)
    branch_ge_u_imm: np.uint8                           = np.uint8(85)
    branch_gt_u_imm: np.uint8                           = np.uint8(86)
    branch_lt_s_imm: np.uint8                           = np.uint8(87)
    branch_le_s_imm: np.uint8                           = np.uint8(88)
    branch_ge_s_imm: np.uint8                           = np.uint8(89)
    branch_gt_s_imm: np.uint8                           = np.uint8(90)

    # GP_A.5.9
    # Instructions with Arguments Of Two Registers (reg_reg)
    move_reg: np.uint8                                  = np.uint8(100)
    sbrk: np.uint8                                      = np.uint8(101)

    # GP_A.5.10
    # Instructions with Arguments Of Two Registers & One Immediate (reg_reg_imm)
    store_ind_u8: np.uint8                              = np.uint8(110)
    store_ind_u16: np.uint8                             = np.uint8(111)
    store_ind_u32: np.uint8                             = np.uint8(112)
    store_ind_u64: np.uint8                             = np.uint8(113) #TODO:NEW->TEST
    load_ind_u8: np.uint8                               = np.uint8(114)
    load_ind_i8: np.uint8                               = np.uint8(115)
    load_ind_u16: np.uint8                              = np.uint8(116)
    load_ind_i16: np.uint8                              = np.uint8(117)
    load_ind_u32: np.uint8                              = np.uint8(118)
    load_ind_i32: np.uint8                              = np.uint8(119) #TODO:NEW->TEST
    load_ind_u64: np.uint8                              = np.uint8(120) #TODO:NEW->TEST
    add_imm_32: np.uint8                                = np.uint8(121) #TODO:NEW->TEST
    and_imm: np.uint8                                   = np.uint8(122)
    xor_imm: np.uint8                                   = np.uint8(123)
    or_imm: np.uint8                                    = np.uint8(124)
    mul_imm_32: np.uint8                                = np.uint8(125) #TODO:NEW->TEST
    set_lt_u_imm: np.uint8                              = np.uint8(126)
    set_lt_s_imm: np.uint8                              = np.uint8(127)
    shlo_l_imm_32: np.uint8                             = np.uint8(128) #TODO:NEW->TEST
    shlo_r_imm_32: np.uint8                             = np.uint8(129) #TODO:NEW->TEST
    shar_r_imm_32: np.uint8                             = np.uint8(130) #TODO:NEW->TEST
    neg_add_imm_32: np.uint8                            = np.uint8(131) #TODO:NEW->TEST
    set_gt_u_imm: np.uint8                              = np.uint8(132)
    set_gt_s_imm: np.uint8                              = np.uint8(133)
    shlo_l_imm_alt_32: np.uint8                         = np.uint8(134) #TODO:NEW->TEST
    shlo_r_imm_alt_32: np.uint8                         = np.uint8(135) #TODO:NEW->TEST
    shar_r_imm_alt_32: np.uint8                         = np.uint8(136) #TODO:NEW->TEST
    cmov_iz_imm: np.uint8                               = np.uint8(137)
    cmov_nz_imm: np.uint8                               = np.uint8(138)
    add_imm_64: np.uint8                                = np.uint8(139) #TODO:NEW->TEST
    mul_imm_64: np.uint8                                = np.uint8(140) #TODO:NEW->TEST
    shlo_l_imm_64: np.uint8                             = np.uint8(141) #TODO:NEW->TEST
    shlo_r_imm_64: np.uint8                             = np.uint8(142) #TODO:NEW->TEST
    shar_r_imm_64: np.uint8                             = np.uint8(143) #TODO:NEW->TEST
    neg_add_imm_64: np.uint8                            = np.uint8(144) #TODO:NEW->TEST
    shlo_l_imm_alt_64: np.uint8                         = np.uint8(145) #TODO:NEW->TEST
    shlo_r_imm_alt_64: np.uint8                         = np.uint8(146) #TODO:NEW->TEST
    shar_r_imm_alt_64: np.uint8                         = np.uint8(147) #TODO:NEW->TEST
    #mul_upper_s_s_imm: np.uint8                         = np.uint8(65) TODO:DEPRECATED?
    #mul_upper_u_u_imm: np.uint8                         = np.uint8(63) TODO:DEPRECATED?

    # GP_A.5.11
    # Instructions with Arguments of Two Registers & One Offset (reg_reg_offset)
    branch_eq: np.uint8                                 = np.uint8(150)
    branch_ne: np.uint8                                 = np.uint8(151)
    branch_lt_u: np.uint8                               = np.uint8(152)
    branch_lt_s: np.uint8                               = np.uint8(153)
    branch_ge_u: np.uint8                               = np.uint8(154)
    branch_ge_s: np.uint8                               = np.uint8(155)

    # GP_A.5.12
    # Instructions with Arguments Of Two Registers And Two Immediates (reg_reg_imm_imm_
    load_imm_jump_ind: np.uint8                         = np.uint8(160)

    # GP_A.5.13
    # Instructions with Arguments Of Three Registers (reg_reg_reg)
    add_32: np.uint8                                    = np.uint8(170) #TODO:NEW->TEST
    sub_32: np.uint8                                    = np.uint8(171) #TODO:NEW->TEST
    mul_32: np.uint8                                    = np.uint8(172) #TODO:NEW->TEST
    div_u_32: np.uint8                                  = np.uint8(173) #TODO:NEW->TEST
    div_s_32: np.uint8                                  = np.uint8(174) #TODO:NEW->TEST
    rem_u_32: np.uint8                                  = np.uint8(175) #TODO:NEW->TEST
    rem_s_32: np.uint8                                  = np.uint8(176) #TODO:NEW->TEST
    shlo_l_32: np.uint8                                 = np.uint8(177) #TODO:NEW->TEST
    shlo_r_32: np.uint8                                 = np.uint8(178) #TODO:NEW->TEST
    shar_r_32: np.uint8                                 = np.uint8(179) #TODO:NEW->TEST
    add_64: np.uint8                                    = np.uint8(180) #TODO:NEW->TEST
    sub_64: np.uint8                                    = np.uint8(181) #TODO:NEW->TEST
    mul_64: np.uint8                                    = np.uint8(182) #TODO:NEW->TEST
    div_u_64: np.uint8                                  = np.uint8(183) #TODO:NEW->TEST
    div_s_64: np.uint8                                  = np.uint8(184) #TODO:NEW->TEST
    rem_u_64: np.uint8                                  = np.uint8(185) #TODO:NEW->TEST
    rem_s_64: np.uint8                                  = np.uint8(186) #TODO:NEW->TEST
    shlo_l_64: np.uint8                                 = np.uint8(187) #TODO:NEW->TEST
    shlo_r_64: np.uint8                                 = np.uint8(188) #TODO:NEW->TEST
    shar_r_64: np.uint8                                 = np.uint8(189) #TODO:NEW->TEST
    _and: np.uint8                                      = np.uint8(190)
    xor: np.uint8                                       = np.uint8(191)
    _or: np.uint8                                       = np.uint8(192)
    mul_upper_s_s: np.uint8                             = np.uint8(193) #TODO:NEW->TEST
    mul_upper_u_u: np.uint8                             = np.uint8(194) #TODO:NEW->TEST
    mul_upper_s_u: np.uint8                             = np.uint8(195) #TODO:NEW->TEST
    set_lt_u: np.uint8                                  = np.uint8(196) #TODO:NEW->TEST
    set_lt_s: np.uint8                                  = np.uint8(197) #TODO:NEW->TEST
    cmov_iz: np.uint8                                   = np.uint8(198) #TODO:NEW->TEST
    cmov_nz: np.uint8                                   = np.uint8(199) #TODO:NEW->TEST


"""
This enum serves as a lookup for the instruction decoding scheme we should apply for a given opcode
"""
it = InstructionType
op = Opcode

OpcodeScheme = {
    # GP_A.5.1
    # Instructions with args: none
    op.trap.value                                           : it.none,
    op.fallthrough.value                                    : it.none,

    # GP_A.5.2
    # Instructions with args: imm
    op.ecalli.value                                         : it.imm,

    # GP_A.5.3
    # Instructions with args: reg_ext_imm
    op.load_imm_64.value                                    : it.reg_ext_imm,

    # GP_A.5.4
    # Instructions with args: imm_imm
    op.store_imm_u8.value                                   : it.imm_imm,
    op.store_imm_u16.value                                  : it.imm_imm,
    op.store_imm_u32.value                                  : it.imm_imm,
    op.store_imm_u64.value                                  : it.imm_imm,

    # GP_A.5.5
    # Instructions with args: offset
    op.jump.value: it.offset,

    # GP_A.5.6
    # Instructions with args: reg, imm
    op.jump_ind.value: it.reg_imm,
    op.load_imm.value: it.reg_imm,
    op.load_u8.value: it.reg_imm,
    op.load_i8.value: it.reg_imm,
    op.load_u16.value: it.reg_imm,
    op.load_i16.value: it.reg_imm,
    op.load_u32.value: it.reg_imm,
    op.load_i32.value: it.reg_imm,
    op.load_u64.value: it.reg_imm,
    op.store_u8.value: it.reg_imm,
    op.store_u16.value: it.reg_imm,
    op.store_u32.value: it.reg_imm,
    op.store_u64.value: it.reg_imm,

    # GP_A.5.7
    # Instructions with args: reg, imm, imm
    op.store_imm_ind_u8.value                               : it.reg_imm_imm,
    op.store_imm_ind_u16.value                              : it.reg_imm_imm,
    op.store_imm_ind_u32.value                              : it.reg_imm_imm,
    op.store_imm_ind_u64.value                              : it.reg_imm_imm,

    # GP_A.5.8
    # Instructions with args: reg, imm, offset
    op.load_imm_jump.value                                  : it.reg_imm_offset,
    op.branch_eq_imm.value                                  : it.reg_imm_offset,
    op.branch_ne_imm.value                                  : it.reg_imm_offset,
    op.branch_lt_u_imm.value                                : it.reg_imm_offset,
    op.branch_ge_u_imm.value                                : it.reg_imm_offset,
    op.branch_le_u_imm.value                                : it.reg_imm_offset,
    op.branch_gt_u_imm.value                                : it.reg_imm_offset,
    op.branch_lt_s_imm.value                                : it.reg_imm_offset,
    op.branch_ge_s_imm.value                                : it.reg_imm_offset,
    op.branch_le_s_imm.value                                : it.reg_imm_offset,
    op.branch_gt_s_imm.value                                : it.reg_imm_offset,

    # GP_A.5.9
    # Instructions with args: reg, reg
    op.move_reg.value: it.reg_reg,  # riscv:
    op.sbrk.value: it.reg_reg,  # X

    # GP_A.5.10
    # Instructions with args: reg, reg, imm
    op.store_ind_u8.value                                   : it.reg_reg_imm,
    op.store_ind_u16.value                                  : it.reg_reg_imm,
    op.store_ind_u32.value                                  : it.reg_reg_imm,
    op.store_ind_u64.value                                  : it.reg_reg_imm,
    op.load_ind_u8.value                                    : it.reg_reg_imm,
    op.load_ind_i8.value                                    : it.reg_reg_imm,
    op.load_ind_u16.value                                   : it.reg_reg_imm,
    op.load_ind_i16.value                                   : it.reg_reg_imm,
    op.load_ind_u32.value                                   : it.reg_reg_imm,
    op.load_ind_i32.value                                   : it.reg_reg_imm,
    op.load_ind_u64.value                                   : it.reg_reg_imm,
    op.add_imm_32.value                                     : it.reg_reg_imm,
    op.and_imm.value                                        : it.reg_reg_imm,
    op.xor_imm.value                                        : it.reg_reg_imm,
    op.or_imm.value                                         : it.reg_reg_imm,
    op.mul_imm_32.value                                     : it.reg_reg_imm,
    op.set_lt_u_imm.value                                   : it.reg_reg_imm,
    op.set_lt_s_imm.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_32.value                                  : it.reg_reg_imm,
    op.shlo_r_imm_32.value                                  : it.reg_reg_imm,
    op.shar_r_imm_32.value                                  : it.reg_reg_imm,
    op.neg_add_imm_32.value                                 : it.reg_reg_imm,
    op.set_gt_u_imm.value                                   : it.reg_reg_imm,
    op.set_gt_s_imm.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_alt_32.value                              : it.reg_reg_imm,
    op.shlo_r_imm_alt_32.value                              : it.reg_reg_imm,
    op.shar_r_imm_alt_32.value                              : it.reg_reg_imm,
    op.cmov_iz_imm.value                                    : it.reg_reg_imm,
    op.cmov_nz_imm.value                                    : it.reg_reg_imm,
    op.add_imm_64                                           : it.reg_reg_imm,
    op.mul_imm_64                                           : it.reg_reg_imm,
    op.shlo_l_imm_64                                        : it.reg_reg_imm,
    op.shlo_r_imm_64                                        : it.reg_reg_imm,
    op.shar_r_imm_64                                        : it.reg_reg_imm,
    op.neg_add_imm_64                                       : it.reg_reg_imm,
    op.shlo_l_imm_alt_64                                    : it.reg_reg_imm,
    op.shlo_r_imm_alt_64                                    : it.reg_reg_imm,
    op.shar_r_imm_alt_64                                    : it.reg_reg_imm,

    # GP_A.5.11
    # Instructions with args: reg, reg, offset
    op.branch_eq.value                                      : it.reg_reg_offset,
    op.branch_ne.value                                      : it.reg_reg_offset,
    op.branch_lt_u.value                                    : it.reg_reg_offset,
    op.branch_lt_s.value                                    : it.reg_reg_offset,
    op.branch_ge_u.value                                    : it.reg_reg_offset,
    op.branch_ge_s.value                                    : it.reg_reg_offset,

    # GP_A.5.12
    # Instructions with args: reg, reg, imm, im:
    op.load_imm_jump_ind.value: it.reg_reg_imm_imm,  # X

    # GP_A.5.13
    # Instructions with args: reg, reg, reg
    op.add_32.value                                         : it.reg_reg_reg,
    op.sub_32.value                                         : it.reg_reg_reg,
    op.mul_32.value                                         : it.reg_reg_reg,
    op.div_u_32.value                                       : it.reg_reg_reg,
    op.div_s_32.value                                       : it.reg_reg_reg,
    op.rem_u_32.value                                       : it.reg_reg_reg,
    op.rem_s_32.value                                       : it.reg_reg_reg,
    op.shlo_l_32.value                                      : it.reg_reg_reg,
    op.shlo_r_32.value                                      : it.reg_reg_reg,
    op.shar_r_32.value                                      : it.reg_reg_reg,
    op.add_64                                               : it.reg_reg_reg,
    op.sub_64                                               : it.reg_reg_reg,
    op.mul_64                                               : it.reg_reg_reg,
    op.div_u_64                                             : it.reg_reg_reg,
    op.div_s_64                                             : it.reg_reg_reg,
    op.rem_u_64                                             : it.reg_reg_reg,
    op.rem_s_64                                             : it.reg_reg_reg,
    op.shlo_l_64                                            : it.reg_reg_reg,
    op.shlo_r_64                                            : it.reg_reg_reg,
    op.shar_r_64                                            : it.reg_reg_reg,
    op._and.value                                           : it.reg_reg_reg,
    op.xor.value                                            : it.reg_reg_reg,
    op._or.value                                            : it.reg_reg_reg,
    op.mul_upper_s_s.value                                  : it.reg_reg_reg,
    op.mul_upper_u_u.value                                  : it.reg_reg_reg,
    op.mul_upper_s_u.value                                  : it.reg_reg_reg,
    op.set_lt_u.value                                       : it.reg_reg_reg,
    op.set_lt_s.value                                       : it.reg_reg_reg,
    op.cmov_iz.value                                        : it.reg_reg_reg, #riscv:https://stackoverflow.com/questions/72340698/riscv-branchless-coding
    op.cmov_nz.value                                        : it.reg_reg_reg,
}


MemOps = {
    Opcode.load_u8.value,
    Opcode.load_i8.value,
    Opcode.load_u16.value,
    Opcode.load_i16.value,
    Opcode.load_u32.value,
    Opcode.load_i32.value,
    Opcode.load_u64.value,
    Opcode.load_ind_u8.value,
    Opcode.load_ind_i8.value,
    Opcode.load_ind_u16.value,
    Opcode.load_ind_i16.value,
    Opcode.load_ind_u32.value,
    Opcode.load_ind_i32.value,
    Opcode.load_ind_u64.value,
    Opcode.store_imm_u8.value,
    Opcode.store_imm_u16.value,
    Opcode.store_imm_u32.value,
    Opcode.store_imm_u64.value,
    Opcode.store_u8.value,
    Opcode.store_u16.value,
    Opcode.store_u32.value,
    Opcode.store_u64.value,
    Opcode.store_ind_u8.value,
    Opcode.store_ind_u16.value,
    Opcode.store_ind_u32.value,
    Opcode.store_ind_u64.value,
    Opcode.store_imm_ind_u8.value,
    Opcode.store_imm_ind_u16.value,
    Opcode.store_imm_ind_u32.value,
    Opcode.store_imm_ind_u64.value,
}
