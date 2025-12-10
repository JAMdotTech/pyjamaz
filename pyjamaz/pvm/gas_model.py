"""
Brain dump / annotated GP ref:

Naive implementation of the Gas Cost Model (GCM) for the Polkadot Virtual Machine (PVM)
This module implemenst the gas model (Appendix A.9/A.10) which simulates
"a pipelined, out-of-order CPU microarchitecture to compute gas costs for basic blocks."

IT basically predicts how many cycles each basic block takes by simulating CPU execution, taking parallel execution in account!
This has simalarities with compilers; try to reorder instructions - to break dependency chains and let more work happen in parallel
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Set, Tuple

from pyjamaz.pvm.constants import InstructionType, Opcode as op, OpcodeScheme, TERMINATION_OPCODES
from pyjamaz.pvm.interpreters.graypaper.defs import pvm_Z, read_uint


# =============================================================================
# Section 1: Data Structures (GP A.45)
# =============================================================================

class RobStage(IntEnum):
    """
    ROB entry lifecycle stages (s_bar in GP notation).

    Stage transitions:
        DECODED(1) -> READY(2) -> EXECUTING(3) -> RETIRED(4) -> EMPTY(0)
    """
    EMPTY = 0       # Slot is free / entry has been removed
    DECODED = 1     # Just decoded, waiting to become ready
    READY = 2       # Ready to issue (dependencies resolved)
    EXECUTING = 3   # Currently executing on functional units
    RETIRED = 4     # Execution complete, waiting to commit in order


@dataclass
class ExecUnits:
    """
    Execution unit requirements/availability (x_hat / x_ring in GP notation).

    Models the functional units of the virtual CPU:
    - A: Arithmetic/ALU (add, sub, and, xor, shifts, compare, etc.)
    - L: Load unit (memory loads)
    - S: Store unit (memory stores)
    - M: Multiply unit (mul_* operations)
    - D: Divide unit (div_*, rem_* operations)
    """
    A: int = 0
    L: int = 0
    S: int = 0
    M: int = 0
    D: int = 0


@dataclass
class RobEntry:
    """
    Reorder Buffer entry tracking an in-flight instruction.

    GP notation mapping:
    - stage:      s_bar[j] - lifecycle stage (see RobStage)
    - cycles_left: c_bar[j] - remaining execution cycles
    - deps:       p_bar[j] - indices of ROB entries we depend on (RAW hazards)
    - dest_regs:  r_bar[j] - registers this instruction will write
    - units:      x_bar[j] - execution units required
    """
    stage: int
    cycles_left: int
    deps: Set[int]
    dest_regs: Set[int]
    units: ExecUnits


@dataclass
class PipelineState:
    """
    Complete pipeline simulation state (Xi in GP notation).

    GP-0.7.1-eq:A.45 mapping:
    - instruction_pc:   z - next instruction to decode (None when done decoding)
    - cycle_count:      c_dot - total cycles elapsed
    - decode_slots:     d_dot - decode slots remaining this cycle (reset to 4)
    - issue_slots:      e_dot - issue slots remaining this cycle (reset to 5)
    - rob:              s_bar (stages), c_bar (cycles remaining), p_bar dependencies), r_bar (dest regs), x_bar (exec units)
    - units_available:  x_ring - execution units available this cycle
    """
    instruction_pc: Optional[int]
    cycle_count: int
    decode_slots: int
    issue_slots: int
    rob: List[RobEntry]
    units_available: ExecUnits


@dataclass
class InstructionCost:
    """
    Cost parameters for a single instruction type.

    GP notation:
    - latency_fn:  c_hat - execution latency in cycles
    - decode_fn:   d_hat - decode bandwidth cost (slots consumed)
    - units_fn:    x_hat - execution units required
    """
    latency_fn: Callable[[int], int]
    decode_fn: Callable[[int], int]
    units_fn: Callable[[int], ExecUnits]


# =============================================================================
# Section 2: Gas Model Implementation
# =============================================================================

class GasModel:
    """
    Implements the graypaper gas model (Appendix A.9/A.10).

    Simulates a pipelined out-of-order CPU to compute gas costs for basic blocks.
    """

    # Pipeline configuration constants
    MAX_ROB_SIZE = 32
    DECODE_SLOTS_PER_CYCLE = 4
    ISSUE_SLOTS_PER_CYCLE = 5
    INITIAL_EXEC_UNITS = ExecUnits(A=4, L=4, S=4, M=1, D=1)

    def __init__(
        self,
        code: bytes,
        inst_pos: Dict[int, int],
        inst_arg_len: List[int],
        opcode_scheme,
        opcode_enum,
        mem_model: str = "L2HIT",
        jump_table: Optional[List[int]] = None,
    ):
        self.code = code
        self.inst_pos = inst_pos
        self.inst_arg_len = inst_arg_len
        self.opcode_scheme = opcode_scheme
        self.op = opcode_enum
        self.mem_model = mem_model
        self.jump_table = jump_table or []

        # Extend code with synthetic trap for clean termination
        self.sim_code = bytearray(self.code)
        self.inst_arg_len_sim = list(self.inst_arg_len)
        self.inst_pos_sim = dict(self.inst_pos)
        self.inst_pos_sim[len(self.code)] = len(self.inst_arg_len_sim)
        self.inst_arg_len_sim.append(0)
        self.sim_code.append(self.op.trap.value)

        self.cost_table = self._build_instruction_cost_table()

    # =========================================================================
    # Section 2.1: Main Entry Point - Block Gas Cost (GP A.46-A.47)
    # =========================================================================

    def compute_block_gas_cost(self, block_start_pc: int) -> int:
        """
        GP-0.7.1-eq:A.46-A.47

        Simulate the pipeline for a basic block and return its gas cost.

        The simulation runs until all instructions are decoded and the ROB drains.
        Each step applies one of four transitions (A.46):
            1. Xi_decode: Decode next instruction (if possible)
            2. Xi_issue:  Issue a ready instruction (if possible)
            3. Xi_tick:   Advance pipeline by one cycle
            4. Terminate: When ROB is empty and no more instructions

        Final gas cost (A.47): max(cycle_count - 3, 1)
        """
        state = self._create_initial_state(block_start_pc)
        max_steps = 100000

        for _ in range(max_steps):
            # Termination: ROB empty and no more instructions to decode
            if self._should_terminate(state):
                break

            # Handle PC beyond code bounds
            if state.instruction_pc is not None and state.instruction_pc >= len(self.sim_code):
                state = self._set_instruction_pc(state, None)

            # GP A.46: Choose transition based on current state
            if self._can_decode(state):
                state = self._transition_decode(state)
            elif self._can_issue(state):
                state = self._transition_issue(state)
            else:
                state = self._transition_tick(state)

        # GP A.47: Final gas cost
        return max(state.cycle_count - 3, 1)

    # =========================================================================
    # Section 2.2: Initial State (GP A.45)
    # =========================================================================

    def _create_initial_state(self, start_pc: int) -> PipelineState:
        """
        GP-0.7.1-eq:A.45

        Create initial pipeline state Xi_0(t) for block starting at start_pc.
        """
        return PipelineState(
            instruction_pc=start_pc,
            cycle_count=0,
            decode_slots=self.DECODE_SLOTS_PER_CYCLE,
            issue_slots=self.ISSUE_SLOTS_PER_CYCLE,
            rob=[],
            units_available=ExecUnits(
                A=self.INITIAL_EXEC_UNITS.A,
                L=self.INITIAL_EXEC_UNITS.L,
                S=self.INITIAL_EXEC_UNITS.S,
                M=self.INITIAL_EXEC_UNITS.M,
                D=self.INITIAL_EXEC_UNITS.D,
            ),
        )

    # =========================================================================
    # Section 2.3: State Transition Conditions (GP A.46)
    # =========================================================================

    def _should_terminate(self, state: PipelineState) -> bool:
        """Check if simulation should terminate (ROB empty, no more instructions)."""
        return (
            state.instruction_pc is None
            and (not state.rob or all(e.stage == RobStage.EMPTY for e in state.rob))
        )

    def _can_decode(self, state: PipelineState) -> bool:
        """
        GP-0.7.1-eq:A.46 condition 1

        Check if we can decode the next instruction:
        - Have an instruction to decode
        - ROB not full (< 32 entries)
        - Have enough decode slots
        """
        if state.instruction_pc is None:
            return False
        if len(state.rob) >= self.MAX_ROB_SIZE:
            return False

        opcode = self.sim_code[state.instruction_pc]

        # move_reg only needs 1 decode slot
        if opcode == self.op.move_reg.value:
            return state.decode_slots >= 1

        cost = self.cost_table.get(opcode)
        if cost is None:
            return False

        return cost.decode_fn(state.instruction_pc) <= state.decode_slots

    def _can_issue(self, state: PipelineState) -> bool:
        """
        GP-0.7.1-eq:A.46 condition 2

        Check if we can issue a ready instruction.
        """
        return (
            self._find_ready_instruction(state) is not None
            and state.issue_slots > 0
        )

    # =========================================================================
    # Section 2.4: Decode Transition (GP A.48-A.50)
    # =========================================================================

    def _transition_decode(self, state: PipelineState) -> PipelineState:
        """
        GP-0.7.1-eq:A.48

        Decode transition Xi':
        - If move_reg: use Xi_mov (A.49) - no ROB entry
        - Otherwise: use Xi_decode (A.50) - add ROB entry
        """
        if state.instruction_pc is None:
            return state

        pc = state.instruction_pc
        opcode = self.sim_code[pc]

        if opcode == self.op.move_reg.value:
            return self._decode_move_reg(state, pc)
        else:
            return self._decode_normal(state, pc)

    def _decode_move_reg(self, state: PipelineState, pc: int) -> PipelineState:
        """
        GP-0.7.1-eq:A.49

        move_reg is handled by the frontend without adding a ROB entry.
        It just updates register mappings in existing ROB entries.
        """
        src_regs = self.source_registers(pc)
        dst_regs = self.dest_registers(pc)

        # Update ROB entries based on register overlap
        new_rob = []
        for entry in state.rob:
            if src_regs & entry.dest_regs:
                # Source overlaps with entry's dest: union
                new_dest = entry.dest_regs | dst_regs
            elif dst_regs & entry.dest_regs:
                # Dest overlaps with entry's dest: intersection with src
                new_dest = entry.dest_regs & src_regs
            else:
                new_dest = entry.dest_regs

            new_rob.append(RobEntry(
                stage=entry.stage,
                cycles_left=entry.cycles_left,
                units=entry.units,
                deps=set(entry.deps),
                dest_regs=set(new_dest),
            ))

        return PipelineState(
            instruction_pc=pc + self._skip_bytes(pc),
            cycle_count=state.cycle_count,
            decode_slots=state.decode_slots - 1,
            issue_slots=state.issue_slots,
            rob=new_rob,
            units_available=state.units_available,
        )

    def _decode_normal(self, state: PipelineState, pc: int) -> PipelineState:
        """
        GP-0.7.1-eq:A.50

        Decode a normal instruction and add it to the ROB.
        """
        opcode = self.sim_code[pc]
        cost = self.cost_table.get(opcode)

        if cost is None:
            return self._set_instruction_pc(state, None)

        src_regs = self.source_registers(pc)
        dst_regs = self.dest_registers(pc)

        # Get instruction costs
        latency = cost.latency_fn(pc)      # c_hat
        decode_cost = cost.decode_fn(pc)   # d_hat
        exec_units = cost.units_fn(pc)     # x_hat

        # Compute next PC (None for termination opcodes)
        next_pc = None if opcode in TERMINATION_OPCODES else pc + self._skip_bytes(pc)

        # Find dependencies: ROB entries whose dest_regs overlap with our src_regs
        dependencies = {
            idx for idx, entry in enumerate(state.rob)
            if src_regs & entry.dest_regs
        }

        # Update existing ROB entries: remove our dst_regs from their dest_regs
        new_rob = []
        for entry in state.rob:
            new_rob.append(RobEntry(
                stage=entry.stage,
                cycles_left=entry.cycles_left,
                units=entry.units,
                deps=set(entry.deps),
                dest_regs=entry.dest_regs - dst_regs,
            ))

        # Add new ROB entry
        new_rob.append(RobEntry(
            stage=RobStage.DECODED,
            cycles_left=latency,
            units=exec_units,
            deps=dependencies,
            dest_regs=dst_regs,
        ))

        return PipelineState(
            instruction_pc=next_pc,
            cycle_count=state.cycle_count,
            decode_slots=state.decode_slots - decode_cost,
            issue_slots=state.issue_slots,
            rob=new_rob,
            units_available=state.units_available,
        )

    # =========================================================================
    # Section 2.5: Issue Transition (GP A.51-A.52)
    # =========================================================================

    def _transition_issue(self, state: PipelineState) -> PipelineState:
        """
        GP-0.7.1-eq:A.51

        Issue transition Xi'':
        Move a ready instruction from READY to EXECUTING state.
        """
        ready_idx = self._find_ready_instruction(state)
        if ready_idx is None or state.issue_slots <= 0:
            return state

        entry = state.rob[ready_idx]

        # Update ROB entry to EXECUTING
        new_rob = list(state.rob)
        new_rob[ready_idx] = RobEntry(
            stage=RobStage.EXECUTING,
            cycles_left=entry.cycles_left,
            units=entry.units,
            deps=set(entry.deps),
            dest_regs=set(entry.dest_regs),
        )

        # Consume execution units
        new_units = self._subtract_units(state.units_available, entry.units)

        return PipelineState(
            instruction_pc=state.instruction_pc,
            cycle_count=state.cycle_count,
            decode_slots=state.decode_slots,
            issue_slots=state.issue_slots - 1,
            rob=new_rob,
            units_available=new_units,
        )

    def _find_ready_instruction(self, state: PipelineState) -> Optional[int]:
        """
        GP-0.7.1-eq:A.52

        Find the oldest ROB entry that is ready to issue:
        - Stage is READY (2)
        - Has enough execution units available
        - All dependencies have finished (cycles_left <= 0)

        Returns the ROB index, or None if no instruction is ready.
        """
        for idx, entry in enumerate(state.rob):
            if entry.stage != RobStage.READY:
                continue
            if not self._has_enough_units(entry.units, state.units_available):
                continue
            if any(state.rob[dep].cycles_left > 0 for dep in entry.deps if dep < len(state.rob)):
                continue
            return idx
        return None

    # =========================================================================
    # Section 2.6: Tick Transition (GP A.53)
    # =========================================================================

    def _transition_tick(self, state: PipelineState) -> PipelineState:
        """
        GP-0.7.1-eq:A.53

        Tick transition Xi''':
        Advance the pipeline by one cycle:
        1. Retire completed instructions from the front of ROB
        2. Update stages: DECODED(1)->READY(2), EXECUTING(3)->RETIRED(4) when done
        3. Decrement cycles_left for EXECUTING entries
        4. Return execution units from completed instructions
        5. Increment cycle counter
        6. Reset decode/issue slots for next cycle
        """
        returned_units = ExecUnits()

        # Find how many entries to retire from the front
        retire_count = 0
        for entry in state.rob:
            if entry.stage in (RobStage.EMPTY, RobStage.RETIRED):
                retire_count += 1
            else:
                break

        # Process each ROB entry
        new_rob = []
        for idx, entry in enumerate(state.rob):
            new_stage = entry.stage
            new_cycles = entry.cycles_left
            new_dest_regs = set(entry.dest_regs)

            # Stage transitions
            if idx < retire_count:
                new_stage = RobStage.EMPTY
            elif entry.stage == RobStage.DECODED:
                new_stage = RobStage.READY
            elif entry.stage == RobStage.EXECUTING and entry.cycles_left == 0:
                new_stage = RobStage.RETIRED

            # Decrement cycles for executing instructions
            if entry.stage == RobStage.EXECUTING and entry.cycles_left > 0:
                new_cycles = entry.cycles_left - 1

            # Return units and clear dest_regs when execution completes
            if entry.stage == RobStage.EXECUTING and entry.cycles_left == 1:
                new_dest_regs = set()
                returned_units = self._add_units(returned_units, entry.units)

            # Only keep non-retired entries
            if new_stage != RobStage.EMPTY:
                # Adjust dependency indices for removed entries
                adjusted_deps = {d - retire_count for d in entry.deps if d >= retire_count}
                new_rob.append(RobEntry(
                    stage=new_stage,
                    cycles_left=new_cycles,
                    units=entry.units,
                    deps=adjusted_deps,
                    dest_regs=new_dest_regs,
                ))

        return PipelineState(
            instruction_pc=state.instruction_pc,
            cycle_count=state.cycle_count + 1,
            decode_slots=self.DECODE_SLOTS_PER_CYCLE,
            issue_slots=self.ISSUE_SLOTS_PER_CYCLE,
            rob=new_rob,
            units_available=self._add_units(state.units_available, returned_units),
        )

    # =========================================================================
    # Section 3: Register Analysis (GP A.54)
    # =========================================================================

    def source_registers(self, pc: int) -> Set[int]:
        """
        s_hat(pc): Set of source registers read by instruction at pc.
        Used for RAW dependency detection and P(a,b) calculation.
        """
        opcode, inst_type, _ = self._decode_at(pc)

        match inst_type:
            case InstructionType.none | InstructionType.imm | InstructionType.reg_ext_imm | InstructionType.imm_imm | InstructionType.offset:
                return set()

            case InstructionType.reg_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                if opcode in {self.op.jump_ind.value, self.op.store_u8.value,
                             self.op.store_u16.value, self.op.store_u32.value, self.op.store_u64.value}:
                    return {r_a}
                return set()

            case InstructionType.reg_imm_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                return {r_a}

            case InstructionType.reg_imm_offset:
                if opcode == self.op.load_imm_jump.value:
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                return {r_a}

            case InstructionType.reg_reg:
                r_a = min(12, self.sim_code[pc + 1] // 16)
                return {r_a}

            case InstructionType.reg_reg_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                r_b = min(12, self.sim_code[pc + 1] // 16)
                if opcode in {self.op.store_ind_u8.value, self.op.store_ind_u16.value,
                             self.op.store_ind_u32.value, self.op.store_ind_u64.value}:
                    return {r_a, r_b}
                if opcode in {self.op.load_ind_u8.value, self.op.load_ind_i8.value,
                             self.op.load_ind_u16.value, self.op.load_ind_i16.value,
                             self.op.load_ind_u32.value, self.op.load_ind_i32.value,
                             self.op.load_ind_u64.value}:
                    return {r_b}
                return {r_b}

            case InstructionType.reg_reg_offset:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                r_b = min(12, self.sim_code[pc + 1] // 16)
                return {r_a, r_b}

            case InstructionType.reg_reg_imm_imm:
                r_b = min(12, self.sim_code[pc + 1] // 16)
                return {r_b}

            case InstructionType.reg_reg_reg:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                r_b = min(12, self.sim_code[pc + 1] // 16)
                return {r_a, r_b}

        return set()

    def dest_registers(self, pc: int) -> Set[int]:
        """
        r_hat(pc): Set of destination registers written by instruction at pc.
        Used for WAW/WAR hazard detection.
        """
        opcode, inst_type, _ = self._decode_at(pc)

        match inst_type:
            case InstructionType.none | InstructionType.imm | InstructionType.imm_imm | InstructionType.offset:
                return set()

            case InstructionType.reg_ext_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                return {min(12, self.sim_code[pc + 1] % 16)}

            case InstructionType.reg_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                if opcode in {self.op.jump_ind.value, self.op.store_u8.value,
                             self.op.store_u16.value, self.op.store_u32.value, self.op.store_u64.value}:
                    return set()
                return {min(12, self.sim_code[pc + 1] % 16)}

            case InstructionType.reg_imm_imm:
                return set()

            case InstructionType.reg_imm_offset:
                if pc + 1 >= len(self.sim_code):
                    return set()
                if opcode == self.op.load_imm_jump.value:
                    return {min(12, self.sim_code[pc + 1] % 16)}
                return set()

            case InstructionType.reg_reg:
                if pc + 1 >= len(self.sim_code):
                    return set()
                return {min(12, self.sim_code[pc + 1] % 16)}

            case InstructionType.reg_reg_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                if opcode in {self.op.store_ind_u8.value, self.op.store_ind_u16.value,
                             self.op.store_ind_u32.value, self.op.store_ind_u64.value}:
                    return set()
                return {min(12, self.sim_code[pc + 1] % 16)}

            case InstructionType.reg_reg_offset:
                return set()

            case InstructionType.reg_reg_imm_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                return {min(12, self.sim_code[pc + 1] % 16)}

            case InstructionType.reg_reg_reg:
                if pc + 2 >= len(self.sim_code):
                    return set()
                return {min(12, self.sim_code[pc + 2])}

        return set()

    def decode_cost_P(self, a: int, b: int, pc: int) -> int:
        """
        GP-0.7.1-eq:A.54

        Decode cost helper P(a, b, pc):
        Returns 'a' if source and dest registers overlap, otherwise 'b'.

        This models the decode cost penalty when an instruction's destination
        register is also one of its source registers.
        """
        if self.source_registers(pc) & self.dest_registers(pc):
            return a
        return b

    # =========================================================================
    # Section 4: Cost Parameters (GP A.55-A.56)
    # =========================================================================

    def memory_latency(self) -> int:
        """
        GP-0.7.1-eq:A.55

        Memory access latency based on cache model:
        - L2HIT: 25 cycles
        - L3HIT: 37 cycles
        """
        return 25 if self.mem_model == "L2HIT" else 37

    def branch_penalty(self, pc: int) -> int:
        """
        GP-0.7.1-eq:A.56

        Branch misprediction penalty:
        - 1 cycle if either fallthrough or target is 'unlikely' or 'trap'
        - 20 cycles otherwise
        """
        fallthrough_pc = pc + self._skip_bytes(pc)
        fallthrough_op = self.sim_code[fallthrough_pc] if fallthrough_pc < len(self.sim_code) else None

        opcode = self.sim_code[pc]
        target_pc = self._compute_branch_target(pc, opcode)
        target_op = self.sim_code[target_pc] if target_pc and target_pc < len(self.sim_code) else None

        trap_unlikely = {self.op.unlikely.value, self.op.trap.value}
        if fallthrough_op in trap_unlikely or target_op in trap_unlikely:
            return 1
        return 20

    # =========================================================================
    # Section 5: Instruction Cost Table (GP A.10)
    # =========================================================================

    def _build_instruction_cost_table(self) -> Dict[int, InstructionCost]:
        """Build the instruction cost table per GP Appendix A.10."""

        def const(v: int) -> Callable[[int], int]:
            return lambda pc: v

        def units(A=0, L=0, S=0, M=0, D=0) -> Callable[[int], ExecUnits]:
            return lambda pc: ExecUnits(A=A, L=L, S=S, M=M, D=D)

        table: Dict[int, InstructionCost] = {}

        # --- Arithmetic & Logical (64-bit) ---
        for opc in (self.op._and.value, self.op.xor.value, self.op._or.value,
                    self.op.add_64.value, self.op.sub_64.value):
            table[opc] = InstructionCost(
                latency_fn=const(1),
                decode_fn=lambda pc, a=1, b=2: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Arithmetic & Logical (32-bit) ---
        for opc in (self.op.add_32.value, self.op.sub_32.value):
            table[opc] = InstructionCost(
                latency_fn=const(2),
                decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Immediate variants (64-bit) ---
        for opc in (self.op.and_imm.value, self.op.xor_imm.value, self.op.or_imm.value,
                    self.op.add_imm_64.value, self.op.shlo_r_imm_64.value, self.op.shar_r_imm_64.value,
                    self.op.shlo_l_imm_64.value, self.op.rot_r_64_imm.value, self.op.reverse_bytes.value):
            table[opc] = InstructionCost(
                latency_fn=const(1),
                decode_fn=lambda pc, a=1, b=2: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Immediate variants (32-bit) ---
        for opc in (self.op.add_imm_32.value, self.op.shlo_r_imm_32.value, self.op.shar_r_imm_32.value,
                    self.op.shlo_l_imm_32.value, self.op.rot_r_32_imm.value):
            table[opc] = InstructionCost(
                latency_fn=const(2),
                decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Bit operations ---
        for opc in (self.op.count_set_bits_64.value, self.op.count_set_bits_32.value,
                    self.op.leading_zero_bits_64.value, self.op.leading_zero_bits_32.value,
                    self.op.sign_extend_8.value, self.op.sign_extend_16.value, self.op.zero_extend_16.value):
            table[opc] = InstructionCost(latency_fn=const(1), decode_fn=const(1), units_fn=units(A=1))

        for opc in (self.op.trailing_zero_bits_64.value, self.op.trailing_zero_bits_32.value):
            table[opc] = InstructionCost(latency_fn=const(2), decode_fn=const(1), units_fn=units(A=2))

        # --- Shifts/Rotations (64-bit register) ---
        table[self.op.shlo_l_64.value] = InstructionCost(
            latency_fn=const(1),
            decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
            units_fn=units(A=1)
        )
        table[self.op.shlo_r_64.value] = InstructionCost(latency_fn=const(1), decode_fn=const(3), units_fn=units(A=1))

        for opc in (self.op.shar_r_64.value, self.op.rot_l_64.value, self.op.rot_r_64.value):
            table[opc] = InstructionCost(
                latency_fn=const(1),
                decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Shifts/Rotations (32-bit register) ---
        for opc in (self.op.shlo_l_32.value, self.op.shlo_r_32.value, self.op.shar_r_32.value,
                    self.op.rot_l_32.value, self.op.rot_r_32.value):
            table[opc] = InstructionCost(
                latency_fn=const(2),
                decode_fn=lambda pc, a=3, b=4: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Alt immediate shifts ---
        for opc in (self.op.shlo_l_imm_alt_64.value, self.op.shlo_r_imm_alt_64.value,
                    self.op.shar_r_imm_alt_64.value, self.op.rot_r_64_imm_alt.value):
            table[opc] = InstructionCost(latency_fn=const(1), decode_fn=const(3), units_fn=units(A=1))

        for opc in (self.op.shlo_l_imm_alt_32.value, self.op.shlo_r_imm_alt_32.value,
                    self.op.shar_r_imm_alt_32.value, self.op.rot_r_32_imm_alt.value):
            table[opc] = InstructionCost(latency_fn=const(2), decode_fn=const(4), units_fn=units(A=1))

        # --- Set/Compare ---
        for opc in (self.op.set_lt_u.value, self.op.set_lt_s.value, self.op.set_lt_u_imm.value,
                    self.op.set_lt_s_imm.value, self.op.set_gt_u_imm.value, self.op.set_gt_s_imm.value):
            table[opc] = InstructionCost(latency_fn=const(3), decode_fn=const(3), units_fn=units(A=1))

        # --- Conditional moves ---
        table[self.op.cmov_iz.value] = InstructionCost(latency_fn=const(2), decode_fn=const(2), units_fn=units(A=1))
        table[self.op.cmov_nz.value] = table[self.op.cmov_iz.value]
        table[self.op.cmov_iz_imm.value] = InstructionCost(latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1))
        table[self.op.cmov_nz_imm.value] = table[self.op.cmov_iz_imm.value]

        # --- Min/Max ---
        for opc in (self.op._max.value, self.op.max_u.value, self.op._min.value, self.op.min_u.value):
            table[opc] = InstructionCost(
                latency_fn=const(3),
                decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1)
            )

        # --- Memory loads ---
        for opc in (self.op.load_ind_u8.value, self.op.load_ind_i8.value, self.op.load_ind_u16.value,
                    self.op.load_ind_i16.value, self.op.load_ind_u32.value, self.op.load_ind_i32.value,
                    self.op.load_ind_u64.value, self.op.load_u8.value, self.op.load_i8.value,
                    self.op.load_u16.value, self.op.load_i16.value, self.op.load_u32.value,
                    self.op.load_i32.value, self.op.load_u64.value):
            table[opc] = InstructionCost(
                latency_fn=lambda pc: self.memory_latency(),
                decode_fn=const(1),
                units_fn=units(A=1, L=1)
            )

        # --- Memory stores ---
        for opc in (self.op.store_imm_ind_u8.value, self.op.store_imm_ind_u16.value,
                    self.op.store_imm_ind_u32.value, self.op.store_imm_ind_u64.value,
                    self.op.store_ind_u8.value, self.op.store_ind_u16.value,
                    self.op.store_ind_u32.value, self.op.store_ind_u64.value,
                    self.op.store_imm_u8.value, self.op.store_imm_u16.value,
                    self.op.store_imm_u32.value, self.op.store_imm_u64.value,
                    self.op.store_u8.value, self.op.store_u16.value,
                    self.op.store_u32.value, self.op.store_u64.value):
            table[opc] = InstructionCost(latency_fn=const(25), decode_fn=const(1), units_fn=units(A=1, S=1))

        # --- Branches ---
        for opc in (self.op.branch_eq.value, self.op.branch_ne.value, self.op.branch_lt_u.value,
                    self.op.branch_lt_s.value, self.op.branch_ge_u.value, self.op.branch_ge_s.value,
                    self.op.branch_eq_imm.value, self.op.branch_ne_imm.value, self.op.branch_lt_u_imm.value,
                    self.op.branch_le_u_imm.value, self.op.branch_ge_u_imm.value, self.op.branch_gt_u_imm.value,
                    self.op.branch_lt_s_imm.value, self.op.branch_le_s_imm.value, self.op.branch_ge_s_imm.value,
                    self.op.branch_gt_s_imm.value):
            table[opc] = InstructionCost(
                latency_fn=lambda pc: self.branch_penalty(pc),
                decode_fn=const(1),
                units_fn=units(A=1)
            )

        # --- Division/Modulo ---
        for opc in (self.op.div_u_32.value, self.op.div_s_32.value, self.op.rem_u_32.value,
                    self.op.rem_s_32.value, self.op.div_u_64.value, self.op.div_s_64.value,
                    self.op.rem_u_64.value, self.op.rem_s_64.value):
            table[opc] = InstructionCost(latency_fn=const(60), decode_fn=const(4), units_fn=units(A=1, D=1))

        # --- Boolean inversions ---
        for opc in (self.op.and_inv.value, self.op.or_inv.value):
            table[opc] = InstructionCost(latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1))
        table[self.op.xnor.value] = InstructionCost(
            latency_fn=const(2),
            decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
            units_fn=units(A=1)
        )

        # --- Negate/add ---
        table[self.op.neg_add_imm_64.value] = InstructionCost(latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1))
        table[self.op.neg_add_imm_32.value] = InstructionCost(latency_fn=const(3), decode_fn=const(4), units_fn=units(A=1))

        # --- Immediates ---
        table[self.op.load_imm.value] = InstructionCost(latency_fn=const(1), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_64.value] = InstructionCost(latency_fn=const(1), decode_fn=const(2), units_fn=units())

        # --- Multiplication ---
        for opc in (self.op.mul_64.value, self.op.mul_imm_64.value):
            table[opc] = InstructionCost(
                latency_fn=const(3),
                decode_fn=lambda pc, a=1, b=2: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1, M=1)
            )
        for opc in (self.op.mul_32.value, self.op.mul_imm_32.value):
            table[opc] = InstructionCost(
                latency_fn=const(4),
                decode_fn=lambda pc, a=2, b=3: self.decode_cost_P(a, b, pc),
                units_fn=units(A=1, M=1)
            )
        for opc in (self.op.mul_upper_s_s.value, self.op.mul_upper_u_u.value, self.op.mul_upper_s_u.value):
            lat = 6 if opc == self.op.mul_upper_s_u.value else 4
            table[opc] = InstructionCost(latency_fn=const(lat), decode_fn=const(4), units_fn=units(A=1, M=1))

        # --- Control flow & misc ---
        table[self.op.trap.value] = InstructionCost(latency_fn=const(2), decode_fn=const(1), units_fn=units())
        table[self.op.fallthrough.value] = InstructionCost(latency_fn=const(2), decode_fn=const(1), units_fn=units())
        table[self.op.unlikely.value] = InstructionCost(latency_fn=const(40), decode_fn=const(1), units_fn=units())
        table[self.op.jump.value] = InstructionCost(latency_fn=const(15), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_jump.value] = InstructionCost(latency_fn=const(15), decode_fn=const(1), units_fn=units())
        table[self.op.jump_ind.value] = InstructionCost(latency_fn=const(22), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_jump_ind.value] = InstructionCost(latency_fn=const(22), decode_fn=const(1), units_fn=units())
        table[self.op.ecalli.value] = InstructionCost(latency_fn=const(100), decode_fn=const(4), units_fn=units(A=1))
        table[self.op.sbrk.value] = InstructionCost(latency_fn=const(100), decode_fn=const(4), units_fn=units(A=1))

        return table

    # =========================================================================
    # Section 6: Helper Functions
    # =========================================================================

    def _skip_bytes(self, pc: int) -> int:
        """Get the number of bytes to skip to reach the next instruction."""
        inst_index = self.inst_pos_sim.get(pc, 0)
        if inst_index >= len(self.inst_arg_len_sim):
            return 1
        return 1 + self.inst_arg_len_sim[inst_index]

    def _decode_at(self, pc: int) -> Tuple[int, InstructionType, int]:
        """Decode instruction at pc, returning (opcode, type, index)."""
        opcode = self.sim_code[pc]
        inst_type = self.opcode_scheme.get(opcode, InstructionType.none)
        inst_index = self.inst_pos_sim.get(pc, 0)
        return opcode, inst_type, inst_index

    def _compute_branch_target(self, pc: int, opcode: int) -> Optional[int]:
        """Compute static branch target PC, or None for non-branches."""
        inst_type = self.opcode_scheme.get(opcode)
        inst_index = self.inst_pos_sim.get(pc, 0)
        if inst_index >= len(self.inst_arg_len_sim):
            return None

        if inst_type == InstructionType.reg_reg_offset:
            l_x = min(4, max(0, self.inst_arg_len_sim[inst_index] - 1))
            offset = pvm_Z(read_uint(self.sim_code, pc + 2, l_x), l_x)
            return pc + offset

        if inst_type == InstructionType.reg_imm_offset:
            l_x = min(4, (self.sim_code[pc + 1] // 16) % 8)
            l_y = min(4, max(0, self.inst_arg_len_sim[inst_index] - l_x - 1))
            offset = pvm_Z(read_uint(self.sim_code, pc + 2 + l_x, l_y), l_y)
            return pc + offset

        return None

    def _set_instruction_pc(self, state: PipelineState, pc: Optional[int]) -> PipelineState:
        """Create new state with updated instruction_pc."""
        return PipelineState(
            instruction_pc=pc,
            cycle_count=state.cycle_count,
            decode_slots=state.decode_slots,
            issue_slots=state.issue_slots,
            rob=state.rob,
            units_available=state.units_available,
        )

    def _add_units(self, a: ExecUnits, b: ExecUnits) -> ExecUnits:
        """Element-wise addition of execution units."""
        return ExecUnits(A=a.A + b.A, L=a.L + b.L, S=a.S + b.S, M=a.M + b.M, D=a.D + b.D)

    def _subtract_units(self, a: ExecUnits, b: ExecUnits) -> ExecUnits:
        """Element-wise subtraction of execution units."""
        return ExecUnits(A=a.A - b.A, L=a.L - b.L, S=a.S - b.S, M=a.M - b.M, D=a.D - b.D)

    def _has_enough_units(self, required: ExecUnits, available: ExecUnits) -> bool:
        """Check if required <= available for all unit types."""
        return (required.A <= available.A and required.L <= available.L and
                required.S <= available.S and required.M <= available.M and required.D <= available.D)


    # def s_hat(self, pc: int) -> Set[int]:
    #     """Alias for source_registers (legacy API)."""
    #     return self.source_registers(pc)
    #
    # def r_hat(self, pc: int) -> Set[int]:
    #     """Alias for dest_registers (legacy API)."""
    #     return self.dest_registers(pc)
    #
    # def P(self, a: int, b: int, pc: int) -> int:
    #     """Alias for decode_cost_P (legacy API)."""
    #     return self.decode_cost_P(a, b, pc)
    #
    # def skip_bytes(self, pc: int) -> int:
    #     """Alias for _skip_bytes (legacy API)."""
    #     return self._skip_bytes(pc)
    #
    # def decode_instruction(self, pc: int) -> Tuple[int, InstructionType, int]:
    #     """Alias for _decode_at (legacy API)."""
    #     return self._decode_at(pc)
