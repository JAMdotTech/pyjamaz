from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Optional, Union

import numpy as np

from pyjamaz.pvm.exceptions import PVMMemoryError

# TODO configurable during bootstrap
PVM_MIN_HEAP_SIZE = 0 #1_000_000*2    #TODO: necesary? seems like a good idea to prevent lots of small mallocs, but then again, maybe not :S
PVM_MAX_HEAP_SIZE = 1_000_000*10    #TODO: find out what it should be...
PVM_PAGE_SIZE = 2**12 #ZP
PVM_INIT_ZONE_SIZE = 2**16 #ZZ
PVM_INPUT_DATA_SIZE = 2**24 #ZI

class ExitReason(Enum):
    resume:int          = 0 #GP:     ▸: continue PVM
    halt:int            = 1 #GP-A.2: ∎: regular halt: halt
    panic:int           = 2 #GP-A.2: ☇: unexpected program termination: panic
    out_of_gas:int      = 3 #GP-A.2: ∞: out-of-gas
    page_fault:int      = 4 #GP-A.2: F: page-fault
    host_halt:int       = 5 #GP-A.2: h: host-call

# Cache frequently used enum values for performance
EXIT_RESUME = ExitReason.resume.value
EXIT_HALT = ExitReason.halt.value
EXIT_PANIC = ExitReason.panic.value
EXIT_PAGE_FAULT = ExitReason.page_fault.value
EXIT_HOST_HALT = ExitReason.host_halt.value


@dataclass
class ExitCondition:
    reason: ExitReason
    value: Optional[Union[int, bytes]] = None


class InstructionType(IntEnum):
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


class Opcode(IntEnum):
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
    load_i32: np.uint8                                  = np.uint8(57)
    load_u64: np.uint8                                  = np.uint8(58)
    store_u8: np.uint8                                  = np.uint8(59)
    store_u16: np.uint8                                 = np.uint8(60)
    store_u32: np.uint8                                 = np.uint8(61)
    store_u64: np.uint8                                 = np.uint8(62)

    # GP_A.5.7
    # Instructions with Arguments Of One Register & Two Immediates (reg_imm_imm)
    store_imm_ind_u8: np.uint8                          = np.uint8(70)
    store_imm_ind_u16: np.uint8                         = np.uint8(71)
    store_imm_ind_u32: np.uint8                         = np.uint8(72)
    store_imm_ind_u64: np.uint8                         = np.uint8(73)

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
    count_set_bits_64: np.uint8                         = np.uint8(102)
    count_set_bits_32: np.uint8                         = np.uint8(103)
    leading_zero_bits_64: np.uint8                      = np.uint8(104)
    leading_zero_bits_32: np.uint8                      = np.uint8(105)
    trailing_zero_bits_64: np.uint8                     = np.uint8(106)
    trailing_zero_bits_32: np.uint8                     = np.uint8(107)
    sign_extend_8: np.uint8                             = np.uint8(108)
    sign_extend_16: np.uint8                            = np.uint8(109)
    zero_extend_16: np.uint8                            = np.uint8(110)
    reverse_bytes: np.uint8                             = np.uint8(111)

    # GP_A.5.10
    # Instructions with Arguments Of Two Registers & One Immediate (reg_reg_imm)
    store_ind_u8: np.uint8                              = np.uint8(120)
    store_ind_u16: np.uint8                             = np.uint8(121)
    store_ind_u32: np.uint8                             = np.uint8(122)
    store_ind_u64: np.uint8                             = np.uint8(123)
    load_ind_u8: np.uint8                               = np.uint8(124)
    load_ind_i8: np.uint8                               = np.uint8(125)
    load_ind_u16: np.uint8                              = np.uint8(126)
    load_ind_i16: np.uint8                              = np.uint8(127)
    load_ind_u32: np.uint8                              = np.uint8(128)
    load_ind_i32: np.uint8                              = np.uint8(129)
    load_ind_u64: np.uint8                              = np.uint8(130)
    add_imm_32: np.uint8                                = np.uint8(131)
    and_imm: np.uint8                                   = np.uint8(132)
    xor_imm: np.uint8                                   = np.uint8(133)
    or_imm: np.uint8                                    = np.uint8(134)
    mul_imm_32: np.uint8                                = np.uint8(135)
    set_lt_u_imm: np.uint8                              = np.uint8(136)
    set_lt_s_imm: np.uint8                              = np.uint8(137)
    shlo_l_imm_32: np.uint8                             = np.uint8(138)
    shlo_r_imm_32: np.uint8                             = np.uint8(139)
    shar_r_imm_32: np.uint8                             = np.uint8(140)
    neg_add_imm_32: np.uint8                            = np.uint8(141)
    set_gt_u_imm: np.uint8                              = np.uint8(142)
    set_gt_s_imm: np.uint8                              = np.uint8(143)
    shlo_l_imm_alt_32: np.uint8                         = np.uint8(144)
    shlo_r_imm_alt_32: np.uint8                         = np.uint8(145)
    shar_r_imm_alt_32: np.uint8                         = np.uint8(146)
    cmov_iz_imm: np.uint8                               = np.uint8(147)
    cmov_nz_imm: np.uint8                               = np.uint8(148)
    add_imm_64: np.uint8                                = np.uint8(149)
    mul_imm_64: np.uint8                                = np.uint8(150)
    shlo_l_imm_64: np.uint8                             = np.uint8(151)
    shlo_r_imm_64: np.uint8                             = np.uint8(152)
    shar_r_imm_64: np.uint8                             = np.uint8(153)
    neg_add_imm_64: np.uint8                            = np.uint8(154)
    shlo_l_imm_alt_64: np.uint8                         = np.uint8(155)
    shlo_r_imm_alt_64: np.uint8                         = np.uint8(156)
    shar_r_imm_alt_64: np.uint8                         = np.uint8(157)
    rot_r_64_imm: np.uint8                              = np.uint8(158)
    rot_r_64_imm_alt: np.uint8                          = np.uint8(159)
    rot_r_32_imm: np.uint8                              = np.uint8(160)
    rot_r_32_imm_alt: np.uint8                          = np.uint8(161)


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
    op.trap                                           : it.none,
    op.fallthrough                                    : it.none,

    # GP_A.5.2
    # Instructions with args: imm
    op.ecalli                                         : it.imm,

    # GP_A.5.3
    # Instructions with args: reg_ext_imm
    op.load_imm_64                                    : it.reg_ext_imm,

    # GP_A.5.4
    # Instructions with args: imm_imm
    op.store_imm_u8                                   : it.imm_imm,
    op.store_imm_u16                                  : it.imm_imm,
    op.store_imm_u32                                  : it.imm_imm,
    op.store_imm_u64                                  : it.imm_imm,

    # GP_A.5.5
    # Instructions with args: offset
    op.jump: it.offset,

    # GP_A.5.6
    # Instructions with args: reg, imm
    op.jump_ind: it.reg_imm,
    op.load_imm: it.reg_imm,
    op.load_u8: it.reg_imm,
    op.load_i8: it.reg_imm,
    op.load_u16: it.reg_imm,
    op.load_i16: it.reg_imm,
    op.load_u32: it.reg_imm,
    op.load_i32: it.reg_imm,
    op.load_u64: it.reg_imm,
    op.store_u8: it.reg_imm,
    op.store_u16: it.reg_imm,
    op.store_u32: it.reg_imm,
    op.store_u64: it.reg_imm,

    # GP_A.5.7
    # Instructions with args: reg, imm, imm
    op.store_imm_ind_u8                               : it.reg_imm_imm,
    op.store_imm_ind_u16                              : it.reg_imm_imm,
    op.store_imm_ind_u32                              : it.reg_imm_imm,
    op.store_imm_ind_u64                              : it.reg_imm_imm,

    # GP_A.5.8
    # Instructions with args: reg, imm, offset
    op.load_imm_jump                                  : it.reg_imm_offset,
    op.branch_eq_imm                                  : it.reg_imm_offset,
    op.branch_ne_imm                                  : it.reg_imm_offset,
    op.branch_lt_u_imm                                : it.reg_imm_offset,
    op.branch_ge_u_imm                                : it.reg_imm_offset,
    op.branch_le_u_imm                                : it.reg_imm_offset,
    op.branch_gt_u_imm                                : it.reg_imm_offset,
    op.branch_lt_s_imm                                : it.reg_imm_offset,
    op.branch_ge_s_imm                                : it.reg_imm_offset,
    op.branch_le_s_imm                                : it.reg_imm_offset,
    op.branch_gt_s_imm                                : it.reg_imm_offset,

    # GP_A.5.9
    # Instructions with args: reg, reg
    op.move_reg: it.reg_reg,
    op.sbrk: it.reg_reg,
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
    op.store_ind_u8                               : it.reg_reg_imm,
    op.store_ind_u8                               : it.reg_reg_imm,
    op.store_ind_u16                              : it.reg_reg_imm,
    op.store_ind_u32                              : it.reg_reg_imm,
    op.store_ind_u64                              : it.reg_reg_imm,
    op.load_ind_u8                                : it.reg_reg_imm,
    op.load_ind_i8                                : it.reg_reg_imm,
    op.load_ind_u16                               : it.reg_reg_imm,
    op.load_ind_i16                               : it.reg_reg_imm,
    op.load_ind_u32                               : it.reg_reg_imm,
    op.load_ind_i32                               : it.reg_reg_imm,
    op.load_ind_u64                               : it.reg_reg_imm,
    op.add_imm_32                                 : it.reg_reg_imm,
    op.and_imm                                    : it.reg_reg_imm,
    op.xor_imm                                    : it.reg_reg_imm,
    op.or_imm                                     : it.reg_reg_imm,
    op.mul_imm_32                                 : it.reg_reg_imm,
    op.set_lt_u_imm                               : it.reg_reg_imm,
    op.set_lt_s_imm                               : it.reg_reg_imm,
    op.shlo_l_imm_32                              : it.reg_reg_imm,
    op.shlo_r_imm_32                              : it.reg_reg_imm,
    op.shar_r_imm_32                              : it.reg_reg_imm,
    op.neg_add_imm_32                             : it.reg_reg_imm,
    op.set_gt_u_imm                               : it.reg_reg_imm,
    op.set_gt_s_imm                               : it.reg_reg_imm,
    op.shlo_l_imm_alt_32                          : it.reg_reg_imm,
    op.shlo_r_imm_alt_32                          : it.reg_reg_imm,
    op.shar_r_imm_alt_32                          : it.reg_reg_imm,
    op.cmov_iz_imm                                : it.reg_reg_imm,
    op.cmov_nz_imm                                : it.reg_reg_imm,
    op.add_imm_64                                 : it.reg_reg_imm,
    op.mul_imm_64                                 : it.reg_reg_imm,
    op.shlo_l_imm_64                              : it.reg_reg_imm,
    op.shlo_r_imm_64                              : it.reg_reg_imm,
    op.shar_r_imm_64                              : it.reg_reg_imm,
    op.neg_add_imm_64                             : it.reg_reg_imm,
    op.shlo_l_imm_alt_64                          : it.reg_reg_imm,
    op.shlo_r_imm_alt_64                          : it.reg_reg_imm,
    op.shar_r_imm_alt_64                          : it.reg_reg_imm,
    op.rot_r_64_imm                               : it.reg_reg_imm,
    op.rot_r_64_imm_alt                           : it.reg_reg_imm,
    op.rot_r_32_imm                               : it.reg_reg_imm,
    op.rot_r_32_imm_alt                           : it.reg_reg_imm,


    # GP_A.5.11
    # Instructions with args: reg, reg, offset
    op.branch_eq                                      : it.reg_reg_offset,
    op.branch_ne                                      : it.reg_reg_offset,
    op.branch_lt_u                                    : it.reg_reg_offset,
    op.branch_lt_s                                    : it.reg_reg_offset,
    op.branch_ge_u                                    : it.reg_reg_offset,
    op.branch_ge_s                                    : it.reg_reg_offset,

    # GP_A.5.12
    # Instructions with args: reg, reg, imm, im:
    op.load_imm_jump_ind: it.reg_reg_imm_imm,  # X

    # GP_A.5.13
    # Instructions with args: reg, reg, reg
    op.add_32: it.reg_reg_reg,
    op.sub_32: it.reg_reg_reg,
    op.mul_32: it.reg_reg_reg,
    op.div_u_32: it.reg_reg_reg,
    op.div_s_32: it.reg_reg_reg,
    op.rem_u_32: it.reg_reg_reg,
    op.rem_s_32: it.reg_reg_reg,
    op.shlo_l_32: it.reg_reg_reg,
    op.shlo_r_32: it.reg_reg_reg,
    op.shar_r_32: it.reg_reg_reg,
    op.add_64: it.reg_reg_reg,
    op.sub_64: it.reg_reg_reg,
    op.mul_64: it.reg_reg_reg,
    op.div_u_64: it.reg_reg_reg,
    op.div_s_64: it.reg_reg_reg,
    op.rem_u_64: it.reg_reg_reg,
    op.rem_s_64: it.reg_reg_reg,
    op.shlo_l_64: it.reg_reg_reg,
    op.shlo_r_64: it.reg_reg_reg,
    op.shar_r_64: it.reg_reg_reg,
    op._and: it.reg_reg_reg,
    op.xor: it.reg_reg_reg,
    op._or: it.reg_reg_reg,
    op.mul_upper_s_s: it.reg_reg_reg,
    op.mul_upper_u_u: it.reg_reg_reg,
    op.mul_upper_s_u: it.reg_reg_reg,
    op.set_lt_u: it.reg_reg_reg,
    op.set_lt_s: it.reg_reg_reg,
    op.cmov_iz: it.reg_reg_reg,
    op.cmov_nz: it.reg_reg_reg,
    op.rot_l_64: it.reg_reg_reg,
    op.rot_l_32: it.reg_reg_reg,
    op.rot_r_64: it.reg_reg_reg,
    op.rot_r_32: it.reg_reg_reg,
    op.and_inv: it.reg_reg_reg,
    op.or_inv: it.reg_reg_reg,
    op.xnor: it.reg_reg_reg,
    op._max: it.reg_reg_reg,
    op.max_u: it.reg_reg_reg,
    op._min: it.reg_reg_reg,
    op.min_u: it.reg_reg_reg
}


MemOps = {
    Opcode.load_u8: {"read": True, "write": False, "bytes": 1},
    Opcode.load_i8: {"read": True, "write": False, "bytes": 1},
    Opcode.load_u16: {"read": True, "write": False, "bytes": 2},
    Opcode.load_i16: {"read": True, "write": False, "bytes": 2},
    Opcode.load_u32: {"read": True, "write": False, "bytes": 4},
    Opcode.load_i32: {"read": True, "write": False, "bytes": 4},
    Opcode.load_u64: {"read": True, "write": False, "bytes": 8},
    Opcode.load_imm_64: {"read": True, "write": False, "bytes": 8},
    Opcode.load_ind_u8: {"read": True, "write": False, "bytes": 1},
    Opcode.load_ind_i8: {"read": True, "write": False, "bytes": 1},
    Opcode.load_ind_u16: {"read": True, "write": False, "bytes": 2},
    Opcode.load_ind_i16: {"read": True, "write": False, "bytes": 2},
    Opcode.load_ind_u32: {"read": True, "write": False, "bytes": 4},
    Opcode.load_ind_i32: {"read": True, "write": False, "bytes": 4},
    Opcode.load_ind_u64: {"read": True, "write": False, "bytes": 8},
    Opcode.store_imm_u8: {"read": True, "write": True, "bytes": 1},
    Opcode.store_imm_u16: {"read": True, "write": True, "bytes": 2},
    Opcode.store_imm_u32: {"read": True, "write": True, "bytes": 4},
    Opcode.store_imm_u64: {"read": True, "write": True, "bytes": 8},
    Opcode.store_u8: {"read": True, "write": True, "bytes": 1},
    Opcode.store_u16: {"read": True, "write": True, "bytes": 2},
    Opcode.store_u32: {"read": True, "write": True, "bytes": 4},
    Opcode.store_u64: {"read": True, "write": True, "bytes": 8},
    Opcode.store_ind_u8: {"read": True, "write": True, "bytes": 1},
    Opcode.store_ind_u16: {"read": True, "write": True, "bytes": 2},
    Opcode.store_ind_u32: {"read": True, "write": True, "bytes": 4},
    Opcode.store_ind_u64: {"read": True, "write": True, "bytes": 8},
    Opcode.store_imm_ind_u8: {"read": True, "write": True, "bytes": 1},
    Opcode.store_imm_ind_u16: {"read": True, "write": True, "bytes": 2},
    Opcode.store_imm_ind_u32: {"read": True, "write": True, "bytes": 4},
    Opcode.store_imm_ind_u64: {"read": True, "write": True, "bytes": 8},
}

OpcodeNames = {
    # GP_A.5.1
    # Instructions with args: none
    op.trap: "trap",
    op.fallthrough: "fallthrough",

    # GP_A.5.2
    # Instructions with args: imm
    op.ecalli: "ecalli",

    # GP_A.5.3
    # Instructions with args: reg_ext_imm
    op.load_imm_64: "load_imm_64",

    # GP_A.5.4
    # Instructions with args: imm_imm
    op.store_imm_u8: "store_imm_u8",
    op.store_imm_u16: "store_imm_u16",
    op.store_imm_u32: "store_imm_u32",
    op.store_imm_u64: "store_imm_u64",

    # GP_A.5.5
    # Instructions with args: offset
    op.jump: "jump",

    # GP_A.5.6
    # Instructions with args: reg, imm
    op.jump_ind: "jump_ind",
    op.load_imm: "load_imm",
    op.load_u8: "load_u8",
    op.load_i8: "load_i8",
    op.load_u16: "load_u16",
    op.load_i16: "load_i16",
    op.load_u32: "load_u32",
    op.load_i32: "load_i32",
    op.load_u64: "load_u64",
    op.store_u8: "store_u8",
    op.store_u16: "store_u16",
    op.store_u32: "store_u32",
    op.store_u64: "store_u64",

    # GP_A.5.7
    # Instructions with args: reg, imm, imm
    op.store_imm_ind_u8: "store_imm_ind_u8",
    op.store_imm_ind_u16: "store_imm_ind_u16",
    op.store_imm_ind_u32: "store_imm_ind_u32",
    op.store_imm_ind_u64: "store_imm_ind_u64",

    # GP_A.5.8
    # Instructions with args: reg, imm, offset
    op.load_imm_jump: "load_imm_jump",
    op.branch_eq_imm: "branch_eq_imm",
    op.branch_ne_imm: "branch_ne_imm",
    op.branch_lt_u_imm: "branch_lt_u_imm",
    op.branch_ge_u_imm: "branch_ge_u_imm",
    op.branch_le_u_imm: "branch_le_u_imm",
    op.branch_gt_u_imm: "branch_gt_u_imm",
    op.branch_lt_s_imm: "branch_lt_s_imm",
    op.branch_ge_s_imm: "branch_ge_s_imm",
    op.branch_le_s_imm: "branch_le_s_imm",
    op.branch_gt_s_imm: "branch_gt_s_imm",

    # GP_A.5.9
    # Instructions with args: reg, reg
    op.move_reg: "move_reg",
    op.sbrk: "sbrk",
    op.count_set_bits_64: "count_set_bits_64",
    op.count_set_bits_32: "count_set_bits_32",
    op.leading_zero_bits_64: "leading_zero_bits_64",
    op.leading_zero_bits_32: "leading_zero_bits_32",
    op.trailing_zero_bits_64: "trailing_zero_bits_64",
    op.trailing_zero_bits_32: "trailing_zero_bits_32",
    op.sign_extend_8: "sign_extend_8",
    op.sign_extend_16: "sign_extend_16",
    op.zero_extend_16: "zero_extend_16",
    op.reverse_bytes: "reverse_bytes",

    # GP_A.5.10
    # Instructions with args: reg, reg, imm
    op.store_ind_u8: "store_ind_u8",
    op.store_ind_u8: "store_ind_u8",
    op.store_ind_u16: "store_ind_u16",
    op.store_ind_u32: "store_ind_u32",
    op.store_ind_u64: "store_ind_u64",
    op.load_ind_u8: "load_ind_u8",
    op.load_ind_i8: "load_ind_i8",
    op.load_ind_u16: "load_ind_u16",
    op.load_ind_i16: "load_ind_i16",
    op.load_ind_u32: "load_ind_u32",
    op.load_ind_i32: "load_ind_i32",
    op.load_ind_u64: "load_ind_u64",
    op.add_imm_32: "add_imm_32",
    op.and_imm: "and_imm",
    op.xor_imm: "xor_imm",
    op.or_imm: "or_imm",
    op.mul_imm_32: "mul_imm_32",
    op.set_lt_u_imm: "set_lt_u_imm",
    op.set_lt_s_imm: "set_lt_s_imm",
    op.shlo_l_imm_32: "shlo_l_imm_32",
    op.shlo_r_imm_32: "shlo_r_imm_32",
    op.shar_r_imm_32: "shar_r_imm_32",
    op.neg_add_imm_32: "neg_add_imm_32",
    op.set_gt_u_imm: "set_gt_u_imm",
    op.set_gt_s_imm: "set_gt_s_imm",
    op.shlo_l_imm_alt_32: "shlo_l_imm_alt_32",
    op.shlo_r_imm_alt_32: "shlo_r_imm_alt_32",
    op.shar_r_imm_alt_32: "shar_r_imm_alt_32",
    op.cmov_iz_imm: "cmov_iz_imm",
    op.cmov_nz_imm: "cmov_nz_imm",
    op.add_imm_64: "add_imm_64",
    op.mul_imm_64: "mul_imm_64",
    op.shlo_l_imm_64: "shlo_l_imm_64",
    op.shlo_r_imm_64: "shlo_r_imm_64",
    op.shar_r_imm_64: "shar_r_imm_64",
    op.neg_add_imm_64: "neg_add_imm_64",
    op.shlo_l_imm_alt_64: "shlo_l_imm_alt_64",
    op.shlo_r_imm_alt_64: "shlo_r_imm_alt_64",
    op.shar_r_imm_alt_64: "shar_r_imm_alt_64",
    op.rot_r_64_imm: "rot_r_64_imm",
    op.rot_r_64_imm_alt: "rot_r_64_imm_alt",
    op.rot_r_32_imm: "rot_r_32_imm",
    op.rot_r_32_imm_alt: "rot_r_32_imm_alt",

    # GP_A.5.11
    # Instructions with args: reg, reg, offset
    op.branch_eq: "branch_eq",
    op.branch_ne: "branch_ne",
    op.branch_lt_u: "branch_lt_u",
    op.branch_lt_s: "branch_lt_s",
    op.branch_ge_u: "branch_ge_u",
    op.branch_ge_s: "branch_ge_s",

    # GP_A.5.12
    # Instructions with args: reg, reg, imm, im:
    op.load_imm_jump_ind: "load_imm_jump_ind",

    # GP_A.5.13
    # Instructions with args: reg, reg, reg
    op.add_32: "add_32",
    op.sub_32: "sub_32",
    op.mul_32: "mul_32",
    op.div_u_32: "div_u_32",
    op.div_s_32: "div_s_32",
    op.rem_u_32: "rem_u_32",
    op.rem_s_32: "rem_s_32",
    op.shlo_l_32: "shlo_l_32",
    op.shlo_r_32: "shlo_r_32",
    op.shar_r_32: "shar_r_32",
    op.add_64: "add_64",
    op.sub_64: "sub_64",
    op.mul_64: "mul_64",
    op.div_u_64: "div_u_64",
    op.div_s_64: "div_s_64",
    op.rem_u_64: "rem_u_64",
    op.rem_s_64: "rem_s_64",
    op.shlo_l_64: "shlo_l_64",
    op.shlo_r_64: "shlo_r_64",
    op.shar_r_64: "shar_r_64",
    op._and: "_and",
    op.xor: "xor",
    op._or: "_or",
    op.mul_upper_s_s: "mul_upper_s_s",
    op.mul_upper_u_u: "mul_upper_u_u",
    op.mul_upper_s_u: "mul_upper_s_u",
    op.set_lt_u: "set_lt_u",
    op.set_lt_s: "set_lt_s",
    op.cmov_iz: "cmov_iz",
    op.cmov_nz: "cmov_nz",
    op.rot_l_64: "rot_l_64",
    op.rot_l_32: "rot_l_32",
    op.rot_r_64: "rot_r_64",
    op.rot_r_32: "rot_r_32",
    op.and_inv: "and_inv",
    op.or_inv: "or_inv",
    op.xnor: "xnor",
    op._max: "_max",
    op.max_u: "max_u",
    op._min: "_min",
    op.min_u: "min_u"
}

op_trap = 0
op_fallthrough = 1
op_ecalli = 10
op_load_imm_64 = 20
op_store_imm_u8 = 30
op_store_imm_u16 = 31
op_store_imm_u32 = 32
op_store_imm_u64 = 33
op_jump = 40
op_jump_ind = 50
op_load_imm = 51
op_load_u8 = 52
op_load_i8 = 53
op_load_u16 = 54
op_load_i16 = 55
op_load_u32 = 56
op_load_i32 = 57
op_load_u64 = 58
op_store_u8 = 59
op_store_u16 = 60
op_store_u32 = 61
op_store_u64 = 62
op_store_imm_ind_u8 = 70
op_store_imm_ind_u16 = 71
op_store_imm_ind_u32 = 72
op_store_imm_ind_u64 = 73
op_load_imm_jump = 80
op_branch_eq_imm = 81
op_branch_ne_imm = 82
op_branch_lt_u_imm = 83
op_branch_le_u_imm = 84
op_branch_ge_u_imm = 85
op_branch_gt_u_imm = 86
op_branch_lt_s_imm = 87
op_branch_le_s_imm = 88
op_branch_ge_s_imm = 89
op_branch_gt_s_imm = 90
op_move_reg = 100
op_sbrk = 101
op_count_set_bits_64 = 102
op_count_set_bits_32 = 103
op_leading_zero_bits_64 = 104
op_leading_zero_bits_32 = 105
op_trailing_zero_bits_64 = 106
op_trailing_zero_bits_32 = 107
op_sign_extend_8 = 108
op_sign_extend_16 = 109
op_zero_extend_16 = 110
op_reverse_bytes = 111
op_store_ind_u8 = 120
op_store_ind_u16 = 121
op_store_ind_u32 = 122
op_store_ind_u64 = 123
op_load_ind_u8 = 124
op_load_ind_i8 = 125
op_load_ind_u16 = 126
op_load_ind_i16 = 127
op_load_ind_u32 = 128
op_load_ind_i32 = 129
op_load_ind_u64 = 130
op_add_imm_32 = 131
op_and_imm = 132
op_xor_imm = 133
op_or_imm = 134
op_mul_imm_32 = 135
op_set_lt_u_imm = 136
op_sub_imm = 92
op_mul_imm = 96
op_shlo_l_imm = 99
op_set_lt_s_imm = 137
op_shlo_l_imm_32 = 138
op_shlo_r_imm_32 = 139
op_shar_r_imm_32 = 140
op_neg_add_imm_32 = 141
op_set_gt_u_imm = 142
op_set_gt_s_imm = 143
op_shlo_l_imm_alt_32 = 144
op_shlo_r_imm_alt_32 = 145
op_shar_r_imm_alt_32 = 146
op_cmov_iz_imm = 147
op_cmov_nz_imm = 148
op_add_imm_64 = 149
op_mul_imm_64 = 150
op_shlo_l_imm_64 = 151
op_shlo_r_imm_64 = 152
op_shar_r_imm_64 = 153
op_neg_add_imm_64 = 154
op_shlo_l_imm_alt_64 = 155
op_shlo_r_imm_alt_64 = 156
op_shar_r_imm_alt_64 = 157
op_rot_r_64_imm = 158
op_rot_r_64_imm_alt = 159
op_rot_r_32_imm = 160
op_rot_r_32_imm_alt = 161
op_branch_eq = 170
op_branch_ne = 171
op_branch_lt_u = 172
op_branch_lt_s = 173
op_branch_ge_u = 174
op_branch_ge_s = 175
op_load_imm_jump_ind = 180
op_add_32 = 190
op_sub_32 = 191
op_mul_32 = 192
op_div_u_32 = 193
op_div_s_32 = 194
op_rem_u_32 = 195
op_rem_s_32 = 196
op_shlo_l_32 = 197
op_shlo_r_32 = 198
op_shar_r_32 = 199
op_add_64 = 200
op_sub_64 = 201
op_mul_64 = 202
op_div_u_64 = 203
op_div_s_64 = 204
op_rem_u_64 = 205
op_rem_s_64 = 206
op_shlo_l_64 = 207
op_shlo_r_64 = 208
op_shar_r_64 = 209
op_and = 210
op_xor = 211
op_or = 212
op_mul_upper_s_s = 213
op_mul_upper_u_u = 214
op_mul_upper_s_u = 215
op_set_lt_u = 216
op_set_lt_s = 217
op_cmov_iz = 218
op_cmov_nz = 219
op_rot_l_64 = 220
op_rot_l_32 = 221
op_rot_r_64 = 222
op_rot_r_32 = 223
op_and_inv = 224
op_or_inv = 225
op_xnor = 226
op_max = 227
op_max_u = 228
op_min = 229
op_min_u = 230