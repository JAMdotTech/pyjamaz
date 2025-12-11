"""
Optional logging for the gas model

- Debug gas mismatches; see exactly where timing differs from reference
- Visualize parallelism; Out-of-order execution runs independent instructions concurrently
- Spot hazards; = shows RAW dependencies stalling instructions

Timeline Legend:
    - D : Decode cycle
    - = : Waiting (decoded but blocked on dependencies)
    - e : Executing
    - E : Execution complete
    - - : Waiting to retire (in-order commit)
    - R : Retire cycle
    - . : Not yet decoded

usage:

from pyjamaz.pvm.gas_model import GasModel
from pyjamaz.pvm.gas_model_logger import TimelineTracker

# logging enabled:
tracker = TimelineTracker()
gas_model = GasModel(..., timeline_tracker=tracker)
cost = gas_model.compute_block_gas_cost(block_pc)
timeline = tracker.get_timeline(block_pc)
print(tracker.render_timeline(timeline, gas_model))

# without logging
gas_model = GasModel(...)
cost = gas_model.compute_block_gas_cost(block_pc)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pyjamaz.pvm.gas_model import GasModel

from pyjamaz.pvm.constants import InstructionType, Opcode


@dataclass
class InstructionTimeline:
    """
    Timeline events for a single instruction in the pipeline.

    Used to generate ASCII timeline visualizations for debugging.
    """
    pc: int                              # Instruction PC
    decode_cycle: int                    # Cycle when decoded (D)
    issue_cycle: Optional[int] = None    # Cycle when issued/started executing
    complete_cycle: Optional[int] = None # Cycle when execution completed (E)
    retire_cycle: Optional[int] = None   # Cycle when retired (R)
    is_move_reg: bool = False            # move_reg doesn't enter ROB


@dataclass
class BlockTimeline:
    """
    Complete timeline data for a basic block simulation.
    """
    block_start_pc: int
    total_cycles: int                    # Raw cycles (before -3 adjustment)
    gas_cost: int                        # Final gas cost (max(cycles-3, 1))
    instructions: List[InstructionTimeline] = field(default_factory=list)


class TimelineTracker:
    """
    Tracks pipeline timing events during gas model simulation.

    This class is designed to be optionally passed to GasModel. When present,
    the gas model will call tracking methods during simulation. When absent,
    no tracking overhead is incurred.
    """

    def __init__(self):
        self._timelines: Dict[int, Dict[int, InstructionTimeline]] = {}
        self._instruction_order: Dict[int, List[int]] = {}
        self._current_block: Optional[int] = None
        self._total_cycles: Dict[int, int] = {}

    def start_block(self, block_pc: int) -> None:
        """Called when starting simulation of a new block."""
        self._current_block = block_pc
        self._timelines[block_pc] = {}
        self._instruction_order[block_pc] = []

    def end_block(self, block_pc: int, total_cycles: int) -> None:
        """Called when block simulation completes."""
        self._total_cycles[block_pc] = total_cycles

    def record_decode(self, pc: int, cycle: int, is_move_reg: bool = False) -> None:
        """Record instruction decode event."""
        if self._current_block is None:
            return
        self._timelines[self._current_block][pc] = InstructionTimeline(
            pc=pc,
            decode_cycle=cycle,
            is_move_reg=is_move_reg,
        )
        self._instruction_order[self._current_block].append(pc)

    def record_issue(self, pc: int, cycle: int) -> None:
        """Record instruction issue event."""
        if self._current_block is None:
            return
        timeline = self._timelines[self._current_block].get(pc)
        if timeline:
            timeline.issue_cycle = cycle

    def record_complete(self, pc: int, cycle: int) -> None:
        """Record instruction execution complete event."""
        if self._current_block is None:
            return
        timeline = self._timelines[self._current_block].get(pc)
        if timeline:
            timeline.complete_cycle = cycle

    def record_retire(self, pc: int, cycle: int) -> None:
        """Record instruction retire event."""
        if self._current_block is None:
            return
        timeline = self._timelines[self._current_block].get(pc)
        if timeline and timeline.retire_cycle is None:
            timeline.retire_cycle = cycle

    def get_timeline(self, block_pc: int) -> Optional[BlockTimeline]:
        """Get the recorded timeline for a block."""
        if block_pc not in self._timelines:
            return None

        total_cycles = self._total_cycles.get(block_pc, 0)
        gas_cost = max(total_cycles - 3, 1)

        instructions = [
            self._timelines[block_pc][pc]
            for pc in self._instruction_order.get(block_pc, [])
            if pc in self._timelines[block_pc]
        ]

        return BlockTimeline(
            block_start_pc=block_pc,
            total_cycles=total_cycles,
            gas_cost=gas_cost,
            instructions=instructions,
        )

    def clear(self) -> None:
        """Clear all recorded timelines."""
        self._timelines.clear()
        self._instruction_order.clear()
        self._total_cycles.clear()
        self._current_block = None

    # =========================================================================
    # Rendering
    # =========================================================================

    def render_timeline(self, timeline: BlockTimeline, gas_model: 'GasModel') -> str:
        """
        Render a BlockTimeline as ASCII art matching the graypaper test format.

        Format:
            DeeeeeER...  instruction_disasm
            D=eE---R...  instruction_disasm

        Legend:
            . = not yet decoded
            D = decode cycle
            = = waiting (decoded but blocked)
            e = executing
            E = execution complete
            - = waiting to retire (in-order commit)
            R = retire cycle
        """
        lines = []
        total_width = timeline.total_cycles

        for inst in timeline.instructions:
            line = self._render_instruction_timeline(inst, total_width)
            disasm = disassemble(gas_model, inst.pc)
            lines.append(f"    {line}  {disasm}")

        return "\n".join(lines)

    def _render_instruction_timeline(self, inst: InstructionTimeline, total_width: int) -> str:
        """Render timeline for a single instruction."""
        chars = []

        for cycle in range(total_width):
            if cycle < inst.decode_cycle:
                # Before decode
                chars.append('.')
            elif cycle == inst.decode_cycle:
                # Decode cycle
                chars.append('D')
            elif inst.is_move_reg:
                # move_reg doesn't enter ROB - just show dots after decode
                chars.append('.')
            elif inst.issue_cycle is None:
                # Never issued (shouldn't happen for valid blocks)
                chars.append('.')
            elif cycle < inst.issue_cycle:
                # Waiting for issue (decoded but blocked)
                chars.append('=')
            elif inst.complete_cycle is None:
                # Still executing
                chars.append('e')
            elif cycle < inst.complete_cycle:
                # Executing
                chars.append('e')
            elif cycle == inst.complete_cycle:
                # Execution complete
                chars.append('E')
            elif inst.retire_cycle is None:
                # Waiting to retire
                chars.append('-')
            elif cycle < inst.retire_cycle:
                # Waiting to retire (in-order commit)
                chars.append('-')
            elif cycle == inst.retire_cycle:
                # Retire cycle
                chars.append('R')
            else:
                # After retire
                chars.append('-')

        return ''.join(chars)


# =============================================================================
# Disassembly Helper
# =============================================================================

def disassemble(gas_model: 'GasModel', pc: int) -> str:
    """
    Disassembly of instruction at given pc.
    Returns a human-readable string matching the graypaper TESTCASES.md format.
    """
    if pc >= len(gas_model.sim_code):
        return "invalid"

    opcode = gas_model.sim_code[pc]

    # Get opcode name
    try:
        op_name = Opcode(opcode).name
    except ValueError:
        return f"unknown({opcode})"

    # Get instruction type and length
    inst_type = gas_model.opcode_scheme.get(opcode, InstructionType.none)
    inst_index = gas_model.inst_pos_sim.get(pc, 0)
    arg_len = gas_model.inst_arg_len_sim[inst_index] if inst_index < len(gas_model.inst_arg_len_sim) else 0

    # Simple cases - no arguments
    if inst_type == InstructionType.none:
        # Match reference format: "trap" -> "invalid"
        if op_name == "trap":
            return "invalid"
        return op_name

    # Read register byte if present
    if pc + 1 >= len(gas_model.sim_code):
        return op_name

    reg_byte = gas_model.sim_code[pc + 1]
    r_a = reg_byte % 16
    r_b = reg_byte // 16

    # Format based on instruction type
    match inst_type:
        case InstructionType.reg_imm:
            if arg_len > 1:
                imm = _read_imm(gas_model.sim_code, pc + 2, arg_len - 1)
                return f"r{r_a} = {op_name}(0x{imm:x})"
            return f"r{r_a} = {op_name}"

        case InstructionType.reg_reg:
            if op_name == "move_reg":
                return f"r{r_a} = r{r_b}"
            return f"r{r_a} = {op_name} r{r_b}"

        case InstructionType.reg_reg_imm:
            if arg_len > 1:
                imm = _read_imm(gas_model.sim_code, pc + 2, arg_len - 1)
                return f"r{r_a} = r{r_b} {op_name} 0x{imm:x}"
            return f"r{r_a} = r{r_b} {op_name}"

        case InstructionType.offset:
            offset = _read_signed_offset(gas_model.sim_code, pc + 1, arg_len)
            return f"{op_name} {offset}"

        case InstructionType.reg_reg_offset:
            if arg_len > 1:
                offset = _read_signed_offset(gas_model.sim_code, pc + 2, arg_len - 1)
                return f"{op_name} {offset} if r{r_a} ? r{r_b}"
            return f"{op_name} r{r_a}, r{r_b}"

        case InstructionType.reg_imm_offset:
            return f"r{r_a} {op_name}"

        case _:
            return op_name


def _read_imm(code: bytes, offset: int, length: int) -> int:
    if offset + length > len(code):
        return 0
    value = 0
    for i in range(length):
        value |= code[offset + i] << (8 * i)
    return value


def _read_signed_offset(code: bytes, offset: int, length: int) -> int:
    value = _read_imm(code, offset, length)
    # Note: sign extend
    if length > 0 and value >= (1 << (8 * length - 1)):
        value -= (1 << (8 * length))
    return value


def render_block_timeline(gas_model: 'GasModel',
                          block_pc: int,
                          tracker: Optional[TimelineTracker] = None) -> str:
    if tracker is None:
        tracker = TimelineTracker()

    # Compute with tracking
    gas_model.compute_block_gas_cost(block_pc, timeline_tracker=tracker)
    timeline = tracker.get_timeline(block_pc)

    if timeline is None:
        return f"No timeline data for block at PC {block_pc}"

    header = f"Gas simulation at offset {block_pc} with total cost of {timeline.gas_cost}:\n\n```"
    footer = "```"
    body = tracker.render_timeline(timeline, gas_model)
    return f"{header}\n{body}\n{footer}"
