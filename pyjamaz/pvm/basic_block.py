"""
GP-0.7.2-section:A.3 - Basic Blocks and Termination Instructions
"""
import bisect
from typing import Dict, List, Set

from pyjamaz.pvm.constants import TERMINATION_OPCODES, Opcode as op


def calculate_jump_offset(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    arg_len = inst_arg_len[inst_index]
    if arg_len == 0:
        return 0
    return _read_signed_offset(code, pc + 1, arg_len)


def calculate_jump_target(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    return pc + calculate_jump_offset(code, inst_arg_len, pc, inst_index)


def calculate_branch_reg_offset(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    arg_len = inst_arg_len[inst_index]
    if arg_len <= 1:
        return 0
    return _read_signed_offset(code, pc + 2, arg_len - 1)


def calculate_branch_reg_target(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    return pc + calculate_branch_reg_offset(code, inst_arg_len, pc, inst_index)


def calculate_branch_imm_offset(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    arg_len = inst_arg_len[inst_index]
    if arg_len < 1:
        return 0

    # Extract immediate length from register byte bits 4-6
    l_x = min(4, (code[pc + 1] // 16) % 8)
    # Offset length is remaining bytes: arg_len - 1 (reg byte) - l_x (imm bytes)
    l_y = min(4, max(0, arg_len - l_x - 1))

    if l_y <= 0:
        return 0

    return _read_signed_offset(code, pc + 2 + l_x, l_y)


def calculate_branch_imm_target(code: bytes, inst_arg_len: List[int], pc: int, inst_index: int) -> int:
    return pc + calculate_branch_imm_offset(code, inst_arg_len, pc, inst_index)


def _read_signed_offset(code: bytes, offset: int, length: int) -> int:
    if length <= 0 or offset + length > len(code):
        return 0

    # Read unsigned value
    value = 0
    for i in range(length):
        value |= code[offset + i] << (8 * i)

    # Sign extend
    if value >= (1 << (8 * length - 1)):
        value -= (1 << (8 * length))

    return value


def detect_basic_blocks(
    code: bytes,
    code_length: int,
    inst_pos: Dict[int, int],
    inst_arg_len: List[int],
) -> Set[int]:
    """
    GP-0.7.2-section:A.3 - Basic Blocks and Termination Instructions

    Detect all basic block start positions in the code.
    A basic block starts at:
    - PC 0 (always)
    - Fallthrough position after any termination instruction
    - Target of any branch/jump instruction
    """
    # GP-0.7.2-section:A.5 - ϖ (beginning of basic-blocks)
    basic_block_starts = {0}

    # GP-0.7.2-section:A.3 - U (all valid opcodes within original code)
    opcode_positions = sorted(k for k in inst_pos.keys() if k < code_length)

    for pc in opcode_positions:
        opcode = code[pc]

        if opcode in TERMINATION_OPCODES:
            inst_index = inst_pos[pc]
            skip = inst_arg_len[inst_index] + 1
            fallthrough = pc + skip

            # Add fallthrough if it's a valid instruction position
            if fallthrough in inst_pos:
                # Include synthetic trap only for 'fallthrough' opcode
                if fallthrough < code_length or opcode == op.fallthrough.value:
                    basic_block_starts.add(fallthrough)

            # Add branch/jump targets
            if opcode == op.jump.value:
                target = calculate_jump_target(code, inst_arg_len, pc, inst_index)
                if target in inst_pos:
                    basic_block_starts.add(target)

            elif opcode in {
                op.branch_eq.value, op.branch_ne.value,
                op.branch_lt_u.value, op.branch_lt_s.value,
                op.branch_ge_u.value, op.branch_ge_s.value,
            }:
                target = calculate_branch_reg_target(code, inst_arg_len, pc, inst_index)
                if target in inst_pos:
                    basic_block_starts.add(target)

            elif opcode == op.load_imm_jump.value:
                target = calculate_branch_imm_target(code, inst_arg_len, pc, inst_index)
                if target in inst_pos:
                    basic_block_starts.add(target)

            elif opcode in {
                op.branch_eq_imm.value, op.branch_ne_imm.value,
                op.branch_lt_u_imm.value, op.branch_ge_u_imm.value,
                op.branch_le_u_imm.value, op.branch_gt_u_imm.value,
                op.branch_lt_s_imm.value, op.branch_ge_s_imm.value,
                op.branch_le_s_imm.value, op.branch_gt_s_imm.value,
            }:
                target = calculate_branch_imm_target(code, inst_arg_len, pc, inst_index)
                if target in inst_pos:
                    basic_block_starts.add(target)

    # Make sure to be within code bounds (including synthetic trap position)
    basic_block_starts = {pc for pc in basic_block_starts if 0 <= pc <= code_length}

    return basic_block_starts


def get_block_start(basic_block_starts_sorted: List[int], pc: int) -> int:
    # find the basic block that contains the given PC
    idx = bisect.bisect_right(basic_block_starts_sorted, pc) - 1
    return basic_block_starts_sorted[idx] if idx >= 0 else 0
