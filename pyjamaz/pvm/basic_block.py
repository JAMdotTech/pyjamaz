"""
GP-0.7.2-section:A.3 - Basic Blocks and Termination Instructions
"""
import bisect
from typing import Dict, List, Set

from pyjamaz.pvm.constants import TERMINATION_OPCODES, Opcode as op


def decode_instructions(code, bitmask):
    """Graypaper 0.8 A.2: validate the whole blob, including its final terminator."""
    positions, lengths = {}, []
    if len(code) == 0 or len(code) != len(bitmask):
        return positions, lengths, False
    valid_opcodes = {opcode.value for opcode in op}
    pc = 0
    while pc < len(code):
        if not bitmask[pc] or code[pc] not in valid_opcodes:
            return positions, lengths, False
        length = 0
        while length < 24 and pc + length + 1 < len(code) and not bitmask[pc + length + 1]:
            length += 1
        positions[pc] = len(lengths)
        lengths.append(length)
        last_opcode = code[pc]
        pc += length + 1
    return positions, lengths, last_opcode in TERMINATION_OPCODES


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
    """A.3: only entry zero and instructions following a terminator start blocks."""
    starts = {0} if 0 in inst_pos else set()
    for pc, index in inst_pos.items():
        if pc < code_length and code[pc] in TERMINATION_OPCODES:
            following = pc + inst_arg_len[index] + 1
            if following < code_length and following in inst_pos:
                starts.add(following)
    return starts


def get_block_start(basic_block_starts_sorted: List[int], pc: int) -> int:
    # find the basic block that contains the given PC
    idx = bisect.bisect_right(basic_block_starts_sorted, pc) - 1
    return basic_block_starts_sorted[idx] if idx >= 0 else 0
