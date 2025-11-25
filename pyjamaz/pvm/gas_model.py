from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR
from pyjamaz.pvm.constants import InstructionType, Opcode as op, OpcodeNames, OpcodeScheme, TERMINATION_OPCODES
from pyjamaz.pvm.interpreters.graypaper.defs import pvm_Z, read_uint


@dataclass
class ExecUnits:
    A: int = 0
    L: int = 0
    S: int = 0
    M: int = 0
    D: int = 0


@dataclass
class RobEntry:
    stage: int
    cycles_left: int
    units: ExecUnits
    deps: Set[int]
    dest_regs: Set[int]


@dataclass
class GasState:
    # GP-0.7.1-eq:A.45
    i: Optional[int]
    c_cycles: int
    n_rob: int
    d_slots: int
    e_slots: int
    rob: List[RobEntry]
    units_free: ExecUnits


class GasModel:
    """
    Implements the graypaper gas model (Appendix A.9/A.10).
    """

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

        # Extend with a synthetic trap to gracefully terminate when running past
        # the end of the code blob during simulation.
        self.sim_code = bytearray(self.code)
        self.inst_arg_len_sim = list(self.inst_arg_len)
        self.inst_pos_sim = dict(self.inst_pos)
        self.inst_pos_sim[len(self.code)] = len(self.inst_arg_len_sim)
        self.inst_arg_len_sim.append(0)
        self.sim_code.append(self.op.trap.value)

        self.cost_table = self._build_cost_table()

    # ----- Helpers ------------------------------------------------------------------
    def skip_bytes(self, pc: int) -> int:
        inst_index = self.inst_pos_sim.get(pc, 0)
        if inst_index >= len(self.inst_arg_len_sim):
            return 1
        return 1 + self.inst_arg_len_sim[inst_index]

    def decode_instruction(self, pc: int) -> Tuple[int, InstructionType, int]:
        opcode = self.sim_code[pc]
        inst_type = self.opcode_scheme.get(opcode, InstructionType.none)
        inst_index = self.inst_pos_sim.get(pc, 0)
        return opcode, inst_type, inst_index

    def s_hat(self, pc: int) -> Set[int]:
        opcode, inst_type, inst_index = self.decode_instruction(pc)

        match inst_type:
            case InstructionType.none:
                return set()

            case InstructionType.imm:
                return set()

            case InstructionType.reg_ext_imm:
                return set()

            case InstructionType.imm_imm:
                return set()

            case InstructionType.offset:
                return set()

            case InstructionType.reg_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                if opcode == self.op.jump_ind.value:
                    return {r_a}
                if opcode in {
                    self.op.store_u8.value,
                    self.op.store_u16.value,
                    self.op.store_u32.value,
                    self.op.store_u64.value,
                }:
                    return {r_a}
                return set()

            case InstructionType.reg_imm_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                return {r_a}

            case InstructionType.reg_imm_offset:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                # load_imm_jump writes r_a but does not read it
                if opcode == self.op.load_imm_jump.value:
                    return set()
                return {r_a}

            case InstructionType.reg_reg:
                r_a = min(12, self.sim_code[pc + 1] // 16)
                if opcode == self.op.move_reg.value:
                    return {r_a}
                return {r_a}

            case InstructionType.reg_reg_imm:
                r_a = min(12, self.sim_code[pc + 1] % 16)
                r_b = min(12, self.sim_code[pc + 1] // 16)
                if opcode in {
                    self.op.store_ind_u8.value,
                    self.op.store_ind_u16.value,
                    self.op.store_ind_u32.value,
                    self.op.store_ind_u64.value,
                }:
                    return {r_a, r_b}
                if opcode in {
                    self.op.load_ind_u8.value,
                    self.op.load_ind_i8.value,
                    self.op.load_ind_u16.value,
                    self.op.load_ind_i16.value,
                    self.op.load_ind_u32.value,
                    self.op.load_ind_i32.value,
                    self.op.load_ind_u64.value,
                }:
                    return {r_b}

                # Regular immediates read r_b
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

    def r_hat(self, pc: int) -> Set[int]:
        opcode, inst_type, inst_index = self.decode_instruction(pc)

        match inst_type:
            case InstructionType.none:
                return set()

            case InstructionType.imm:
                return set()

            case InstructionType.reg_ext_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                return {r_a}

            case InstructionType.imm_imm:
                return set()

            case InstructionType.offset:
                return set()

            case InstructionType.reg_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                if opcode in {
                    self.op.jump_ind.value,
                    self.op.store_u8.value,
                    self.op.store_u16.value,
                    self.op.store_u32.value,
                    self.op.store_u64.value,
                }:
                    return set()
                return {r_a}

            case InstructionType.reg_imm_imm:
                return set()

            case InstructionType.reg_imm_offset:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                if opcode == self.op.load_imm_jump.value:
                    return {r_a}
                return set()

            case InstructionType.reg_reg:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_d = min(12, self.sim_code[pc + 1] % 16)
                if opcode == self.op.move_reg.value:
                    return {r_d}
                return {r_d}

            case InstructionType.reg_reg_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                if opcode in {
                    self.op.store_ind_u8.value,
                    self.op.store_ind_u16.value,
                    self.op.store_ind_u32.value,
                    self.op.store_ind_u64.value,
                }:
                    return set()
                return {r_a}

            case InstructionType.reg_reg_offset:
                return set()

            case InstructionType.reg_reg_imm_imm:
                if pc + 1 >= len(self.sim_code):
                    return set()
                r_a = min(12, self.sim_code[pc + 1] % 16)
                return {r_a}

            case InstructionType.reg_reg_reg:
                if pc + 2 >= len(self.sim_code):
                    return set()
                r_d = min(12, self.sim_code[pc + 2])
                return {r_d}

        return set()

    # GP-0.7.1-eq:A.54
    def P(self, a: int, b: int, pc: int) -> int:
        return a if self.s_hat(pc) & self.r_hat(pc) else b

    def memory_latency(self) -> int:
        # GP-0.7.1-eq:A.55
        return 25 if self.mem_model == "L2HIT" else 37

    def _static_branch_target(self, pc: int, opcode: int) -> Optional[int]:
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

    # GP-0.7.1-eq:A.56
    def branch_penalty(self, pc: int) -> int:
        inst_index = self.inst_pos_sim.get(pc, 0)
        fallthrough_pc = pc + self.skip_bytes(pc)
        fallthrough_opcode = self.sim_code[fallthrough_pc] if fallthrough_pc < len(self.sim_code) else None

        opcode = self.sim_code[pc]
        target_pc = self._static_branch_target(pc, opcode)
        target_opcode = self.sim_code[target_pc] if target_pc is not None and target_pc < len(self.sim_code) else None

        if fallthrough_opcode in (self.op.unlikely.value, self.op.trap.value) or target_opcode in (
            self.op.unlikely.value,
            self.op.trap.value,
        ):
            return 1
        return 20


    @dataclass
    class InstrCost:
        latency_fn: Callable[[int], int]
        decode_fn: Callable[[int], int]
        units_fn: Callable[[int], ExecUnits]

    def _build_cost_table(self) -> Dict[int, "GasModel.InstrCost"]:
        def const(v: int) -> Callable[[int], int]:
            return lambda pc: v

        def units(A=0, L=0, S=0, M=0, D=0) -> Callable[[int], ExecUnits]:
            return lambda pc: ExecUnits(A=A, L=L, S=S, M=M, D=D)

        table: Dict[int, GasModel.InstrCost] = {}

        # Arithmetic & logical operations
        for opcode in (self.op._and.value, self.op.xor.value, self.op._or.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(1), decode_fn=lambda pc, a=1, b=2: self.P(a, b, pc), units_fn=units(A=1)
            )
        for opcode in (self.op.add_64.value, self.op.sub_64.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(1), decode_fn=lambda pc, a=1, b=2: self.P(a, b, pc), units_fn=units(A=1)
            )
        for opcode in (self.op.add_32.value, self.op.sub_32.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(2), decode_fn=lambda pc, a=2, b=3: self.P(a, b, pc), units_fn=units(A=1)
            )
        for opcode in (self.op.and_imm.value, self.op.xor_imm.value, self.op.or_imm.value, self.op.add_imm_64.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(1), decode_fn=lambda pc, a=1, b=2: self.P(a, b, pc), units_fn=units(A=1)
            )
        table[self.op.shlo_r_imm_64.value] = self.InstrCost(
            latency_fn=const(1), decode_fn=lambda pc, a=1, b=2: self.P(a, b, pc), units_fn=units(A=1)
        )
        table[self.op.shar_r_imm_64.value] = table[self.op.shlo_r_imm_64.value]
        table[self.op.shlo_l_imm_64.value] = table[self.op.shlo_r_imm_64.value]
        table[self.op.rot_r_64_imm.value] = table[self.op.shlo_r_imm_64.value]
        table[self.op.reverse_bytes.value] = table[self.op.shlo_r_imm_64.value]

        # 32-bit immediates with higher decode cost
        for opcode in (
            self.op.add_imm_32.value,
            self.op.shlo_r_imm_32.value,
            self.op.shar_r_imm_32.value,
            self.op.shlo_l_imm_32.value,
            self.op.rot_r_32_imm.value,
        ):
            table[opcode] = self.InstrCost(
                latency_fn=const(2), decode_fn=lambda pc, a=2, b=3: self.P(a, b, pc), units_fn=units(A=1)
            )

        # Bit operations
        for opcode in (
            self.op.count_set_bits_64.value,
            self.op.count_set_bits_32.value,
            self.op.leading_zero_bits_64.value,
            self.op.leading_zero_bits_32.value,
            self.op.sign_extend_8.value,
            self.op.sign_extend_16.value,
            self.op.zero_extend_16.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(1), decode_fn=const(1), units_fn=units(A=1))
        for opcode in (self.op.trailing_zero_bits_64.value, self.op.trailing_zero_bits_32.value):
            table[opcode] = self.InstrCost(latency_fn=const(2), decode_fn=const(1), units_fn=units(A=2))

        # 64-bit shifts/rotations
        for opcode in (
            self.op.shlo_l_64.value,
            self.op.shlo_r_64.value,
            self.op.shar_r_64.value,
            self.op.rot_l_64.value,
            self.op.rot_r_64.value,
        ):
            table[opcode] = self.InstrCost(
                latency_fn=const(1), decode_fn=lambda pc, a=3, b=4: self.P(a, b, pc), units_fn=units(A=1)
            )

        # 32-bit shifts/rotations (register)
        for opcode in (
            self.op.shlo_l_32.value,
            self.op.shlo_r_32.value,
            self.op.shar_r_32.value,
            self.op.rot_l_32.value,
            self.op.rot_r_32.value,
        ):
            table[opcode] = self.InstrCost(
                latency_fn=const(2), decode_fn=lambda pc, a=3, b=4: self.P(a, b, pc), units_fn=units(A=1)
            )

        # Alt immediates
        for opcode in (
            self.op.shlo_l_imm_alt_64.value,
            self.op.shlo_r_imm_alt_64.value,
            self.op.shar_r_imm_alt_64.value,
            self.op.rot_r_64_imm_alt.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(1), decode_fn=const(3), units_fn=units(A=1))
        for opcode in (
            self.op.shlo_l_imm_alt_32.value,
            self.op.shlo_r_imm_alt_32.value,
            self.op.shar_r_imm_alt_32.value,
            self.op.rot_r_32_imm_alt.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(2), decode_fn=const(4), units_fn=units(A=1))

        # Set/compare ops
        for opcode in (
            self.op.set_lt_u.value,
            self.op.set_lt_s.value,
            self.op.set_lt_u_imm.value,
            self.op.set_lt_s_imm.value,
            self.op.set_gt_u_imm.value,
            self.op.set_gt_s_imm.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(3), decode_fn=const(3), units_fn=units(A=1))

        # Conditional moves
        table[self.op.cmov_iz.value] = self.InstrCost(latency_fn=const(2), decode_fn=const(2), units_fn=units(A=1))
        table[self.op.cmov_nz.value] = table[self.op.cmov_iz.value]
        table[self.op.cmov_iz_imm.value] = self.InstrCost(latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1))
        table[self.op.cmov_nz_imm.value] = table[self.op.cmov_iz_imm.value]

        # Min/Max
        for opcode in (
            self.op._max.value,
            self.op.max_u.value,
            self.op._min.value,
            self.op.min_u.value,
        ):
            table[opcode] = self.InstrCost(
                latency_fn=const(3), decode_fn=lambda pc, a=2, b=3: self.P(a, b, pc), units_fn=units(A=1)
            )

        # Memory loads
        load_opcodes = [
            self.op.load_ind_u8.value,
            self.op.load_ind_i8.value,
            self.op.load_ind_u16.value,
            self.op.load_ind_i16.value,
            self.op.load_ind_u32.value,
            self.op.load_ind_i32.value,
            self.op.load_ind_u64.value,
            self.op.load_u8.value,
            self.op.load_i8.value,
            self.op.load_u16.value,
            self.op.load_i16.value,
            self.op.load_u32.value,
            self.op.load_i32.value,
            self.op.load_u64.value,
        ]
        for opcode in load_opcodes:
            table[opcode] = self.InstrCost(
                latency_fn=lambda pc: self.memory_latency(), decode_fn=const(1), units_fn=units(A=1, L=1)
            )

        # Stores
        store_opcodes = [
            self.op.store_imm_ind_u8.value,
            self.op.store_imm_ind_u16.value,
            self.op.store_imm_ind_u32.value,
            self.op.store_imm_ind_u64.value,
            self.op.store_ind_u8.value,
            self.op.store_ind_u16.value,
            self.op.store_ind_u32.value,
            self.op.store_ind_u64.value,
            self.op.store_imm_u8.value,
            self.op.store_imm_u16.value,
            self.op.store_imm_u32.value,
            self.op.store_imm_u64.value,
            self.op.store_u8.value,
            self.op.store_u16.value,
            self.op.store_u32.value,
            self.op.store_u64.value,
        ]
        for opcode in store_opcodes:
            table[opcode] = self.InstrCost(
                latency_fn=const(25), decode_fn=const(1), units_fn=units(A=1, S=1)
            )

        # Branches
        branch_opcodes = [
            self.op.branch_eq.value,
            self.op.branch_ne.value,
            self.op.branch_lt_u.value,
            self.op.branch_lt_s.value,
            self.op.branch_ge_u.value,
            self.op.branch_ge_s.value,
            self.op.branch_eq_imm.value,
            self.op.branch_ne_imm.value,
            self.op.branch_lt_u_imm.value,
            self.op.branch_le_u_imm.value,
            self.op.branch_ge_u_imm.value,
            self.op.branch_gt_u_imm.value,
            self.op.branch_lt_s_imm.value,
            self.op.branch_le_s_imm.value,
            self.op.branch_ge_s_imm.value,
            self.op.branch_gt_s_imm.value,
        ]
        for opcode in branch_opcodes:
            table[opcode] = self.InstrCost(
                latency_fn=lambda pc: self.branch_penalty(pc), decode_fn=const(1), units_fn=units(A=1)
            )

        # Division/Modulo
        for opcode in (
            self.op.div_u_32.value,
            self.op.div_s_32.value,
            self.op.rem_u_32.value,
            self.op.rem_s_32.value,
            self.op.div_u_64.value,
            self.op.div_s_64.value,
            self.op.rem_u_64.value,
            self.op.rem_s_64.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(60), decode_fn=const(4), units_fn=units(A=1, D=1))

        # Boolean inversions
        for opcode in (self.op.and_inv.value, self.op.or_inv.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1)
            )
        table[self.op.xnor.value] = self.InstrCost(
            latency_fn=const(2), decode_fn=lambda pc, a=2, b=3: self.P(a, b, pc), units_fn=units(A=1)
        )

        # Negate/add
        table[self.op.neg_add_imm_64.value] = self.InstrCost(latency_fn=const(2), decode_fn=const(3), units_fn=units(A=1))
        table[self.op.neg_add_imm_32.value] = self.InstrCost(latency_fn=const(3), decode_fn=const(4), units_fn=units(A=1))

        # Immediates
        table[self.op.load_imm.value] = self.InstrCost(latency_fn=const(1), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_64.value] = self.InstrCost(latency_fn=const(1), decode_fn=const(2), units_fn=units())

        # Multiplication
        for opcode in (self.op.mul_64.value, self.op.mul_imm_64.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(3), decode_fn=lambda pc, a=1, b=2: self.P(a, b, pc), units_fn=units(A=1, M=1)
            )
        for opcode in (self.op.mul_32.value, self.op.mul_imm_32.value):
            table[opcode] = self.InstrCost(
                latency_fn=const(4), decode_fn=lambda pc, a=2, b=3: self.P(a, b, pc), units_fn=units(A=1, M=1)
            )
        for opcode in (
            self.op.mul_upper_s_s.value,
            self.op.mul_upper_u_u.value,
            self.op.mul_upper_s_u.value,
        ):
            table[opcode] = self.InstrCost(latency_fn=const(4 if opcode != self.op.mul_upper_s_u.value else 6), decode_fn=const(4), units_fn=units(A=1, M=1))

        # Control flow and misc
        table[self.op.trap.value] = self.InstrCost(latency_fn=const(2), decode_fn=const(1), units_fn=units())
        table[self.op.fallthrough.value] = self.InstrCost(latency_fn=const(2), decode_fn=const(1), units_fn=units())
        table[self.op.unlikely.value] = self.InstrCost(latency_fn=const(40), decode_fn=const(1), units_fn=units())
        table[self.op.jump.value] = self.InstrCost(latency_fn=const(15), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_jump.value] = self.InstrCost(latency_fn=const(15), decode_fn=const(1), units_fn=units())
        table[self.op.jump_ind.value] = self.InstrCost(latency_fn=const(22), decode_fn=const(1), units_fn=units())
        table[self.op.load_imm_jump_ind.value] = self.InstrCost(latency_fn=const(22), decode_fn=const(1), units_fn=units())
        table[self.op.ecalli.value] = self.InstrCost(latency_fn=const(100), decode_fn=const(4), units_fn=units(A=1))
        table[self.op.sbrk.value] = self.InstrCost(latency_fn=const(100), decode_fn=const(4), units_fn=units(A=1))

        return table

    # Pipeline transitions
    def _units_add(self, a: ExecUnits, b: ExecUnits) -> ExecUnits:
        return ExecUnits(A=a.A + b.A, L=a.L + b.L, S=a.S + b.S, M=a.M + b.M, D=a.D + b.D)

    def _units_sub(self, a: ExecUnits, b: ExecUnits) -> ExecUnits:
        return ExecUnits(A=a.A - b.A, L=a.L - b.L, S=a.S - b.S, M=a.M - b.M, D=a.D - b.D)

    def _units_leq(self, a: ExecUnits, b: ExecUnits) -> bool:
        return a.A <= b.A and a.L <= b.L and a.S <= b.S and a.M <= b.M and a.D <= b.D

    def _initial_state(self, start_pc: int) -> GasState:
        # GP-0.7.1-eq:A.45
        return GasState(
            i=start_pc,
            c_cycles=0,
            n_rob=0,
            d_slots=4,
            e_slots=5,
            rob=[],
            units_free=ExecUnits(A=4, L=4, S=4, M=1, D=1),
        )

    def _ready_index(self, state: GasState) -> Optional[int]:
        # GP-0.7.1-eq:A.52
        for idx, entry in enumerate(state.rob):
            if entry.stage != 2:
                continue
            if not self._units_leq(entry.units, state.units_free):
                continue
            if any(state.rob[k].cycles_left > 0 for k in entry.deps):
                continue
            return idx
        return None

    def _step_decode(self, state: GasState) -> GasState:
        if state.i is None:
            return state
        pc = state.i
        opcode, inst_type, _ = self.decode_instruction(pc)
        cost = self.cost_table.get(opcode)

        # Special-case move_reg: GP-0.7.1-eq:A.49
        if opcode == self.op.move_reg.value:
            src = self.s_hat(pc)
            dst = self.r_hat(pc)
            # Update existing ROB write sets according to overlaps
            new_rob: List[RobEntry] = []
            for entry in state.rob:
                if src & entry.dest_regs:
                    dest_regs = entry.dest_regs | dst
                elif dst & entry.dest_regs:
                    dest_regs = entry.dest_regs & src
                else:
                    dest_regs = entry.dest_regs
                new_rob.append(
                    RobEntry(
                        stage=entry.stage,
                        cycles_left=entry.cycles_left,
                        units=entry.units,
                        deps=set(entry.deps),
                        dest_regs=set(dest_regs),
                    )
                )

            return GasState(
                i=pc + self.skip_bytes(pc),
                c_cycles=state.c_cycles,
                n_rob=state.n_rob,
                d_slots=state.d_slots - 1,
                e_slots=state.e_slots,
                rob=new_rob,
                units_free=state.units_free,
            )

        if cost is None:
            return GasState(
                i=None,
                c_cycles=state.c_cycles,
                n_rob=state.n_rob,
                d_slots=state.d_slots,
                e_slots=state.e_slots,
                rob=state.rob,
                units_free=state.units_free,
            )

        src = self.s_hat(pc)
        dst = self.r_hat(pc)

        c_hat = cost.latency_fn(pc)
        d_hat = cost.decode_fn(pc)
        x_hat = cost.units_fn(pc)

        # Advance instruction pointer unless we hit termination (handled by main loop).
        next_i = None if opcode in TERMINATION_OPCODES else pc + self.skip_bytes(pc)
        new_d_slots = state.d_slots - d_hat
        new_n_rob = state.n_rob + 1

        # Compute dependencies based on overlapping register writes
        parents = {idx for idx, entry in enumerate(state.rob) if src & entry.dest_regs}

        # Remove new destinations from older entries
        new_rob = []
        for entry in state.rob:
            new_rob.append(
                RobEntry(
                    stage=entry.stage,
                    cycles_left=entry.cycles_left,
                    units=entry.units,
                    deps=set(entry.deps),
                    dest_regs=entry.dest_regs - dst,
                )
            )

        new_rob.append(
            RobEntry(stage=1, cycles_left=c_hat, units=x_hat, deps=parents, dest_regs=dst)
        )

        return GasState(
            i=next_i,
            c_cycles=state.c_cycles,
            n_rob=new_n_rob,
            d_slots=new_d_slots,
            e_slots=state.e_slots,
            rob=new_rob,
            units_free=state.units_free,
        )

    def _step_issue(self, state: GasState) -> GasState:
        ready_idx = self._ready_index(state)
        if ready_idx is None or state.e_slots <= 0:
            return state

        new_rob = list(state.rob)
        entry = new_rob[ready_idx]
        new_rob[ready_idx] = RobEntry(
            stage=3,
            cycles_left=entry.cycles_left,
            units=entry.units,
            deps=set(entry.deps),
            dest_regs=set(entry.dest_regs),
        )

        new_units = self._units_sub(state.units_free, entry.units)
        return GasState(
            i=state.i,
            c_cycles=state.c_cycles,
            n_rob=state.n_rob,
            d_slots=state.d_slots,
            e_slots=state.e_slots - 1,
            rob=new_rob,
            units_free=new_units,
        )

    def _step_tick(self, state: GasState) -> GasState:
        new_rob: List[RobEntry] = []
        returned_units = ExecUnits()

        # Determine which slots become empty
        empty_up_to = -1
        for idx, entry in enumerate(state.rob):
            if entry.stage in (0, 4):
                empty_up_to = idx
            else:
                break

        for idx, entry in enumerate(state.rob):
            stage = entry.stage
            cycles_left = entry.cycles_left
            dest_regs = set(entry.dest_regs)

            if idx <= empty_up_to:
                stage = 0
            elif entry.stage == 1:
                stage = 2
            elif entry.stage == 3 and entry.cycles_left == 0:
                stage = 4

            if entry.stage == 3 and entry.cycles_left > 0:
                cycles_left = entry.cycles_left - 1

            if entry.stage == 3 and entry.cycles_left == 1:
                dest_regs = set()
                returned_units = self._units_add(returned_units, entry.units)

            new_rob.append(
                RobEntry(stage=stage, cycles_left=cycles_left, units=entry.units, deps=set(entry.deps), dest_regs=dest_regs)
            )

        new_units = self._units_add(state.units_free, returned_units)
        return GasState(
            i=state.i,
            c_cycles=state.c_cycles + 1,
            n_rob=state.n_rob,
            d_slots=4,
            e_slots=5,
            rob=new_rob,
            units_free=new_units,
        )


    def block_cost(self, block_start_pc: int) -> int:
        state = self._initial_state(block_start_pc)
        steps = 0
        max_steps = 100000

        while steps < max_steps:
            # Terminate when instruction pointer is None and ROB is empty
            if state.i is None and all(entry.stage == 0 for entry in state.rob):
                break

            if state.i is not None and state.i >= len(self.sim_code):
                state = GasState(
                    i=None,
                    c_cycles=state.c_cycles,
                    n_rob=state.n_rob,
                    d_slots=state.d_slots,
                    e_slots=state.e_slots,
                    rob=state.rob,
                    units_free=state.units_free,
                )

            opcode = self.sim_code[state.i] if state.i is not None else None
            cost_entry = self.cost_table.get(opcode) if opcode is not None else None
            can_decode = (
                state.i is not None
                and len(state.rob) < 32
                and (
                    (opcode == self.op.move_reg.value and state.d_slots >= 1)
                    or (cost_entry is not None and cost_entry.decode_fn(state.i) <= state.d_slots)
                )
            )
            ready_idx = self._ready_index(state)
            can_issue = ready_idx is not None and state.e_slots > 0

            if steps == 0 or can_decode:
                state = self._step_decode(state)
            elif can_issue:
                state = self._step_issue(state)
            elif state.rob or state.i is not None:
                state = self._step_tick(state)
            else:
                break

            steps += 1

        # GP-0.7.1-eq:A.47
        return max(state.c_cycles - 3, 1)
