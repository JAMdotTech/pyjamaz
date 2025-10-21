from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union


# TODO configurable during bootstrap
PVM_PAGE_SIZE = 2**12 #ZP
PVM_INIT_ZONE_SIZE = 2**16 #ZZ
PVM_INPUT_DATA_SIZE = 2**24 #ZI


MEM_I = 0  # inaccessible memory
MEM_R = 1  # readable memory
MEM_W = 2  # writable memory
MEM_RW = 3  # explicit read/write memory (since we have that bit available anyway :)


class ExitReason(Enum):
    resume:int          = 0 #GP:     ▸: continue PVM
    halt:int            = 1 #GP-A.2: ∎: regular halt: halt
    panic:int           = 2 #GP-A.2: ☇: unexpected program termination: panic
    out_of_gas:int      = 3 #GP-A.2: ∞: out-of-gas
    page_fault:int      = 4 #GP-A.2: F: page-fault
    host_halt:int       = 5 #GP-A.2: h: host-call


@dataclass
class ExitCondition:
    reason: ExitReason
    value: Optional[Union[int, bytes]] = None


class InstructionType(Enum):
    """
    This enum serves as classification for how instructions should be decoded
    """
    none: int                                      = 0   #GP_A.5.1
    imm: int                                       = 1   #GP_A.5.2
    reg_ext_imm: int                               = 2   #GP_A.5.3
    imm_imm: int                                   = 3   #GP_A.5.4
    offset: int                                    = 4   #GP_A.5.5
    reg_imm: int                                   = 5   #GP_A.5.6
    reg_imm_imm: int                               = 6   #GP_A.5.7
    reg_imm_offset: int                            = 7   #GP_A.5.8
    reg_reg: int                                   = 8   #GP_A.5.9
    reg_reg_imm: int                               = 9   #GP_A.5.10
    reg_reg_offset: int                            = 10  #GP_A.5.11
    reg_reg_imm_imm: int                           = 11  #GP_A.5.12
    reg_reg_reg: int                               = 12  #GP_A.5.13


class Opcode(Enum):
    """
    This enum serves as a readable lookup for the different opcodes defined in gp::
    """
    # GP_A.5.1
    # Instructions without Arguments (none)
    trap: int                                      = 0
    fallthrough: int                               = 1

    # GP_A.5.2
    # Instructions with Arguments of One Immediate (imm)
    ecalli: int                                    = 10

    # GP_A.5.3
    # Instructions with Arguments of One Register and One Extended Width Immediate (reg_ext_imm)
    load_imm_64: int                              = 20

    # GP_A.5.4
    # Instructions with Arguments of two Immediates (imm_imm)
    store_imm_u8: int                              = 30
    store_imm_u16: int                             = 31
    store_imm_u32: int                             = 32
    store_imm_u64: int                             = 33

    # GP_A.5.5
    # Instructions with Arguments of One Offset (offset)
    jump: int                                      = 40

    # GP_A.5.6
    # Instructions with Arguments Of One Register & One Immediate (reg_imm)
    jump_ind: int                                  = 50
    load_imm: int                                  = 51
    load_u8: int                                   = 52
    load_i8: int                                   = 53
    load_u16: int                                  = 54
    load_i16: int                                  = 55
    load_u32: int                                  = 56
    load_i32: int                                  = 57
    load_u64: int                                  = 58
    store_u8: int                                  = 59
    store_u16: int                                 = 60
    store_u32: int                                 = 61
    store_u64: int                                 = 62

    # GP_A.5.7
    # Instructions with Arguments Of One Register & Two Immediates (reg_imm_imm)
    store_imm_ind_u8: int                          = 70
    store_imm_ind_u16: int                         = 71
    store_imm_ind_u32: int                         = 72
    store_imm_ind_u64: int                         = 73

    # GP_A.5.8
    # Instructions with Arguments Of One Register, One Immediate and One Offset (reg_imm_offset)
    load_imm_jump: int                             = 80
    branch_eq_imm: int                             = 81
    branch_ne_imm: int                             = 82
    branch_lt_u_imm: int                           = 83
    branch_le_u_imm: int                           = 84
    branch_ge_u_imm: int                           = 85
    branch_gt_u_imm: int                           = 86
    branch_lt_s_imm: int                           = 87
    branch_le_s_imm: int                           = 88
    branch_ge_s_imm: int                           = 89
    branch_gt_s_imm: int                           = 90

    # GP_A.5.9
    # Instructions with Arguments Of Two Registers (reg_reg)
    move_reg: int                                  = 100
    sbrk: int                                      = 101
    count_set_bits_64: int                         = 102
    count_set_bits_32: int                         = 103
    leading_zero_bits_64: int                      = 104
    leading_zero_bits_32: int                      = 105
    trailing_zero_bits_64: int                     = 106
    trailing_zero_bits_32: int                     = 107
    sign_extend_8: int                             = 108
    sign_extend_16: int                            = 109
    zero_extend_16: int                            = 110
    reverse_bytes: int                             = 111

    # GP_A.5.10
    # Instructions with Arguments Of Two Registers & One Immediate (reg_reg_imm)
    store_ind_u8: int                              = 120
    store_ind_u16: int                             = 121
    store_ind_u32: int                             = 122
    store_ind_u64: int                             = 123
    load_ind_u8: int                               = 124
    load_ind_i8: int                               = 125
    load_ind_u16: int                              = 126
    load_ind_i16: int                              = 127
    load_ind_u32: int                              = 128
    load_ind_i32: int                              = 129
    load_ind_u64: int                              = 130
    add_imm_32: int                                = 131
    and_imm: int                                   = 132
    xor_imm: int                                   = 133
    or_imm: int                                    = 134
    mul_imm_32: int                                = 135
    set_lt_u_imm: int                              = 136
    set_lt_s_imm: int                              = 137
    shlo_l_imm_32: int                             = 138
    shlo_r_imm_32: int                             = 139
    shar_r_imm_32: int                             = 140
    neg_add_imm_32: int                            = 141
    set_gt_u_imm: int                              = 142
    set_gt_s_imm: int                              = 143
    shlo_l_imm_alt_32: int                         = 144
    shlo_r_imm_alt_32: int                         = 145
    shar_r_imm_alt_32: int                         = 146
    cmov_iz_imm: int                               = 147
    cmov_nz_imm: int                               = 148
    add_imm_64: int                                = 149
    mul_imm_64: int                                = 150
    shlo_l_imm_64: int                             = 151
    shlo_r_imm_64: int                             = 152
    shar_r_imm_64: int                             = 153
    neg_add_imm_64: int                            = 154
    shlo_l_imm_alt_64: int                         = 155
    shlo_r_imm_alt_64: int                         = 156
    shar_r_imm_alt_64: int                         = 157
    rot_r_64_imm: int                              = 158
    rot_r_64_imm_alt: int                          = 159
    rot_r_32_imm: int                              = 160
    rot_r_32_imm_alt: int                          = 161


    # GP_A.5.11
    # Instructions with Arguments of Two Registers & One Offset (reg_reg_offset)
    branch_eq: int                                 = 170
    branch_ne: int                                 = 171
    branch_lt_u: int                               = 172
    branch_lt_s: int                               = 173
    branch_ge_u: int                               = 174
    branch_ge_s: int                               = 175

    # GP_A.5.12
    # Instructions with Arguments Of Two Registers And Two Immediates (reg_reg_imm_imm)
    load_imm_jump_ind: int                         = 180

    # GP_A.5.13
    # Instructions with Arguments Of Three Registers (reg_reg_reg)
    add_32: int                                    = 190
    sub_32: int                                    = 191
    mul_32: int                                    = 192
    div_u_32: int                                  = 193
    div_s_32: int                                  = 194
    rem_u_32: int                                  = 195
    rem_s_32: int                                  = 196
    shlo_l_32: int                                 = 197
    shlo_r_32: int                                 = 198
    shar_r_32: int                                 = 199
    add_64: int                                    = 200
    sub_64: int                                    = 201
    mul_64: int                                    = 202
    div_u_64: int                                  = 203
    div_s_64: int                                  = 204
    rem_u_64: int                                  = 205
    rem_s_64: int                                  = 206
    shlo_l_64: int                                 = 207
    shlo_r_64: int                                 = 208
    shar_r_64: int                                 = 209
    _and: int                                      = 210
    xor: int                                       = 211
    _or: int                                       = 212
    mul_upper_s_s: int                             = 213
    mul_upper_u_u: int                             = 214
    mul_upper_s_u: int                             = 215
    set_lt_u: int                                  = 216
    set_lt_s: int                                  = 217
    cmov_iz: int                                   = 218
    cmov_nz: int                                   = 219
    rot_l_64: int                                  = 220
    rot_l_32: int                                  = 221
    rot_r_64: int                                  = 222
    rot_r_32: int                                  = 223
    and_inv: int                                   = 224
    or_inv: int                                    = 225
    xnor: int                                      = 226
    _max: int                                      = 227
    max_u: int                                     = 228
    _min: int                                      = 229
    min_u: int                                     = 230


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
    op.count_set_bits_64.value: it.reg_reg,
    op.count_set_bits_32.value: it.reg_reg,
    op.leading_zero_bits_64.value: it.reg_reg,
    op.leading_zero_bits_32.value: it.reg_reg,
    op.trailing_zero_bits_64.value: it.reg_reg,
    op.trailing_zero_bits_32.value: it.reg_reg,
    op.sign_extend_8.value: it.reg_reg,
    op.sign_extend_16.value: it.reg_reg,
    op.zero_extend_16.value: it.reg_reg,
    op.reverse_bytes.value: it.reg_reg,

    # GP_A.5.10
    # Instructions with args: reg, reg, imm
    op.store_ind_u8.value                               : it.reg_reg_imm,
    op.store_ind_u8.value                               : it.reg_reg_imm,
    op.store_ind_u16.value                              : it.reg_reg_imm,
    op.store_ind_u32.value                              : it.reg_reg_imm,
    op.store_ind_u64.value                              : it.reg_reg_imm,
    op.load_ind_u8.value                                : it.reg_reg_imm,
    op.load_ind_i8.value                                : it.reg_reg_imm,
    op.load_ind_u16.value                               : it.reg_reg_imm,
    op.load_ind_i16.value                               : it.reg_reg_imm,
    op.load_ind_u32.value                               : it.reg_reg_imm,
    op.load_ind_i32.value                               : it.reg_reg_imm,
    op.load_ind_u64.value                               : it.reg_reg_imm,
    op.add_imm_32.value                                 : it.reg_reg_imm,
    op.and_imm.value                                    : it.reg_reg_imm,
    op.xor_imm.value                                    : it.reg_reg_imm,
    op.or_imm.value                                     : it.reg_reg_imm,
    op.mul_imm_32.value                                 : it.reg_reg_imm,
    op.set_lt_u_imm.value                               : it.reg_reg_imm,
    op.set_lt_s_imm.value                               : it.reg_reg_imm,
    op.shlo_l_imm_32.value                              : it.reg_reg_imm,
    op.shlo_r_imm_32.value                              : it.reg_reg_imm,
    op.shar_r_imm_32.value                              : it.reg_reg_imm,
    op.neg_add_imm_32.value                             : it.reg_reg_imm,
    op.set_gt_u_imm.value                               : it.reg_reg_imm,
    op.set_gt_s_imm.value                               : it.reg_reg_imm,
    op.shlo_l_imm_alt_32.value                          : it.reg_reg_imm,
    op.shlo_r_imm_alt_32.value                          : it.reg_reg_imm,
    op.shar_r_imm_alt_32.value                          : it.reg_reg_imm,
    op.cmov_iz_imm.value                                : it.reg_reg_imm,
    op.cmov_nz_imm.value                                : it.reg_reg_imm,
    op.add_imm_64.value                                 : it.reg_reg_imm,
    op.mul_imm_64.value                                 : it.reg_reg_imm,
    op.shlo_l_imm_64.value                              : it.reg_reg_imm,
    op.shlo_r_imm_64.value                              : it.reg_reg_imm,
    op.shar_r_imm_64.value                              : it.reg_reg_imm,
    op.neg_add_imm_64.value                             : it.reg_reg_imm,
    op.shlo_l_imm_alt_64.value                          : it.reg_reg_imm,
    op.shlo_r_imm_alt_64.value                          : it.reg_reg_imm,
    op.shar_r_imm_alt_64.value                          : it.reg_reg_imm,
    op.rot_r_64_imm.value                               : it.reg_reg_imm,
    op.rot_r_64_imm_alt.value                           : it.reg_reg_imm,
    op.rot_r_32_imm.value                               : it.reg_reg_imm,
    op.rot_r_32_imm_alt.value                           : it.reg_reg_imm,


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

OpcodeNames = {
    # GP_A.5.1
    # Instructions with args: none
    op.trap.value: "trap",
    op.fallthrough.value: "fallthrough",

    # GP_A.5.2
    # Instructions with args: imm
    op.ecalli.value: "ecalli",

    # GP_A.5.3
    # Instructions with args: reg_ext_imm
    op.load_imm_64.value: "load_imm_64",

    # GP_A.5.4
    # Instructions with args: imm_imm
    op.store_imm_u8.value: "store_imm_u8",
    op.store_imm_u16.value: "store_imm_u16",
    op.store_imm_u32.value: "store_imm_u32",
    op.store_imm_u64.value: "store_imm_u64",

    # GP_A.5.5
    # Instructions with args: offset
    op.jump.value: "jump",

    # GP_A.5.6
    # Instructions with args: reg, imm
    op.jump_ind.value: "jump_ind",
    op.load_imm.value: "load_imm",
    op.load_u8.value: "load_u8",
    op.load_i8.value: "load_i8",
    op.load_u16.value: "load_u16",
    op.load_i16.value: "load_i16",
    op.load_u32.value: "load_u32",
    op.load_i32.value: "load_i32",
    op.load_u64.value: "load_u64",
    op.store_u8.value: "store_u8",
    op.store_u16.value: "store_u16",
    op.store_u32.value: "store_u32",
    op.store_u64.value: "store_u64",

    # GP_A.5.7
    # Instructions with args: reg, imm, imm
    op.store_imm_ind_u8.value: "store_imm_ind_u8",
    op.store_imm_ind_u16.value: "store_imm_ind_u16",
    op.store_imm_ind_u32.value: "store_imm_ind_u32",
    op.store_imm_ind_u64.value: "store_imm_ind_u64",

    # GP_A.5.8
    # Instructions with args: reg, imm, offset
    op.load_imm_jump.value: "load_imm_jump",
    op.branch_eq_imm.value: "branch_eq_imm",
    op.branch_ne_imm.value: "branch_ne_imm",
    op.branch_lt_u_imm.value: "branch_lt_u_imm",
    op.branch_ge_u_imm.value: "branch_ge_u_imm",
    op.branch_le_u_imm.value: "branch_le_u_imm",
    op.branch_gt_u_imm.value: "branch_gt_u_imm",
    op.branch_lt_s_imm.value: "branch_lt_s_imm",
    op.branch_ge_s_imm.value: "branch_ge_s_imm",
    op.branch_le_s_imm.value: "branch_le_s_imm",
    op.branch_gt_s_imm.value: "branch_gt_s_imm",

    # GP_A.5.9
    # Instructions with args: reg, reg
    op.move_reg.value: "move_reg",
    op.sbrk.value: "sbrk",
    op.count_set_bits_64.value: "count_set_bits_64",
    op.count_set_bits_32.value: "count_set_bits_32",
    op.leading_zero_bits_64.value: "leading_zero_bits_64",
    op.leading_zero_bits_32.value: "leading_zero_bits_32",
    op.trailing_zero_bits_64.value: "trailing_zero_bits_64",
    op.trailing_zero_bits_32.value: "trailing_zero_bits_32",
    op.sign_extend_8.value: "sign_extend_8",
    op.sign_extend_16.value: "sign_extend_16",
    op.zero_extend_16.value: "zero_extend_16",
    op.reverse_bytes.value: "reverse_bytes",

    # GP_A.5.10
    # Instructions with args: reg, reg, imm
    op.store_ind_u8.value: "store_ind_u8",
    op.store_ind_u8.value: "store_ind_u8",
    op.store_ind_u16.value: "store_ind_u16",
    op.store_ind_u32.value: "store_ind_u32",
    op.store_ind_u64.value: "store_ind_u64",
    op.load_ind_u8.value: "load_ind_u8",
    op.load_ind_i8.value: "load_ind_i8",
    op.load_ind_u16.value: "load_ind_u16",
    op.load_ind_i16.value: "load_ind_i16",
    op.load_ind_u32.value: "load_ind_u32",
    op.load_ind_i32.value: "load_ind_i32",
    op.load_ind_u64.value: "load_ind_u64",
    op.add_imm_32.value: "add_imm_32",
    op.and_imm.value: "and_imm",
    op.xor_imm.value: "xor_imm",
    op.or_imm.value: "or_imm",
    op.mul_imm_32.value: "mul_imm_32",
    op.set_lt_u_imm.value: "set_lt_u_imm",
    op.set_lt_s_imm.value: "set_lt_s_imm",
    op.shlo_l_imm_32.value: "shlo_l_imm_32",
    op.shlo_r_imm_32.value: "shlo_r_imm_32",
    op.shar_r_imm_32.value: "shar_r_imm_32",
    op.neg_add_imm_32.value: "neg_add_imm_32",
    op.set_gt_u_imm.value: "set_gt_u_imm",
    op.set_gt_s_imm.value: "set_gt_s_imm",
    op.shlo_l_imm_alt_32.value: "shlo_l_imm_alt_32",
    op.shlo_r_imm_alt_32.value: "shlo_r_imm_alt_32",
    op.shar_r_imm_alt_32.value: "shar_r_imm_alt_32",
    op.cmov_iz_imm.value: "cmov_iz_imm",
    op.cmov_nz_imm.value: "cmov_nz_imm",
    op.add_imm_64.value: "add_imm_64",
    op.mul_imm_64.value: "mul_imm_64",
    op.shlo_l_imm_64.value: "shlo_l_imm_64",
    op.shlo_r_imm_64.value: "shlo_r_imm_64",
    op.shar_r_imm_64.value: "shar_r_imm_64",
    op.neg_add_imm_64.value: "neg_add_imm_64",
    op.shlo_l_imm_alt_64.value: "shlo_l_imm_alt_64",
    op.shlo_r_imm_alt_64.value: "shlo_r_imm_alt_64",
    op.shar_r_imm_alt_64.value: "shar_r_imm_alt_64",
    op.rot_r_64_imm.value: "rot_r_64_imm",
    op.rot_r_64_imm_alt.value: "rot_r_64_imm_alt",
    op.rot_r_32_imm.value: "rot_r_32_imm",
    op.rot_r_32_imm_alt.value: "rot_r_32_imm_alt",

    # GP_A.5.11
    # Instructions with args: reg, reg, offset
    op.branch_eq.value: "branch_eq",
    op.branch_ne.value: "branch_ne",
    op.branch_lt_u.value: "branch_lt_u",
    op.branch_lt_s.value: "branch_lt_s",
    op.branch_ge_u.value: "branch_ge_u",
    op.branch_ge_s.value: "branch_ge_s",

    # GP_A.5.12
    # Instructions with args: reg, reg, imm, im:
    op.load_imm_jump_ind.value: "load_imm_jump_ind",

    # GP_A.5.13
    # Instructions with args: reg, reg, reg
    op.add_32.value: "add_32",
    op.sub_32.value: "sub_32",
    op.mul_32.value: "mul_32",
    op.div_u_32.value: "div_u_32",
    op.div_s_32.value: "div_s_32",
    op.rem_u_32.value: "rem_u_32",
    op.rem_s_32.value: "rem_s_32",
    op.shlo_l_32.value: "shlo_l_32",
    op.shlo_r_32.value: "shlo_r_32",
    op.shar_r_32.value: "shar_r_32",
    op.add_64.value: "add_64",
    op.sub_64.value: "sub_64",
    op.mul_64.value: "mul_64",
    op.div_u_64.value: "div_u_64",
    op.div_s_64.value: "div_s_64",
    op.rem_u_64.value: "rem_u_64",
    op.rem_s_64.value: "rem_s_64",
    op.shlo_l_64.value: "shlo_l_64",
    op.shlo_r_64.value: "shlo_r_64",
    op.shar_r_64.value: "shar_r_64",
    op._and.value: "_and",
    op.xor.value: "xor",
    op._or.value: "_or",
    op.mul_upper_s_s.value: "mul_upper_s_s",
    op.mul_upper_u_u.value: "mul_upper_u_u",
    op.mul_upper_s_u.value: "mul_upper_s_u",
    op.set_lt_u.value: "set_lt_u",
    op.set_lt_s.value: "set_lt_s",
    op.cmov_iz.value: "cmov_iz",
    op.cmov_nz.value: "cmov_nz",
    op.rot_l_64.value: "rot_l_64",
    op.rot_l_32.value: "rot_l_32",
    op.rot_r_64.value: "rot_r_64",
    op.rot_r_32.value: "rot_r_32",
    op.and_inv.value: "and_inv",
    op.or_inv.value: "or_inv",
    op.xnor.value: "xnor",
    op._max.value: "_max",
    op.max_u.value: "max_u",
    op._min.value: "_min",
    op.min_u.value: "min_u"
}

TERMINATION_OPCODES = {
    op.trap.value,
    op.fallthrough.value,

    op.jump.value,
    op.jump_ind.value,

    op.load_imm_jump.value,
    op.load_imm_jump_ind.value,

    op.branch_eq_imm.value,
    op.branch_ne_imm.value,
    op.branch_lt_u_imm.value,
    op.branch_ge_u_imm.value,
    op.branch_le_u_imm.value,
    op.branch_gt_u_imm.value,
    op.branch_lt_s_imm.value,
    op.branch_ge_s_imm.value,
    op.branch_le_s_imm.value,
    op.branch_gt_s_imm.value,
    op.branch_eq.value,
    op.branch_ne.value,
    op.branch_lt_u.value,
    op.branch_lt_s.value,
    op.branch_ge_u.value,
    op.branch_ge_s.value
}

inst_none = InstructionType.none.value
inst_imm = InstructionType.imm.value
inst_reg_ext_imm = InstructionType.reg_ext_imm.value
inst_imm_imm = InstructionType.imm_imm.value
inst_offset = InstructionType.offset.value
inst_reg_imm = InstructionType.reg_imm.value
inst_reg_imm_imm = InstructionType.reg_imm_imm.value
inst_reg_imm_offset = InstructionType.reg_imm_offset.value
inst_reg_reg = InstructionType.reg_reg.value
inst_reg_reg_imm = InstructionType.reg_reg_imm.value
inst_reg_reg_offset = InstructionType.reg_reg_offset.value
inst_reg_reg_imm_imm = InstructionType.reg_reg_imm_imm.value
inst_reg_reg_reg = InstructionType.reg_reg_reg.value


op_trap = Opcode.trap.value
op_fallthrough = Opcode.fallthrough.value
op_ecalli = Opcode.ecalli.value
op_load_imm_64 = Opcode.load_imm_64.value
op_store_imm_u8 = Opcode.store_imm_u8.value
op_store_imm_u16 = Opcode.store_imm_u16.value
op_store_imm_u32 = Opcode.store_imm_u32.value
op_store_imm_u64 = Opcode.store_imm_u64.value
op_jump = Opcode.jump.value
op_jump_ind = Opcode.jump_ind.value
op_load_imm = Opcode.load_imm.value
op_load_u8 = Opcode.load_u8.value
op_load_i8 = Opcode.load_i8.value
op_load_u16 = Opcode.load_u16.value
op_load_i16 = Opcode.load_i16.value
op_load_u32 = Opcode.load_u32.value
op_load_i32 = Opcode.load_i32.value
op_load_u64 = Opcode.load_u64.value
op_store_u8 = Opcode.store_u8.value
op_store_u16 = Opcode.store_u16.value
op_store_u32 = Opcode.store_u32.value
op_store_u64 = Opcode.store_u64.value
op_store_imm_ind_u8 = Opcode.store_imm_ind_u8.value
op_store_imm_ind_u16 = Opcode.store_imm_ind_u16.value
op_store_imm_ind_u32 = Opcode.store_imm_ind_u32.value
op_store_imm_ind_u64 = Opcode.store_imm_ind_u64.value
op_load_imm_jump = Opcode.load_imm_jump.value
op_branch_eq_imm = Opcode.branch_eq_imm.value
op_branch_ne_imm = Opcode.branch_ne_imm.value
op_branch_lt_u_imm = Opcode.branch_lt_u_imm.value
op_branch_le_u_imm = Opcode.branch_le_u_imm.value
op_branch_ge_u_imm = Opcode.branch_ge_u_imm.value
op_branch_gt_u_imm = Opcode.branch_gt_u_imm.value
op_branch_lt_s_imm = Opcode.branch_lt_s_imm.value
op_branch_le_s_imm = Opcode.branch_le_s_imm.value
op_branch_ge_s_imm = Opcode.branch_ge_s_imm.value
op_branch_gt_s_imm = Opcode.branch_gt_s_imm.value
op_move_reg = Opcode.move_reg.value
op_sbrk = Opcode.sbrk.value
op_count_set_bits_64 = Opcode.count_set_bits_64.value
op_count_set_bits_32 = Opcode.count_set_bits_32.value
op_leading_zero_bits_64 = Opcode.leading_zero_bits_64.value
op_leading_zero_bits_32 = Opcode.leading_zero_bits_32.value
op_trailing_zero_bits_64 = Opcode.trailing_zero_bits_64.value
op_trailing_zero_bits_32 = Opcode.trailing_zero_bits_32.value
op_sign_extend_8 = Opcode.sign_extend_8.value
op_sign_extend_16 = Opcode.sign_extend_16.value
op_zero_extend_16 = Opcode.zero_extend_16.value
op_reverse_bytes = Opcode.reverse_bytes.value
op_store_ind_u8 = Opcode.store_ind_u8.value
op_store_ind_u16 = Opcode.store_ind_u16.value
op_store_ind_u32 = Opcode.store_ind_u32.value
op_store_ind_u64 = Opcode.store_ind_u64.value
op_load_ind_u8 = Opcode.load_ind_u8.value
op_load_ind_i8 = Opcode.load_ind_i8.value
op_load_ind_u16 = Opcode.load_ind_u16.value
op_load_ind_i16 = Opcode.load_ind_i16.value
op_load_ind_u32 = Opcode.load_ind_u32.value
op_load_ind_i32 = Opcode.load_ind_i32.value
op_load_ind_u64 = Opcode.load_ind_u64.value
op_add_imm_32 = Opcode.add_imm_32.value
op_and_imm = Opcode.and_imm.value
op_xor_imm = Opcode.xor_imm.value
op_or_imm = Opcode.or_imm.value
op_mul_imm_32 = Opcode.mul_imm_32.value
op_set_lt_u_imm = Opcode.set_lt_u_imm.value
op_set_lt_s_imm = Opcode.set_lt_s_imm.value
op_shlo_l_imm_32 = Opcode.shlo_l_imm_32.value
op_shlo_r_imm_32 = Opcode.shlo_r_imm_32.value
op_shar_r_imm_32 = Opcode.shar_r_imm_32.value
op_neg_add_imm_32 = Opcode.neg_add_imm_32.value
op_set_gt_u_imm = Opcode.set_gt_u_imm.value
op_set_gt_s_imm = Opcode.set_gt_s_imm.value
op_shlo_l_imm_alt_32 = Opcode.shlo_l_imm_alt_32.value
op_shlo_r_imm_alt_32 = Opcode.shlo_r_imm_alt_32.value
op_shar_r_imm_alt_32 = Opcode.shar_r_imm_alt_32.value
op_cmov_iz_imm = Opcode.cmov_iz_imm.value
op_cmov_nz_imm = Opcode.cmov_nz_imm.value
op_add_imm_64 = Opcode.add_imm_64.value
op_mul_imm_64 = Opcode.mul_imm_64.value
op_shlo_l_imm_64 = Opcode.shlo_l_imm_64.value
op_shlo_r_imm_64 = Opcode.shlo_r_imm_64.value
op_shar_r_imm_64 = Opcode.shar_r_imm_64.value
op_neg_add_imm_64 = Opcode.neg_add_imm_64.value
op_shlo_l_imm_alt_64 = Opcode.shlo_l_imm_alt_64.value
op_shlo_r_imm_alt_64 = Opcode.shlo_r_imm_alt_64.value
op_shar_r_imm_alt_64 = Opcode.shar_r_imm_alt_64.value
op_rot_r_64_imm = Opcode.rot_r_64_imm.value
op_rot_r_64_imm_alt = Opcode.rot_r_64_imm_alt.value
op_rot_r_32_imm = Opcode.rot_r_32_imm.value
op_rot_r_32_imm_alt = Opcode.rot_r_32_imm_alt.value
op_branch_eq = Opcode.branch_eq.value
op_branch_ne = Opcode.branch_ne.value
op_branch_lt_u = Opcode.branch_lt_u.value
op_branch_lt_s = Opcode.branch_lt_s.value
op_branch_ge_u = Opcode.branch_ge_u.value
op_branch_ge_s = Opcode.branch_ge_s.value
op_load_imm_jump_ind = Opcode.load_imm_jump_ind.value
op_add_32 = Opcode.add_32.value
op_sub_32 = Opcode.sub_32.value
op_mul_32 = Opcode.mul_32.value
op_div_u_32 = Opcode.div_u_32.value
op_div_s_32 = Opcode.div_s_32.value
op_rem_u_32 = Opcode.rem_u_32.value
op_rem_s_32 = Opcode.rem_s_32.value
op_shlo_l_32 = Opcode.shlo_l_32.value
op_shlo_r_32 = Opcode.shlo_r_32.value
op_shar_r_32 = Opcode.shar_r_32.value
op_add_64 = Opcode.add_64.value
op_sub_64 = Opcode.sub_64.value
op_mul_64 = Opcode.mul_64.value
op_div_u_64 = Opcode.div_u_64.value
op_div_s_64 = Opcode.div_s_64.value
op_rem_u_64 = Opcode.rem_u_64.value
op_rem_s_64 = Opcode.rem_s_64.value
op_shlo_l_64 = Opcode.shlo_l_64.value
op_shlo_r_64 = Opcode.shlo_r_64.value
op_shar_r_64 = Opcode.shar_r_64.value
op_and = Opcode._and.value
op_xor = Opcode.xor.value
op_or = Opcode._or.value
op_mul_upper_s_s = Opcode.mul_upper_s_s.value
op_mul_upper_u_u = Opcode.mul_upper_u_u.value
op_mul_upper_s_u = Opcode.mul_upper_s_u.value
op_set_lt_u = Opcode.set_lt_u.value
op_set_lt_s = Opcode.set_lt_s.value
op_cmov_iz = Opcode.cmov_iz.value
op_cmov_nz = Opcode.cmov_nz.value
op_rot_l_64 = Opcode.rot_l_64.value
op_rot_l_32 = Opcode.rot_l_32.value
op_rot_r_64 = Opcode.rot_r_64.value
op_rot_r_32 = Opcode.rot_r_32.value
op_and_inv = Opcode.and_inv.value
op_or_inv = Opcode.or_inv.value
op_xnor = Opcode.xnor.value
op_max = Opcode._max.value
op_max_u = Opcode.max_u.value
op_min = Opcode._min.value
op_min_u = Opcode.min_u.value