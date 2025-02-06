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
    load_imm_64: np.uint8                              = np.uint8(20)

    # GP_A.5.4
    # Instructions with Arguments of two Immediates (imm_imm)
    store_imm_u8: np.uint8                              = np.uint8(30)
    store_imm_u16: np.uint8                             = np.uint8(31)
    store_imm_u32: np.uint8                             = np.uint8(32)
    store_imm_u64: np.uint8                             = np.uint8(33)

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
    count_set_bits_64: np.uint8                         = np.uint8(102) #TODO:NEW->TEST
    count_set_bits_32: np.uint8                         = np.uint8(103) #TODO:NEW->TEST
    leading_zero_bits_64: np.uint8                      = np.uint8(104) #TODO:NEW->TEST
    leading_zero_bits_32: np.uint8                      = np.uint8(105) #TODO:NEW->TEST
    trailing_zero_bits_64: np.uint8                     = np.uint8(106) #TODO:NEW->TEST
    trailing_zero_bits_32: np.uint8                     = np.uint8(107) #TODO:NEW->TEST
    sign_extend_8: np.uint8                             = np.uint8(108) #TODO:NEW->TEST
    sign_extend_16: np.uint8                            = np.uint8(109) #TODO:NEW->TEST
    zero_extend_16: np.uint8                            = np.uint8(110) #TODO:NEW->TEST
    reverse_bytes: np.uint8                             = np.uint8(111) #TODO:NEW->TEST

    # GP_A.5.10
    # Instructions with Arguments Of Two Registers & One Immediate (reg_reg_imm)
    store_ind_u8: np.uint8                              = np.uint8(120)
    store_ind_u16: np.uint8                             = np.uint8(121)
    store_ind_u32: np.uint8                             = np.uint8(122)
    store_ind_u64: np.uint8                             = np.uint8(123) #TODO:NEW->TEST
    load_ind_u8: np.uint8                               = np.uint8(124)
    load_ind_i8: np.uint8                               = np.uint8(125)
    load_ind_u16: np.uint8                              = np.uint8(126)
    load_ind_i16: np.uint8                              = np.uint8(127)
    load_ind_u32: np.uint8                              = np.uint8(128)
    load_ind_i32: np.uint8                              = np.uint8(129) #TODO:NEW->TEST
    load_ind_u64: np.uint8                              = np.uint8(130) #TODO:NEW->TEST
    add_imm_32: np.uint8                                = np.uint8(131) #TODO:NEW->TEST
    and_imm: np.uint8                                   = np.uint8(132)
    xor_imm: np.uint8                                   = np.uint8(133)
    or_imm: np.uint8                                    = np.uint8(134)
    mul_imm_32: np.uint8                                = np.uint8(135) #TODO:NEW->TEST
    set_lt_u_imm: np.uint8                              = np.uint8(136)
    set_lt_s_imm: np.uint8                              = np.uint8(137)
    shlo_l_imm_32: np.uint8                             = np.uint8(138) #TODO:NEW->TEST
    shlo_r_imm_32: np.uint8                             = np.uint8(139) #TODO:NEW->TEST
    shar_r_imm_32: np.uint8                             = np.uint8(140) #TODO:NEW->TEST
    neg_add_imm_32: np.uint8                            = np.uint8(141) #TODO:NEW->TEST
    set_gt_u_imm: np.uint8                              = np.uint8(142)
    set_gt_s_imm: np.uint8                              = np.uint8(143)
    shlo_l_imm_alt_32: np.uint8                         = np.uint8(144) #TODO:NEW->TEST
    shlo_r_imm_alt_32: np.uint8                         = np.uint8(145) #TODO:NEW->TEST
    shar_r_imm_alt_32: np.uint8                         = np.uint8(146) #TODO:NEW->TEST
    cmov_iz_imm: np.uint8                               = np.uint8(147)
    cmov_nz_imm: np.uint8                               = np.uint8(148)
    add_imm_64: np.uint8                                = np.uint8(149) #TODO:NEW->TEST
    mul_imm_64: np.uint8                                = np.uint8(150) #TODO:NEW->TEST
    shlo_l_imm_64: np.uint8                             = np.uint8(151) #TODO:NEW->TEST
    shlo_r_imm_64: np.uint8                             = np.uint8(152) #TODO:NEW->TEST
    shar_r_imm_64: np.uint8                             = np.uint8(153) #TODO:NEW->TEST
    neg_add_imm_64: np.uint8                            = np.uint8(154) #TODO:NEW->TEST
    shlo_l_imm_alt_64: np.uint8                         = np.uint8(155) #TODO:NEW->TEST
    shlo_r_imm_alt_64: np.uint8                         = np.uint8(156) #TODO:NEW->TEST
    shar_r_imm_alt_64: np.uint8                         = np.uint8(157) #TODO:NEW->TEST
    rot_r_64_imm: np.uint8                              = np.uint8(158) #TODO:NEW->TEST!!!!!!!!!!!!!
    rot_r_64_imm_alt: np.uint8                          = np.uint8(159) #TODO:NEW->TEST
    rot_r_32_imm: np.uint8                              = np.uint8(160) #TODO:NEW->TEST
    rot_r_32_imm_alt: np.uint8                          = np.uint8(161) #TODO:NEW->TEST


    # GP_A.5.11
    # Instructions with Arguments of Two Registers & One Offset (reg_reg_offset)
    branch_eq: np.uint8                                 = np.uint8(170)
    branch_ne: np.uint8                                 = np.uint8(171)
    branch_lt_u: np.uint8                               = np.uint8(172)
    branch_lt_s: np.uint8                               = np.uint8(173)
    branch_ge_u: np.uint8                               = np.uint8(174)
    branch_ge_s: np.uint8                               = np.uint8(175)

    # GP_A.5.12
    # Instructions with Arguments Of Two Registers And Two Immediates (reg_reg_imm_imm)
    load_imm_jump_ind: np.uint8                         = np.uint8(180)

    # GP_A.5.13
    # Instructions with Arguments Of Three Registers (reg_reg_reg)
    add_32: np.uint8                                    = np.uint8(190)
    sub_32: np.uint8                                    = np.uint8(191)
    mul_32: np.uint8                                    = np.uint8(192)
    div_u_32: np.uint8                                  = np.uint8(193)
    div_s_32: np.uint8                                  = np.uint8(194)
    rem_u_32: np.uint8                                  = np.uint8(195)
    rem_s_32: np.uint8                                  = np.uint8(196)
    shlo_l_32: np.uint8                                 = np.uint8(197)
    shlo_r_32: np.uint8                                 = np.uint8(198)
    shar_r_32: np.uint8                                 = np.uint8(199)
    add_64: np.uint8                                    = np.uint8(200)
    sub_64: np.uint8                                    = np.uint8(201)
    mul_64: np.uint8                                    = np.uint8(202)
    div_u_64: np.uint8                                  = np.uint8(203)
    div_s_64: np.uint8                                  = np.uint8(204)
    rem_u_64: np.uint8                                  = np.uint8(205)
    rem_s_64: np.uint8                                  = np.uint8(206)
    shlo_l_64: np.uint8                                 = np.uint8(207)
    shlo_r_64: np.uint8                                 = np.uint8(208)
    shar_r_64: np.uint8                                 = np.uint8(209)
    _and: np.uint8                                      = np.uint8(210)
    xor: np.uint8                                       = np.uint8(211)
    _or: np.uint8                                       = np.uint8(212)
    mul_upper_s_s: np.uint8                             = np.uint8(213)
    mul_upper_u_u: np.uint8                             = np.uint8(214)
    mul_upper_s_u: np.uint8                             = np.uint8(215)
    set_lt_u: np.uint8                                  = np.uint8(216)
    set_lt_s: np.uint8                                  = np.uint8(217)
    cmov_iz: np.uint8                                   = np.uint8(218)
    cmov_nz: np.uint8                                   = np.uint8(219)
    rot_l_64: np.uint8                                  = np.uint8(220)
    rot_l_32: np.uint8                                  = np.uint8(221)
    rot_r_64: np.uint8                                  = np.uint8(222)
    rot_r_32: np.uint8                                  = np.uint8(223)
    and_inv: np.uint8                                   = np.uint8(224)
    or_inv: np.uint8                                    = np.uint8(225)
    xnor: np.uint8                                      = np.uint8(226)
    _max: np.uint8                                      = np.uint8(227)
    max_u: np.uint8                                     = np.uint8(228)
    _min: np.uint8                                      = np.uint8(229)
    min_u: np.uint8                                     = np.uint8(230)


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
    op.move_reg.value: it.reg_reg,
    op.sbrk.value: it.reg_reg,
    op.count_set_bits_64: it.reg_reg,
    op.count_set_bits_32: it.reg_reg,
    op.leading_zero_bits_64: it.reg_reg,
    op.leading_zero_bits_32: it.reg_reg,
    op.trailing_zero_bits_64: it.reg_reg,
    op.trailing_zero_bits_32: it.reg_reg,
    op.sign_extend_8: it.reg_reg,
    op.sign_extend_16: it.reg_reg,
    op.zero_extend_16: it.reg_reg,
    op.reverse_bytes: it.reg_reg,

    # GP_A.5.10
    # Instructions with args: reg, reg, imm
    op.store_ind_u8.value                                   : it.reg_reg_imm,
    op.store_ind_u8.value                                   : it.reg_reg_imm,
    op.store_ind_u16.value                                   : it.reg_reg_imm,
    op.store_ind_u32.value                                   : it.reg_reg_imm,
    op.store_ind_u64.value                                   : it.reg_reg_imm,
    op.load_ind_u8.value                                   : it.reg_reg_imm,
    op.load_ind_i8.value                                   : it.reg_reg_imm,
    op.load_ind_u16.value                                   : it.reg_reg_imm,
    op.load_ind_i16.value                                   : it.reg_reg_imm,
    op.load_ind_u32.value                                   : it.reg_reg_imm,
    op.load_ind_i32.value                                   : it.reg_reg_imm,
    op.load_ind_u64.value                                   : it.reg_reg_imm,
    op.add_imm_32.value                                   : it.reg_reg_imm,
    op.and_imm.value                                   : it.reg_reg_imm,
    op.xor_imm.value                                   : it.reg_reg_imm,
    op.or_imm.value                                   : it.reg_reg_imm,
    op.mul_imm_32.value                                   : it.reg_reg_imm,
    op.set_lt_u_imm.value                                   : it.reg_reg_imm,
    op.set_lt_s_imm.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_32.value                                   : it.reg_reg_imm,
    op.shlo_r_imm_32.value                                   : it.reg_reg_imm,
    op.shar_r_imm_32.value                                   : it.reg_reg_imm,
    op.neg_add_imm_32.value                                   : it.reg_reg_imm,
    op.set_gt_u_imm.value                                   : it.reg_reg_imm,
    op.set_gt_s_imm.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_alt_32.value                                   : it.reg_reg_imm,
    op.shlo_r_imm_alt_32.value                                   : it.reg_reg_imm,
    op.shar_r_imm_alt_32.value                                   : it.reg_reg_imm,
    op.cmov_iz_imm.value                                   : it.reg_reg_imm,
    op.cmov_nz_imm.value                                   : it.reg_reg_imm,
    op.add_imm_64.value                                   : it.reg_reg_imm,
    op.mul_imm_64.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_64.value                                   : it.reg_reg_imm,
    op.shlo_r_imm_64.value                                   : it.reg_reg_imm,
    op.shar_r_imm_64.value                                   : it.reg_reg_imm,
    op.neg_add_imm_64.value                                   : it.reg_reg_imm,
    op.shlo_l_imm_alt_64.value                                   : it.reg_reg_imm,
    op.shlo_r_imm_alt_64.value                                   : it.reg_reg_imm,
    op.shar_r_imm_alt_64.value                                   : it.reg_reg_imm,
    op.rot_r_64_imm.value                                   : it.reg_reg_imm,
    op.rot_r_64_imm_alt.value                                   : it.reg_reg_imm,
    op.rot_r_32_imm.value                                   : it.reg_reg_imm,
    op.rot_r_32_imm_alt.value                                   : it.reg_reg_imm,


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
    op.add_32.value: it.reg_reg_reg,
    op.sub_32.value: it.reg_reg_reg,
    op.mul_32.value: it.reg_reg_reg,
    op.div_u_32.value: it.reg_reg_reg,
    op.div_s_32.value: it.reg_reg_reg,
    op.rem_u_32.value: it.reg_reg_reg,
    op.rem_s_32.value: it.reg_reg_reg,
    op.shlo_l_32.value: it.reg_reg_reg,
    op.shlo_r_32.value: it.reg_reg_reg,
    op.shar_r_32.value: it.reg_reg_reg,
    op.add_64.value: it.reg_reg_reg,
    op.sub_64.value: it.reg_reg_reg,
    op.mul_64.value: it.reg_reg_reg,
    op.div_u_64.value: it.reg_reg_reg,
    op.div_s_64.value: it.reg_reg_reg,
    op.rem_u_64.value: it.reg_reg_reg,
    op.rem_s_64.value: it.reg_reg_reg,
    op.shlo_l_64.value: it.reg_reg_reg,
    op.shlo_r_64.value: it.reg_reg_reg,
    op.shar_r_64.value: it.reg_reg_reg,
    op._and.value: it.reg_reg_reg,
    op.xor.value: it.reg_reg_reg,
    op._or.value: it.reg_reg_reg,
    op.mul_upper_s_s.value: it.reg_reg_reg,
    op.mul_upper_u_u.value: it.reg_reg_reg,
    op.mul_upper_s_u.value: it.reg_reg_reg,
    op.set_lt_u.value: it.reg_reg_reg,
    op.set_lt_s.value: it.reg_reg_reg,
    op.cmov_iz.value: it.reg_reg_reg,
    op.cmov_nz.value: it.reg_reg_reg,
    op.rot_l_64.value: it.reg_reg_reg,
    op.rot_l_32.value: it.reg_reg_reg,
    op.rot_r_64.value: it.reg_reg_reg,
    op.rot_r_32.value: it.reg_reg_reg,
    op.and_inv.value: it.reg_reg_reg,
    op.or_inv.value: it.reg_reg_reg,
    op.xnor.value: it.reg_reg_reg,
    op._max.value: it.reg_reg_reg,
    op.max_u.value: it.reg_reg_reg,
    op._min.value: it.reg_reg_reg,
    op.min_u.value: it.reg_reg_reg
}


MemOps = {
    Opcode.load_u8.value: {"read": True, "write": False, "bytes": 1},
    Opcode.load_i8.value: {"read": True, "write": False, "bytes": 1},
    Opcode.load_u16.value: {"read": True, "write": False, "bytes": 2},
    Opcode.load_i16.value: {"read": True, "write": False, "bytes": 2},
    Opcode.load_u32.value: {"read": True, "write": False, "bytes": 4},
    Opcode.load_i32.value: {"read": True, "write": False, "bytes": 4},
    Opcode.load_u64.value: {"read": True, "write": False, "bytes": 8},
    Opcode.load_imm_64.value: {"read": True, "write": False, "bytes": 8},
    Opcode.load_ind_u8.value: {"read": True, "write": False, "bytes": 1},
    Opcode.load_ind_i8.value: {"read": True, "write": False, "bytes": 1},
    Opcode.load_ind_u16.value: {"read": True, "write": False, "bytes": 2},
    Opcode.load_ind_i16.value: {"read": True, "write": False, "bytes": 2},
    Opcode.load_ind_u32.value: {"read": True, "write": False, "bytes": 4},
    Opcode.load_ind_i32.value: {"read": True, "write": False, "bytes": 4},
    Opcode.load_ind_u64.value: {"read": True, "write": False, "bytes": 8},
    Opcode.store_imm_u8.value: {"read": True, "write": True, "bytes": 1},
    Opcode.store_imm_u16.value: {"read": True, "write": True, "bytes": 2},
    Opcode.store_imm_u32.value: {"read": True, "write": True, "bytes": 4},
    Opcode.store_imm_u64.value: {"read": True, "write": True, "bytes": 8},
    Opcode.store_u8.value: {"read": True, "write": True, "bytes": 1},
    Opcode.store_u16.value: {"read": True, "write": True, "bytes": 2},
    Opcode.store_u32.value: {"read": True, "write": True, "bytes": 4},
    Opcode.store_u64.value: {"read": True, "write": True, "bytes": 8},
    Opcode.store_ind_u8.value: {"read": True, "write": True, "bytes": 1},
    Opcode.store_ind_u16.value: {"read": True, "write": True, "bytes": 2},
    Opcode.store_ind_u32.value: {"read": True, "write": True, "bytes": 4},
    Opcode.store_ind_u64.value: {"read": True, "write": True, "bytes": 8},
    Opcode.store_imm_ind_u8.value: {"read": True, "write": True, "bytes": 1},
    Opcode.store_imm_ind_u16.value: {"read": True, "write": True, "bytes": 2},
    Opcode.store_imm_ind_u32.value: {"read": True, "write": True, "bytes": 4},
    Opcode.store_imm_ind_u64.value: {"read": True, "write": True, "bytes": 8},
}
