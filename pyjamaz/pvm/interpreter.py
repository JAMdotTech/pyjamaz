from types import MethodType

import numpy as np
import numpy.typing as npt

from typing import List, Dict

from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
from .types import PVMProgram, PVMMemory

from .utils import (
    pvm_Z,
    pvm_X,
    pvm_Z_inv,
    count_trailing_zeroes,
    count_leading_zeroes,
    reverse_bytes,
    rori64,
    rori32,
    riscv_div,
    pvm_smod,
    pvm_rtz_div,
    roli32,
    roli64,
    read_uint
)

from .constants import (
    Opcode as op,
    OpcodeScheme,
    InstructionType,
    ExitReason,
    MemOps, OpcodeNames, ExitCondition,
)

from ..graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR


class PVMInterpreter:

    def __init__(self, program: PVMProgram, logger=None):
        self.reg = np.zeros(13, dtype=np.uint64)
        self.pc:np.uint32 = np.uint32(0)
        self.opcode:int = 0
        self.skip_len: int = 0
        self.gas:np.uint64 = np.uint64(0)
        self.code:npt.NDArray[np.uint8] = np.array(1, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(0)
        self.jump_table = []

        self.inst_bitmask: List[bool] = []
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []

        self.mem:PVMMemory = None
        self.status:int = ExitReason.none.value
        self.exit_value:int = None

        self.reset(program)

        self.log = None
        if logger:
            self.program = program
            self.log = logger
            self.log._pvm = self
            for opcode_name in OpcodeNames.values():
                if opcode_name not in logger.log_opcodes:
                    logger.log_opcodes[opcode_name] = 0


    def create_instruction_lookup(self):
        """
        Create lookups for byte_pos -> instruction_nr and instruction_nr->instruction_length
        """
        self.inst_pos = {0: 0}
        self.inst_arg_len = []

        inst_nr = 0
        inst_bitmask = self.inst_bitmask
        inst_bitmask_idx = 1

        # Note: In the exceptional case we only have 1 instruction (trap or fallthrough), we add it manually and be done
        if len(inst_bitmask) == 1:
            self.inst_arg_len.append(0)
            return

        # Parse instruction bitmask and create a opcode offset and instruction length lookup
        while inst_bitmask_idx < len(inst_bitmask):
            inst_args = 0

            is_opcode = False

            while not is_opcode:

                is_opcode = inst_bitmask[inst_bitmask_idx]
                if not is_opcode:
                    inst_args += 1

                inst_bitmask_idx += 1

                if inst_bitmask_idx > len(inst_bitmask) - 1:
                    is_opcode = True

            # GP-0.6.2-eq:A.19 (l)
            self.inst_arg_len.append(inst_args)
            inst_nr += 1
            self.inst_pos[inst_bitmask_idx - 1] = inst_nr


    def branch(self, b:int, C:bool):
        if C:
            inst_pos = self.pc + b
            if inst_pos not in self.inst_pos:
                #self.status = ExitCondition.panic.value
                raise PanicError(f"Invalid branch instruction: C={C} b={b} inst_pos={inst_pos}")
            else:
                self.skip_len = inst_pos  - self.pc


    def reset(self, program: PVMProgram):
        self.pc = np.uint32(0)
        self.gas = np.uint64(0)

        self.code:npt.NDArray[np.uint8] = np.array(program.code.code, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(len(self.code))
        self.mem = program.memory
        self.jump_table = [x.value for x in program.code.jump_table]

        for idx, val in enumerate(program.registers):
            self.reg[idx] = np.uint64(val)

        self.status = ExitReason.none.value

        self.inst_bitmask: List[bool] = program.code.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []
        self.create_instruction_lookup()


    def mem_write(self, opcode, addr, value):
        if opcode not in MemOps:
            raise Exception(f"Invalid memory operation: {opcode}")

        if not MemOps[opcode]["write"]:
            raise Exception(f"Not a valid memory write operation: {opcode}")

        bytes_to_write = MemOps[opcode]["bytes"]
        self.mem.write_int(addr, value, bytes_to_write)


    def mem_read(self, opcode, addr):
        if opcode not in MemOps:
            raise Exception(f"Invalid memory operation: {opcode}")

        if not MemOps[opcode]["read"]:
            raise Exception(f"Not a valid memory read operation: {opcode}")

        bytes_to_read = MemOps[opcode]["bytes"]
        return self.mem.read_int(addr, bytes_to_read)


    # GP_A.15
    def djump(self, a: int):
        if a == 2 ** 32 - 2 ** 16:
            self.status = ExitReason.halt.value
            return 0
        elif (a == 0 or
              a > len(self.jump_table) * PVM_DYNAMIC_ALIGNMENT_FACTOR or
              a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0 or
              self.jump_table[a//PVM_DYNAMIC_ALIGNMENT_FACTOR-1] not in self.inst_pos):
            #self.status = ExitCondition.panic.value
            #return 0
            raise PanicError(f"Invalid djump operation: a={a}")
        else:
            return self.jump_table[a//PVM_DYNAMIC_ALIGNMENT_FACTOR-1] - self.pc

    def get_exit_condition(self) -> ExitCondition:
        exit_value = None
        exit_reason = self.status

        if self.status in (ExitReason.host_halt.value, ExitReason.page_fault.value):
            exit_value = int(self.exit_value)
        elif self.status == ExitReason.halt.value:
            mem = bytes()
            try:
                mem = bytes(self.mem.read_bytes(self.reg[7], self.reg[8]))
            except PVMMemoryError:
                pass
            exit_value = mem
        elif self.status == ExitReason.panic.value:
            exit_value = None
        else:
            exit_value = b''

        return ExitCondition(reason=ExitReason(exit_reason), value=exit_value)

    def next_instruction(self):
        inst_index = self.inst_pos[self.pc]
        self.skip_len = self.inst_arg_len[inst_index] + 1

    def invoke(
        self,
        pc: int,
        gas: int
    ):
        self.pc = pc
        self.gas = gas

        if self.log:
            self.log.state()
            self.log.header()

        while self.status == ExitReason.none.value and self.gas > 0:

            self.gas -= 1
            self.pc = int(self.pc) + self.skip_len

            #gp_0.3.6-eq:215
            if self.pc >= self.code_size:
                self.status = ExitReason.panic.value
                break

            inst_index = self.inst_pos[self.pc]
            self.opcode = opcode = self.code[self.pc]
            inst_type = OpcodeScheme[opcode]
            self.skip_len = self.inst_arg_len[inst_index] + 1

            try:
                match inst_type:

                    #GP_A.5.1
                    case InstructionType.none:

                        match opcode:
                            case op.trap.value:
                                self.log and self.log()
                                #self.status = ExitCondition.panic.value
                                raise PanicError(f"trap")
                            case op.fallthrough.value:
                                self.log and self.log()

                            case _:
                                raise InvalidOpcode(f"Invalid noargs opcode: {opcode} for instruction type {inst_type}")


                    #GP_A.5.2
                    case InstructionType.imm:

                        l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 2)))
                        v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                        match opcode:
                            case op.ecalli.value:
                                self.status = ExitReason.host_halt.value
                                self.exit_value = v_x
                                self.log and self.log(imm1=v_x)

                            case _:
                                raise InvalidOpcode(f"Invalid imm opcode: {opcode} for instruction type {inst_type}")

                    #GP_A.5.3
                    case InstructionType.reg_ext_imm:

                        r_a = min(12, self.code[self.pc + 1] % 16)
                        v_x = read_uint(self.code, self.pc + 2, 8)

                        match opcode:
                            case op.load_imm_64.value:
                                self.reg[r_a] = v_x
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case _:
                                raise InvalidOpcode(f"Invalid reg_ext_imm opcode: {opcode} for instruction type {inst_type}")

                    #GP_A.5.4
                    case InstructionType.imm_imm:

                        l_x = int(min(4, self.code[self.pc + 1] % 8))
                        l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                        v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)
                        v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                        match opcode:
                            case op.store_imm_u8.value:
                                self.mem_write(opcode, v_x, v_y % 2 ** 8)
                                self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 1)})
                            case op.store_imm_u16.value:
                                self.mem_write(opcode, v_x, v_y % 2 ** 16)
                                self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 2)})
                            case op.store_imm_u32.value:
                                self.mem_write(opcode, v_x, v_y % 2 ** 32)
                                self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 4)})
                            case op.store_imm_u64.value:
                                self.mem_write(opcode, v_x, v_y)
                                self.log and self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 8)})

                            case _:
                                raise InvalidOpcode(f"Invalid imm_imm opcode: {opcode} for instruction type {inst_type}")


                    #GP_A.5.5
                    case InstructionType.offset:

                        l_x = int(min(4, self.inst_arg_len[inst_index]))
                        v_x = pvm_Z(read_uint(self.code, self.pc + 1, l_x), l_x)

                        match opcode:
                            case op.jump.value:
                                self.skip_len = v_x
                                self.log and self.log(off1=v_x)

                            case _:
                                raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                    #GP_A.5.6
                    case InstructionType.reg_imm:
                        r_a = min(12, self.code[self.pc + 1] % 16)
                        l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                        v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)


                        match opcode:
                            case op.jump_ind.value:
                                self.skip_len = self.djump(np.uint32(self.reg[r_a]+v_x))
                                self.log and self.log(reg1=r_a, imm1=v_x, context={"skip_len": self.skip_len})

                            case op.load_imm.value:
                                self.reg[r_a] = v_x
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_u8.value:
                                self.reg[r_a] = self.mem_read(opcode, v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_i8.value:
                                self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 1)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_u16.value:
                                self.reg[r_a] = self.mem_read(opcode, v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_i16.value:
                                self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 2)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_u32.value:
                                self.reg[r_a] = self.mem_read(opcode, v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_i32.value:
                                self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 4)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.load_u64.value:
                                self.reg[r_a] = self.mem_read(opcode, v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x)

                            case op.store_u8.value:
                                self.mem_write(opcode, v_x, self.reg[r_a] % 2**8)
                                self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 1)})

                            case op.store_u16.value:
                                self.mem_write(opcode, v_x, self.reg[r_a] % 2**16)
                                self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 2)})

                            case op.store_u32.value:
                                self.mem_write(opcode, v_x, self.reg[r_a] % 2**32)
                                self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 4)})

                            case op.store_u64.value:
                                self.mem_write(opcode, v_x, self.reg[r_a])
                                self.log and self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 8)})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                    # GP_A.5.7
                    case InstructionType.reg_imm_imm:
                        # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                        r_a = min(12, self.code[self.pc + 1] % 16)
                        w_a = self.reg[r_a]

                        # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                        v_x = 0
                        l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                        if l_x > 0:
                            v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                        l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                        v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                        match opcode:

                            case op.store_imm_ind_u8.value:
                                self.mem_write(opcode, w_a + v_x, v_y % 2**8)
                                self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 1)})

                            case op.store_imm_ind_u16.value:
                                self.mem_write(opcode, w_a + v_x, v_y % 2**16)
                                self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 2)})

                            case op.store_imm_ind_u32.value:
                                self.mem_write(opcode, w_a + v_x, v_y % 2**32)
                                self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 4)})

                            case op.store_imm_ind_u64.value:
                                self.mem_write(opcode, w_a + v_x, v_y)
                                self.log and self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 8)})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                    # GP_A.5.8
                    case InstructionType.reg_imm_offset:
                        # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                        r_a = min(12, self.code[self.pc + 1] % 16)
                        w_a = self.reg[r_a]

                        # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                        l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                        v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                        l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                        v_y = pvm_Z(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                        match opcode:
                            case op.load_imm_jump.value:
                                self.skip_len = v_y
                                self.reg[r_a] = v_x
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_eq_imm.value:
                                self.branch(v_y, w_a == v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_ne_imm.value:
                                self.branch(v_y, w_a != v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_lt_u_imm.value:
                                self.branch(v_y, w_a < v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_le_u_imm.value:
                                self.branch(v_y, w_a <= v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_ge_u_imm.value:
                                self.branch(v_y, w_a >= v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_gt_u_imm.value:
                                self.branch(v_y, w_a > v_x)
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_lt_s_imm.value:
                                self.branch(v_y, pvm_Z(w_a, 8) < pvm_Z(v_x, 8))
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_le_s_imm.value:
                                self.branch(v_y, pvm_Z(w_a, 8) <= pvm_Z(v_x, 8))
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_ge_s_imm.value:
                                self.branch(v_y, pvm_Z(w_a, 8) >= pvm_Z(v_x, 8))
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case op.branch_gt_s_imm.value:
                                self.branch(v_y, pvm_Z(w_a, 8) > pvm_Z(v_x, 8))
                                self.log and self.log(reg1=r_a, imm1=v_x, off1=v_y)

                            case _:
                                raise InvalidOpcode(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")

                    #GP_A.5.9
                    case InstructionType.reg_reg:

                        r_d = min(12, self.code[self.pc + 1] % 16)
                        r_a = min(12, self.code[self.pc + 1] // 16)

                        match opcode:
                            case op.move_reg.value:
                                self.reg[r_d] = self.reg[r_a]
                                self.log and self.log(reg1=r_d, reg2=r_a)

                            case op.sbrk.value:
                                # Note: set break / set break pointer (extend heap memory)
                                self.reg[r_d] = self.mem.extend_heap(self.reg[r_a])
                                self.log and self.log(reg1=r_d, reg2=r_a)

                            case op.count_set_bits_64.value:
                                self.reg[r_d] = np.bitwise_count(self.reg[r_a])
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.count_set_bits_32.value:
                                self.reg[r_d] = np.bitwise_count(np.uint32(self.reg[r_a]))
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.leading_zero_bits_64.value:
                                self.reg[r_d] = count_leading_zeroes(self.reg[r_a])
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.leading_zero_bits_32.value:
                                self.reg[r_d] = count_leading_zeroes(np.uint32(self.reg[r_a]), 32)
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.trailing_zero_bits_64.value:
                                self.reg[r_d] = count_trailing_zeroes(self.reg[r_a])
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.trailing_zero_bits_32.value:
                                self.reg[r_d] = count_trailing_zeroes(np.uint32(self.reg[r_a]), 32)
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.sign_extend_8.value:
                                self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**8, 1), 8)
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.sign_extend_16.value:
                                self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**16, 2), 8)
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.zero_extend_16.value:
                                self.reg[r_d] = self.reg[r_a] % 2**16
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case op.reverse_bytes.value:
                                self.reg[r_d] = reverse_bytes(self.reg[r_a])
                                self.log and self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                    # GP_A.5.10
                    case InstructionType.reg_reg_imm:

                        r_a = min(12, self.code[self.pc + 1] % 16)
                        r_b = min(12, self.code[self.pc + 1] // 16)

                        w_a = self.reg[r_a]
                        w_b = self.reg[r_b]

                        l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                        v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                        match opcode:

                            case op.store_ind_u8.value:
                                self.mem_write(opcode, w_b + v_x, w_a)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.store_ind_u16.value:
                                self.mem_write(opcode, w_b + v_x, w_a)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.store_ind_u32.value:
                                self.mem_write(opcode, w_b + v_x, w_a)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.store_ind_u64.value:
                                self.mem_write(opcode, w_b + v_x, w_a)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_u8.value:
                                self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_i8.value:
                                self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 1), 8)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_u16.value:
                                self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_i16.value:
                                self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 2), 8)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_u32.value:
                                self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_i32.value:
                                self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 4), 8)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.load_ind_u64.value:
                                self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                            case op.add_imm_32.value:
                                self.reg[r_a] = pvm_X((w_b + v_x) % 2**32, 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.and_imm.value:
                                self.reg[r_a] = w_b & v_x
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.xor_imm.value:
                                self.reg[r_a] = w_b ^ v_x
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.or_imm.value:
                                self.reg[r_a] = w_b | v_x
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.mul_imm_32.value:
                                self.reg[r_a] = pvm_X((w_b * v_x) % 2**32, 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.set_lt_u_imm.value:
                                self.reg[r_a] = w_b < v_x and 1 or 0
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.set_lt_s_imm.value:
                                self.reg[r_a] = pvm_Z(w_b, 8) < pvm_Z(v_x, 8) and 1 or 0
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.shlo_l_imm_32.value:
                                self.reg[r_a] = pvm_X((w_b * 2**(v_x % 32)) % 2 ** 32, 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.shlo_r_imm_32.value:
                                self.reg[r_a] = pvm_X(riscv_div((w_b % 2 ** 32), (2 ** (v_x % 32))), 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                            case op.shar_r_imm_32.value:
                                self.reg[r_a] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(w_b % 2 ** 32, 4),
                                        (2 ** (v_x % 32))
                                    ),
                                 8
                                )
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.neg_add_imm_32.value:
                                self.reg[r_a] = pvm_X((v_x + 2**32 - w_b) % 2**32, 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.set_gt_u_imm.value:
                                self.reg[r_a] = w_b > v_x and 1 or 0
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.set_gt_s_imm.value:
                                self.reg[r_a] = pvm_Z(w_b, 8) > pvm_Z(v_x, 8) and 1 or 0
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_l_imm_alt_32.value:
                                self.reg[r_a] = pvm_X((v_x * (2 ** (w_b % 32))) % 2**32, 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_r_imm_alt_32.value:
                                self.reg[r_a] = pvm_X(riscv_div(v_x % 2**32, (2 ** (w_b % 32))), 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shar_r_imm_alt_32.value:
                                self.reg[r_a] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(v_x % 2**32, 4),
                                        2 ** (w_b % 32)
                                    ),
                                    8
                                )
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.cmov_iz_imm.value:
                                if w_b == 0:
                                    self.reg[r_a] = v_x
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.cmov_nz_imm.value:
                                if w_b != 0:
                                    self.reg[r_a] = v_x
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.add_imm_64.value:
                                self.reg[r_a] = (w_b + v_x) #% 2**64
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.mul_imm_64.value:
                                self.reg[r_a] = (w_b * v_x) #% 2**64
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_l_imm_64.value:
                                self.reg[r_a] = pvm_X((w_b * 2**(v_x % 64)), 8)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_r_imm_64.value:
                                self.reg[r_a] = pvm_X(riscv_div(w_b, np.uint64(2**(v_x % 64))), 8)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shar_r_imm_64.value:
                                self.reg[r_a] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(w_b, 8),
                                        2**(v_x % 64)
                                    ),
                                    8
                                )
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.neg_add_imm_64.value:
                                self.reg[r_a] = ((int(v_x) + 2**64 - int(w_b)) % 2**64)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_l_imm_alt_64.value:
                                self.reg[r_a] = (v_x * 2**(w_b % 64)) #% 2**64
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shlo_r_imm_alt_64.value:
                                self.reg[r_a] = riscv_div(v_x, np.uint64(2**(w_b % 64)))
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.shar_r_imm_alt_64.value:
                                self.reg[r_a] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(v_x, 8),
                                        2**(w_b % 64)),
                                    8
                                )
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.rot_r_64_imm.value:
                                self.reg[r_a] = rori64(w_b, v_x)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.rot_r_64_imm_alt.value:
                                self.reg[r_a] = rori64(v_x, w_b)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.rot_r_32_imm.value:
                                self.reg[r_a] = pvm_X(rori32(np.uint32(w_b), np.uint32(v_x)), 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case op.rot_r_32_imm_alt.value:
                                self.reg[r_a] = pvm_X(rori32(np.uint32(v_x), np.uint32(w_b)), 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                    # GP_A.5.11
                    case InstructionType.reg_reg_offset:
                        r_a = min(12, self.code[self.pc + 1] % 16)
                        r_b = min(12, self.code[self.pc + 1] // 16)
                        w_a = self.reg[r_a]
                        w_b = self.reg[r_b]

                        l_x = min(4, max(0, self.inst_arg_len[inst_index] - 1))
                        v_x = pvm_Z(read_uint(self.code, self.pc + 2, l_x), l_x)

                        match opcode:
                            case op.branch_eq.value:
                                self.branch(v_x, w_a == w_b)
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case op.branch_ne.value:
                                self.branch(v_x, w_a != w_b)
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case op.branch_lt_u.value:
                                self.branch(v_x, w_a < w_b)
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case op.branch_lt_s.value:
                                self.branch(v_x, pvm_Z(w_a, 8) < pvm_Z(w_b, 8))
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case op.branch_ge_u.value:
                                self.branch(v_x, w_a >= w_b)
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case op.branch_ge_s.value:
                                self.branch(v_x, pvm_Z(w_a, 8) >= pvm_Z(w_b, 8))
                                self.log and self.log(reg1=r_a, reg2=r_b, off1=v_x)

                            case _:
                                raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")


                    # GP_A.5.12
                    case InstructionType.reg_reg_imm_imm:
                        # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                        r_a = min(12, self.code[self.pc + 1] % 16)
                        r_b = self.code[self.pc + 1] // 16

                        #w_a = self.reg[r_a]
                        w_b = self.reg[r_b]

                        l_x = int(min(4, self.code[self.pc + 2] % 8))
                        v_x = pvm_X(read_uint(self.code, self.pc + 3, l_x), l_x)

                        l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 2)))
                        v_y = pvm_X(read_uint(self.code, self.pc + 3 + l_x, l_y), l_y)

                        match opcode:

                            case op.load_imm_jump_ind.value:
                                self.reg[r_a] = v_x
                                self.skip_len = self.djump(int(w_b + v_y) % 2**32)
                                self.log and self.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": self.skip_len})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                    # GP_A.5.13
                    case InstructionType.reg_reg_reg:

                        r_a = min(12, self.code[self.pc + 1] % 16)
                        r_b = min(12, self.code[self.pc + 1] // 16)
                        r_d = min(12, self.code[self.pc + 2])

                        w_a = self.reg[r_a]
                        w_b = self.reg[r_b]

                        match opcode:
                            case op.add_32.value:
                                self.reg[r_d] = pvm_X((w_a + w_b) % 2**32, 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.sub_32.value:
                                self.reg[r_d] = pvm_X((w_a + 2**32 - (w_b % 2**32)) % 2**32, 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.mul_32.value:
                                self.reg[r_d] = pvm_X((w_a * w_b) % 2**32, 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.div_u_32.value:
                                if self.reg[r_b] == 0:
                                    self.reg[r_d] = 2**64-1
                                else:
                                    self.reg[r_d] = pvm_X(riscv_div(w_a % 2**32, w_b % 2**32), 4)

                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.div_s_32.value:
                                a = np.int32(pvm_Z(w_a % 2**32, 4))
                                b = np.int32(pvm_Z(w_b % 2**32, 4))

                                if b == 0:
                                    self.reg[r_d] = 2**64-1
                                elif a == -2**31 and b == -1:
                                    self.reg[r_d] = pvm_Z_inv(a, 8)
                                else:
                                    self.reg[r_d] = pvm_Z_inv(pvm_rtz_div(a, b), 8)

                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rem_u_32.value:
                                if w_b % 2**32 == 0:
                                    self.reg[r_d] = pvm_X(w_a % 2**32, 4)
                                else:
                                    self.reg[r_d] = pvm_X((w_a % 2**32) % (w_b % 2**32), 4)

                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rem_s_32.value:
                                a = pvm_Z(w_a % 2**32, 4)
                                b = pvm_Z(w_b % 2**32, 4)

                                if b == 0:
                                    self.reg[r_d] = pvm_Z_inv(a, 8)
                                elif a == -2**31 and b == -1:
                                    self.reg[r_d] = 0
                                else:
                                    self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shlo_l_32.value:
                                self.reg[r_d] = pvm_X((w_a * 2**(w_b % 32)) % 2**32, 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shlo_r_32.value:
                                self.reg[r_d] = pvm_X(riscv_div(w_a % 2**32, 2**(w_b % 32)), 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shar_r_32.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(w_a % 2**32, 4),
                                        2**(w_b % 32)
                                    ),
                                 8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.add_64.value:
                                self.reg[r_d] = (w_a + w_b) #% 2**64
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.sub_64.value:
                                self.reg[r_d] = (int(w_a) + 2**64 - int(w_b)) % 2**64
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.mul_64.value:
                                self.reg[r_d] = (w_a * w_b) #% 2**64
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.div_u_64.value:
                                if w_b == 0:
                                    self.reg[r_d] = 2**64 - 1
                                else:
                                    self.reg[r_d] = riscv_div(w_a, w_b)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.div_s_64.value:
                                if w_b == 0:
                                    self.reg[r_d] = 2**64 - 1
                                elif pvm_Z(w_a, 8) == -2**63 and pvm_Z(w_b, 8) == -1:
                                    self.reg[r_d] = w_a
                                else:
                                    self.reg[r_d] = pvm_Z_inv(
                                        pvm_rtz_div(
                                            pvm_Z(w_a, 8),
                                            pvm_Z(w_b, 8)
                                        ),
                                        8
                                    )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rem_u_64.value:
                                if w_b == 0:
                                    self.reg[r_d] = w_a
                                else:
                                    self.reg[r_d] = w_a % w_b
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rem_s_64.value:
                                a = pvm_Z(w_a, 8)
                                b = pvm_Z(w_b, 8)

                                if w_b == 0:
                                    self.reg[r_d] = w_a
                                elif a == -2**63 and b == -1:
                                    self.reg[r_d] = 0
                                else:
                                    self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shlo_l_64.value:
                                self.reg[r_d] = (w_a * 2**(w_b % 64)) #% 2**64
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shlo_r_64.value:
                                self.reg[r_d] = riscv_div(w_a, 2**(w_b % 64))
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.shar_r_64.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    riscv_div(
                                        pvm_Z(w_a, 8),
                                        2**(w_b % 64)
                                    ),
                                    8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op._and.value:
                                self.reg[r_d] = self.reg[r_a] & self.reg[r_b]
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.xor.value:
                                self.reg[r_d] = self.reg[r_a] ^ self.reg[r_b]
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op._or.value:
                                self.reg[r_d] = self.reg[r_a] | self.reg[r_b]
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.mul_upper_s_s.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    riscv_div((pvm_Z(w_a, 8) * pvm_Z(w_b, 8)), 2**64),
                                    8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.mul_upper_u_u.value:
                                self.reg[r_d] = riscv_div(int(w_a) * int(w_b), 2**64)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.mul_upper_s_u.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    riscv_div(pvm_Z(w_a, 8) * int(w_b), 2**64),
                                    8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.set_lt_u.value:
                                self.reg[r_d] = np.uint64(w_a < w_b)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.set_lt_s.value:
                                self.reg[r_d] = np.int64(pvm_Z(w_a, 8) < pvm_Z(w_b,8))
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.cmov_iz.value:
                                if w_b == 0:
                                    self.reg[r_d] = w_a
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.cmov_nz.value:
                                if w_b != 0:
                                    self.reg[r_d] = w_a
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rot_l_64.value:
                                self.reg[r_d] = roli64(w_a, w_b % 64)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rot_l_32.value:
                                self.reg[r_d] = pvm_X(roli32(np.uint32(w_a), w_b % 32), 4)
                                self.log and self.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rot_r_64.value:
                                self.reg[r_d] = rori64(w_a, w_b % 64)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.rot_r_32.value:
                                self.reg[r_d] = pvm_X(rori32(np.uint32(w_a), w_b % 32), 4)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.and_inv.value:
                                self.reg[r_d] = w_a & ~w_b
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.or_inv.value:
                                self.reg[r_d] = w_a | ~w_b
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.xnor.value:
                                self.reg[r_d] = np.uint64(~(w_a ^ w_b) & 0xFFFFFFFFFFFFFFFF)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op._max.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    max(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                                    8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.max_u.value:
                                self.reg[r_d] = max(w_a,  w_b)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op._min.value:
                                self.reg[r_d] = pvm_Z_inv(
                                    min(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                                    8
                                )
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case op.min_u.value:
                                self.reg[r_d] = min(w_a,  w_b)
                                self.log and self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                            case _:
                                raise InvalidOpcode(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                    case _:
                        raise InvalidOpcode(f"Invalid instruction type: {inst_type}")

            except PVMMemoryError:
                self.status = ExitReason.page_fault.value
                self.gas -= 1
                self.exit_value = self.mem._mem_addr
                break

            except PanicError as panic_error:
                self.status = ExitReason.panic.value
                #TODO!!!!!!!!!!!!!!!!
                self.log.dump_code()
                self.log.dump_test_vector()
                break
