"""Deterministic virtual-CPU gas calculation (GP-0.8.0-sec:A.9/A.10).

This is a calculation over instruction bytes and register *indices*. It never
executes instructions or inspects PVM registers, memory, or host-call effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from pyjamaz.pvm.constants import (
    TERMINATION_OPCODES,
    InstructionType,
    Opcode,
    OpcodeScheme,
)


if TYPE_CHECKING:
    from pyjamaz.pvm.gas_model_logger import TimelineTracker


# Execution-unit order is A, L, S, M, D (GP-0.8.0-eq:A.51).
Units = tuple[int, int, int, int, int]
_ALU: Units = (1, 0, 0, 0, 0)
_NONE: Units = (0, 0, 0, 0, 0)
_LOAD: Units = (1, 1, 0, 0, 0)
_STORE: Units = (1, 0, 1, 0, 0)
_MULTIPLY: Units = (1, 0, 0, 1, 0)
_DIVIDE: Units = (1, 0, 0, 0, 1)


@dataclass(frozen=True, slots=True)
class InstructionCost:
    cycles: int
    decode_slots: int
    units: Units


@dataclass(frozen=True, slots=True)
class _CostRule:
    cycles: int
    decode_slots: int
    units: Units = _ALU
    overlap_slots: int | None = None
    first_source_only: bool = False


def _cost_rules() -> dict[int, _CostRule]:
    """The complete GP-0.8.0-sec:A.10 table, grouped by identical rows."""
    rules: dict[int, _CostRule] = {}

    def add(names: str, cycles: int, slots: int, units: Units = _ALU,
            overlap: int | None = None, first_source: bool = False) -> None:
        for name in names.split():
            opcode = Opcode[name].value
            if opcode in rules:
                raise RuntimeError(f"duplicate gas cost for {name}")
            rules[opcode] = _CostRule(cycles, slots, units, overlap, first_source)

    add("move_reg", 0, 1, _NONE)
    add("_and xor _or add_64 sub_64", 1, 2, overlap=1)
    add("add_32 sub_32", 2, 3, overlap=2)
    add("and_imm xor_imm or_imm add_imm_64 shlo_r_imm_64 shar_r_imm_64 "
        "shlo_l_imm_64 rot_r_64_imm reverse_bytes", 1, 2, overlap=1)
    add("add_imm_32 shlo_r_imm_32 shar_r_imm_32 shlo_l_imm_32 rot_r_32_imm",
        2, 3, overlap=2)
    add("count_set_bits_64 count_set_bits_32 leading_zero_bits_64 "
        "leading_zero_bits_32 sign_extend_8 sign_extend_16 zero_extend_16", 1, 1)
    add("trailing_zero_bits_64 trailing_zero_bits_32", 2, 1, (2, 0, 0, 0, 0))
    add("shlo_l_64 shlo_r_64 shar_r_64 rot_l_64 rot_r_64",
        1, 3, overlap=2, first_source=True)
    add("shlo_l_32 shlo_r_32 shar_r_32 rot_l_32 rot_r_32",
        2, 4, overlap=3, first_source=True)
    add("shlo_l_imm_alt_64 shlo_r_imm_alt_64 shar_r_imm_alt_64 rot_r_64_imm_alt",
        1, 3)
    add("shlo_l_imm_alt_32 shlo_r_imm_alt_32 shar_r_imm_alt_32 rot_r_32_imm_alt",
        2, 4)
    add("set_lt_u set_lt_s set_lt_u_imm set_lt_s_imm set_gt_u_imm set_gt_s_imm", 3, 3)
    add("cmov_iz cmov_nz", 2, 2)
    add("cmov_iz_imm cmov_nz_imm", 2, 3)
    add("_max max_u _min min_u", 3, 3, overlap=2)
    add("load_ind_u8 load_ind_i8 load_ind_u16 load_ind_i16 load_ind_u32 "
        "load_ind_i32 load_ind_u64 load_u8 load_i8 load_u16 load_i16 "
        "load_u32 load_i32 load_u64", 25, 1, _LOAD)
    add("store_imm_ind_u8 store_imm_ind_u16 store_imm_ind_u32 store_imm_ind_u64 "
        "store_ind_u8 store_ind_u16 store_ind_u32 store_ind_u64 "
        "store_imm_u8 store_imm_u16 store_imm_u32 store_imm_u64 "
        "store_u8 store_u16 store_u32 store_u64", 25, 1, _STORE)
    add("branch_eq branch_ne branch_lt_u branch_lt_s branch_ge_u branch_ge_s "
        "branch_eq_imm branch_ne_imm branch_lt_u_imm branch_le_u_imm "
        "branch_ge_u_imm branch_gt_u_imm branch_lt_s_imm branch_le_s_imm "
        "branch_ge_s_imm branch_gt_s_imm", 20, 1)
    add("div_u_32 div_s_32 rem_u_32 rem_s_32 div_u_64 div_s_64 rem_u_64 rem_s_64",
        60, 4, _DIVIDE)
    add("and_inv or_inv neg_add_imm_64", 2, 3)
    add("xnor", 2, 3, overlap=2)
    add("neg_add_imm_32", 3, 4)
    add("load_imm", 1, 1, _NONE)
    add("load_imm_64", 1, 2, _NONE)
    add("mul_64 mul_imm_64", 3, 2, _MULTIPLY, overlap=1)
    add("mul_32 mul_imm_32", 4, 3, _MULTIPLY, overlap=2)
    add("mul_upper_s_s mul_upper_u_u", 4, 4, _MULTIPLY)
    add("mul_upper_s_u", 6, 4, _MULTIPLY)
    add("trap fallthrough", 2, 1, _NONE)
    add("unlikely", 40, 1, _NONE)
    add("jump load_imm_jump", 15, 1, _NONE)
    add("jump_ind load_imm_jump_ind", 22, 1, _NONE)
    add("ecalli", 100, 4)
    return rules


_COSTS = MappingProxyType(_cost_rules())
_CONDITIONAL_MOVES = frozenset((Opcode.cmov_iz.value, Opcode.cmov_nz.value))
_CONDITIONAL_IMMEDIATES = frozenset((Opcode.cmov_iz_imm.value, Opcode.cmov_nz_imm.value))


def _byte(code: bytes, index: int) -> int:
    # A.4's infinite zero suffix must never turn a negative target into a Python
    # index relative to the end of the code.
    return code[index] if 0 <= index < len(code) else 0


def instruction_registers(
    code: bytes, pc: int, *, polkavm_cmov: bool = False,
) -> tuple[int, int]:
    """Return source and destination register bitmasks (GP-0.8.0-sec:A.5).

    Conditional moves read the previous destination as well as their explicit
    operands. Host calls read/write no registers in this static model (A.9).
    Register bytes follow the instruction table even if skip-distance is zero.

    The explicit PR112 compatibility mode omits only the old conditional-move
    destination dependency, following PolkaVM's simulator. The default keeps
    the previous destination from the unchanged branch in the A.5 equations.
    """
    opcode = _byte(code, pc)
    if opcode not in _COSTS:
        raise ValueError(f"invalid GP-0.8.0 opcode {opcode}")
    scheme = OpcodeScheme[opcode]
    first = _byte(code, pc + 1)
    low, high = min(12, first & 15), min(12, first >> 4)
    a, b = 1 << low, 1 << high

    if scheme in (InstructionType.none, InstructionType.imm,
                  InstructionType.imm_imm, InstructionType.offset):
        return 0, 0
    if scheme == InstructionType.reg_ext_imm:
        return 0, a
    if scheme == InstructionType.reg_imm:
        if opcode == Opcode.jump_ind.value or Opcode.store_u8.value <= opcode <= Opcode.store_u64.value:
            return a, 0
        return 0, a
    if scheme == InstructionType.reg_imm_imm:
        return a, 0
    if scheme == InstructionType.reg_imm_offset:
        return (0, a) if opcode == Opcode.load_imm_jump.value else (a, 0)
    if scheme == InstructionType.reg_reg:
        return b, a
    if scheme == InstructionType.reg_reg_imm:
        if Opcode.store_ind_u8.value <= opcode <= Opcode.store_ind_u64.value:
            return a | b, 0
        return (a | b if opcode in _CONDITIONAL_IMMEDIATES and not polkavm_cmov else b), a
    if scheme == InstructionType.reg_reg_offset:
        return a | b, 0
    if scheme == InstructionType.reg_reg_imm_imm:
        return b, a
    if scheme == InstructionType.reg_reg_reg:
        dest = 1 << min(12, _byte(code, pc + 2))
        return (a | b | dest if opcode in _CONDITIONAL_MOVES and not polkavm_cmov else a | b), dest
    raise ValueError(f"unsupported instruction scheme {scheme}")


def _signed_offset(code: bytes, start: int, size: int) -> int:
    if not size:
        return 0
    value = sum(_byte(code, start + i) << (8 * i) for i in range(size))
    return value - (1 << (8 * size)) if value & (1 << (8 * size - 1)) else value


def instruction_cost(code: bytes, pc: int, arg_len: int) -> InstructionCost:
    """Return the A.10 cost row, including static overlap/branch adjustments."""
    opcode = _byte(code, pc)
    try:
        rule = _COSTS[opcode]
    except KeyError as exc:
        raise ValueError(f"invalid GP-0.8.0 opcode {opcode}") from exc
    slots = rule.decode_slots
    if rule.overlap_slots is not None:
        sources, destinations = instruction_registers(code, pc)
        if rule.first_source_only:
            # A.63's prose and code-only inputs identify register indices, not
            # run-time register values. The first source is A for this scheme.
            sources = 1 << min(12, _byte(code, pc + 1) & 15)
        if sources & destinations:
            slots = rule.overlap_slots

    cycles = rule.cycles
    scheme = OpcodeScheme[opcode]
    if scheme == InstructionType.reg_reg_offset:
        target = pc + _signed_offset(code, pc + 2, min(4, max(0, arg_len - 1)))
    elif scheme == InstructionType.reg_imm_offset and opcode != Opcode.load_imm_jump.value:
        immediate_len = min(4, (_byte(code, pc + 1) >> 4) & 7)
        offset_len = min(4, max(0, arg_len - immediate_len - 1))
        target = pc + _signed_offset(code, pc + 2 + immediate_len, offset_len)
    else:
        return InstructionCost(cycles, slots, rule.units)
    # A.65 examines instruction *bytes*, not whether either target is valid.
    if _byte(code, target) in (Opcode.trap.value, Opcode.unlikely.value) or _byte(
        code, pc + 1 + arg_len
    ) in (Opcode.trap.value, Opcode.unlikely.value):
        cycles = 1
    return InstructionCost(cycles, slots, rule.units)


_DEC, _WAIT, _EXE, _FIN = range(4)


@dataclass(slots=True, eq=False)
class _Entry:
    state: int
    cycles_left: int
    dependencies: tuple[_Entry, ...]
    registers: int
    units: Units
    pc: int


def calculate_block_gas(
    code: bytes,
    inst_pos: dict[int, int],
    inst_arg_len: Sequence[int],
    start: int,
    *,
    polkavm_cmov: bool = False,
    timeline_tracker: TimelineTracker | None = None,
) -> int:
    """Simulate one complete basic block (GP-0.8.0-eq:A.54-A.61).

    ``inst_pos`` maps opcode byte offsets to ordinals in ``inst_arg_len``;
    lengths exclude the opcode and are A.3 skip-distances. The caller validates
    the program and supplies its basic-block start. A private trailing trap
    sentinel is permitted. Ecalli does not terminate a basic block.

    At most 32 reorder entries are live. Removing the retired prefix is an
    equivalent bounded representation of the paper's entries with null state;
    any references to them have zero remaining cycles.
    """
    if start not in inst_pos or start < 0:
        raise ValueError(f"invalid basic-block start {start}")
    pc: int | None = start
    cycles, decode_slots, starts_left = 0, 4, 5
    units = [4, 4, 4, 1, 1]
    rob: list[_Entry] = []
    if timeline_tracker is not None:
        timeline_tracker.start_block(start)

    while True:
        # A.55 gives decoding precedence over starting ready instructions.
        if pc is not None and len(rob) < 32:
            try:
                arg_len = int(inst_arg_len[inst_pos[pc]])
            except (KeyError, IndexError) as exc:
                raise ValueError(f"invalid instruction position {pc}") from exc
            if not 0 <= arg_len <= 24:
                raise ValueError(f"invalid instruction skip-distance {arg_len}")
            cost = instruction_cost(code, pc, arg_len)
            if cost.decode_slots <= decode_slots:
                sources, destinations = instruction_registers(
                    code, pc, polkavm_cmov=polkavm_cmov,
                )
                opcode = _byte(code, pc)
                if timeline_tracker is not None:
                    timeline_tracker.record_decode(pc, cycles, opcode == Opcode.move_reg.value)
                decode_slots -= cost.decode_slots
                if opcode == Opcode.move_reg.value:
                    # A.57: register renaming; no reorder entry or execution.
                    for entry in rob:
                        if entry.registers & sources:
                            entry.registers |= destinations
                        else:
                            entry.registers &= ~destinations
                else:
                    # A.58 dependencies refer to the prior clobber sets; only
                    # after recording them does this write replace old names.
                    dependencies = tuple(entry for entry in rob if entry.registers & sources)
                    for entry in rob:
                        entry.registers &= ~destinations
                    rob.append(_Entry(_DEC, cost.cycles, dependencies, destinations, cost.units, pc))
                pc = None if opcode in TERMINATION_OPCODES else pc + 1 + arg_len
                continue

        if starts_left:
            ready = next((entry for entry in rob if entry.state == _WAIT
                          and all(wanted <= available for wanted, available in zip(entry.units, units))
                          and all(dep.cycles_left == 0 for dep in entry.dependencies)), None)
            if ready is not None:
                # A.59/A.60: lowest eligible reorder index starts first.
                starts_left -= 1
                units = [available - used for available, used in zip(units, ready.units)]
                if timeline_tracker is not None:
                    timeline_tracker.record_issue(ready.pc, cycles)
                ready.state = _EXE
                ready.dependencies = ()
                continue

        if pc is None and not rob:
            if timeline_tracker is not None:
                timeline_tracker.end_block(start, cycles)
            return max(cycles - 3, 1)

        # A.61 is simultaneous: completion/retirement uses the old state and
        # old cycle counts; EXE(1) only becomes FIN on the *next* cycle.
        retired = 0
        for entry in rob:
            if entry.state != _FIN:
                break
            if timeline_tracker is not None:
                timeline_tracker.record_retire(entry.pc, cycles)
            retired += 1
        if retired:
            del rob[:retired]
        for entry in rob:
            if entry.state == _DEC:
                entry.state = _WAIT
            elif entry.state == _EXE:
                if entry.cycles_left == 1:
                    if timeline_tracker is not None:
                        timeline_tracker.record_complete(entry.pc, cycles + 1)
                    units = [available + released for available, released in zip(units, entry.units)]
                if entry.cycles_left == 0:
                    entry.state = _FIN
                else:
                    entry.cycles_left -= 1
        cycles += 1
        decode_slots, starts_left = 4, 5


class GasModel:
    """Bind program metadata for interpreters and the existing timeline renderer.

    All scheduling and pricing live in calculate_block_gas; this wrapper only
    keeps the program inputs together for repeated block calculations.
    """

    opcode_scheme = OpcodeScheme

    def __init__(self, code: bytes, inst_pos: dict[int, int], inst_arg_len: Sequence[int]):
        self.sim_code = code
        self.inst_pos_sim = inst_pos
        self.inst_arg_len_sim = inst_arg_len

    def compute_block_gas_cost(
        self, block_start_pc: int, timeline_tracker: TimelineTracker | None = None,
        *, polkavm_cmov: bool = False,
    ) -> int:
        return calculate_block_gas(
            self.sim_code, self.inst_pos_sim, self.inst_arg_len_sim, block_start_pc,
            polkavm_cmov=polkavm_cmov, timeline_tracker=timeline_tracker,
        )


__all__ = ["GasModel", "InstructionCost", "calculate_block_gas", "instruction_cost", "instruction_registers"]
