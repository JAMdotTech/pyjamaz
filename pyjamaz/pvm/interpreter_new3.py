import numpy as np
import numpy.typing as npt

from typing import List, Dict

from .exceptions import InvalidOpcode, PVMMemoryError, PanicError
from .types_new import PVMProgram, PVMMemory

from .utils_new import (
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
    read_uint,
)

from .constants_new import (
    Opcode as op,
    OpcodeScheme,
    InstructionType,
    ExitReason,
    MemOps,
    OpcodeNames,
    ExitCondition,
)

from pyjamaz.graypaper_constants import PVM_DYNAMIC_ALIGNMENT_FACTOR


class PVMInterpreter:

    def __init__(self, program: PVMProgram, logger_cls=None):
        self.name = program.name
        self.reg:npt.NDArray[np.uint64] = np.zeros(13, dtype=np.uint64)
        self.inst_nr:np.uint32 = np.uint32(0)
        self.pc:np.uint32 = np.uint32(0)
        self.opcode:int = 0
        self.skip_len: int = 0
        self.gas:np.int64 = np.int64(0)
        self.code:npt.NDArray[np.uint8] = np.array(1, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(0)
        self.jump_table = []

        self.inst_bitmask: List[bool] = []
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []

        self.mem:PVMMemory = None
        self.status:int = ExitReason.resume.value
        self.exit_value:int = None

        #self.log = None

        self.reset(program)

        # if logger_cls:
        #     self.program = program
        #     #self.log = logger_cls(pvm=self)
        #     #self.log._pvm = self
        #     #self.log._pvm_id = self.name
        #     for opcode_name in OpcodeNames.values():
        #         if opcode_name not in #self.log.log_opcodes:
        #             #self.log.log_opcodes[opcode_name] = 0


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

    # @njit removed - contains dict lookup and exception handling
    def branch(self, b:int, C:bool):
        """
        #GP-0.6.4-eq:A.17
        """
        if C:
            inst_pos = self.pc + b
            if inst_pos not in self.inst_pos:
                #self.status = ExitCondition.panic.value
                raise PanicError(f"Invalid branch instruction: C={C} b={b} inst_pos={inst_pos}")
            else:
                self.skip_len = b


    def reset(self, program: PVMProgram):
        self.pc = np.uint32(0)
        self.gas = np.int64(0)

        self.name = program.name
        self.code:npt.NDArray[np.uint8] = np.array(program.code.code, dtype=np.uint8)
        self.code_size: np.uint64 = np.uint64(len(self.code))
        self.mem = program.memory
        self.jump_table = [x.value for x in program.code.jump_table]

        for idx, val in enumerate(program.registers):
            self.reg[idx] = np.uint64(val)

        self.status = ExitReason.resume.value

        self.inst_bitmask: List[bool] = program.code.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_arg_len: List[int] = []
        self.create_instruction_lookup()

    #TODO: registers_as_int
    def get_registers(self):
        return [int(x) for x in self.reg]

    # @njit removed - contains exception handling or dict operations
    def mem_write(self, opcode, addr, value):
        if opcode not in MemOps:
            raise Exception(f"Invalid memory operation: {opcode}")

        if not MemOps[opcode]["write"]:
            raise Exception(f"Not a valid memory write operation: {opcode}")

        bytes_to_write = MemOps[opcode]["bytes"]
        self.mem.write_int(addr % self.mem.SIZE, value, bytes_to_write)

    # @njit removed - contains exception handling or dict operations
    def mem_read(self, opcode, addr):
        if opcode not in MemOps:
            raise Exception(f"Invalid memory operation: {opcode}")

        if not MemOps[opcode]["read"]:
            raise Exception(f"Not a valid memory read operation: {opcode}")

        bytes_to_read = MemOps[opcode]["bytes"]
        return self.mem.read_int(addr % self.mem.SIZE, bytes_to_read)


    #GP-0.6.7-section:A.15
    # @njit removed - contains exception handling or dict operations
    def djump(self, a: int):
        if a == 2 ** 32 - 2 ** 16:
            self.status = ExitReason.halt.value
            return 0
        elif (a == 0 or
              a > len(self.jump_table) * PVM_DYNAMIC_ALIGNMENT_FACTOR or
              a % PVM_DYNAMIC_ALIGNMENT_FACTOR != 0 or
              self.jump_table[a//PVM_DYNAMIC_ALIGNMENT_FACTOR-1] not in self.inst_pos):
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
                mem = self.mem.read_bytes(self.reg[7], self.reg[8])
            except (PVMMemoryError, PanicError):
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

    # @njit removed - contains exception handling or dict operations
    def invoke(
        self,
        pc: int,
        gas: int,
        single_step: bool = False
    ):
        self.pc = pc
        self.gas = gas

        # if #self.log:
        #     #self.log.pvm_counters()
        #     #self.log.pvm_header()

        # GP-0.6.7-section:A.4 Single-Step State Transition
        while self.status == ExitReason.resume.value and self.gas > 0:

            self.gas -= 1
            self.pc = int(self.pc) + self.skip_len
            self.inst_nr += 1

            if self.pc >= self.code_size:
                self.status = ExitReason.panic.value
                self.exit_value = None
                break

            inst_index = self.inst_pos[self.pc]
            self.opcode = opcode = self.code[self.pc]
            inst_type = OpcodeScheme[opcode]
            self.skip_len = self.inst_arg_len[inst_index] + 1

            try:
                #GP-0.6.7-section:A.5.1
                if inst_type == 0:  # InstructionType.none
                    if opcode == 0:  # op.trap
                        #self.status = ExitCondition.panic.value
                        raise PanicError(f"trap")
                    elif opcode == 1:  # op.fallthrough
                        pass
                    else:
                        raise InvalidOpcode(f"Invalid noargs opcode: {opcode} for instruction type {inst_type}")


                #GP-0.6.7-section:A.5.2
                elif inst_type == 1:  # InstructionType.imm
                    l_x = int(min(4, self.inst_arg_len[inst_index]))
                    v_x = pvm_X(read_uint(self.code, self.pc + 1, l_x), l_x)

                    if opcode == 10:  # op.ecalli
                        self.status = ExitReason.host_halt.value
                        self.exit_value = v_x
                    else:
                        raise InvalidOpcode(f"Invalid imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.3
                elif inst_type == 2:  # InstructionType.reg_ext_imm

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    v_x = read_uint(self.code, self.pc + 2, 8)

                    if opcode == 20:  # op.load_imm_64
                        self.reg[r_a] = v_x
                    else:
                        raise InvalidOpcode(f"Invalid reg_ext_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.4
                elif inst_type == 3:  # InstructionType.imm_imm

                    l_x = int(min(4, self.code[self.pc + 1] % 8))
                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)
                    v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == 30:  # op.store_imm_u8
                        self.mem_write(opcode, v_x, v_y % 2 ** 8)
                        #self.log and #self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 1)})
                    elif opcode == 31:  # op.store_imm_u16
                        self.mem_write(opcode, v_x, v_y % 2 ** 16)
                        #self.log and #self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 2)})
                    elif opcode == 32:  # op.store_imm_u32
                        self.mem_write(opcode, v_x, v_y % 2 ** 32)
                        #self.log and #self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 4)})
                    elif opcode == 33:  # op.store_imm_u64
                        self.mem_write(opcode, v_x, v_y)
                        #self.log and #self.log(imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(v_x, 8)})
                    else:
                        raise InvalidOpcode(f"Invalid imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.5
                elif inst_type == 4:  # InstructionType.offset

                    l_x = int(min(4, self.inst_arg_len[inst_index]))
                    v_x = pvm_Z(read_uint(self.code, self.pc + 1, l_x), l_x)

                    if opcode == 40:  # op.jump
                        self.skip_len = v_x
                        #self.log and #self.log(off1=v_x)
                    else:
                        raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                #GP-0.6.7-section:A.5.6
                elif inst_type == 5:  # InstructionType.reg_imm
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == 50:  # op.jump_ind
                        self.skip_len = self.djump(np.uint32(self.reg[r_a]+v_x))
                        #self.log and #self.log(reg1=r_a, imm1=v_x, context={"skip_len": self.skip_len})

                    elif opcode == 51:  # op.load_imm
                        self.reg[r_a] = v_x
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 52:  # op.load_u8
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 53:  # op.load_i8
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 1)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 54:  # op.load_u16
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 55:  # op.load_i16
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 2)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 56:  # op.load_u32
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 57:  # op.load_i32
                        self.reg[r_a] = pvm_X(self.mem_read(opcode, v_x), 4)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 58:  # op.load_u64
                        self.reg[r_a] = self.mem_read(opcode, v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x)

                    elif opcode == 59:  # op.store_u8
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**8)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 1)})

                    elif opcode == 60:  # op.store_u16
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**16)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 2)})

                    elif opcode == 61:  # op.store_u32
                        self.mem_write(opcode, v_x, self.reg[r_a] % 2**32)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 4)})

                    elif opcode == 62:  # op.store_u64
                        self.mem_write(opcode, v_x, self.reg[r_a])
                        #self.log and #self.log(reg1=r_a, imm1=v_x, context={"u'_vx": self.mem.read_int(v_x, 8)})

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.7
                elif inst_type == 6:  # InstructionType.reg_imm_imm
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    w_a = self.reg[r_a]

                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_y = pvm_X(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == 70:  # op.store_imm_ind_u8
                        self.mem_write(opcode, w_a + v_x, v_y % 2**8)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 1)})

                    elif opcode == 71:  # op.store_imm_ind_u16
                        self.mem_write(opcode, w_a + v_x, v_y % 2**16)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 2)})

                    elif opcode == 72:  # op.store_imm_ind_u32
                        self.mem_write(opcode, w_a + v_x, v_y % 2**32)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 4)})

                    elif opcode == 73:  # op.store_imm_ind_u64
                        self.mem_write(opcode, w_a + v_x, v_y)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, imm2=v_y, context={"u'_vx": self.mem.read_int(w_a + v_x, 8)})

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.8
                elif inst_type == 7:  # InstructionType.reg_imm_offset
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    w_a = self.reg[r_a]

                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                    l_x = int(min(4, (self.code[self.pc + 1] // 16) % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 1)))
                    v_y = pvm_Z(read_uint(self.code, self.pc + 2 + l_x, l_y), l_y)

                    if opcode == 80:  # op.load_imm_jump
                        self.skip_len = v_y
                        self.reg[r_a] = v_x
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 81:  # op.branch_eq_imm
                        self.branch(v_y, w_a == v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 82:  # op.branch_ne_imm
                        self.branch(v_y, w_a != v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 83:  # op.branch_lt_u_imm
                        self.branch(v_y, w_a < v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 84:  # op.branch_le_u_imm
                        self.branch(v_y, w_a <= v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 85:  # op.branch_ge_u_imm
                        self.branch(v_y, w_a >= v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 86:  # op.branch_gt_u_imm
                        self.branch(v_y, w_a > v_x)
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 87:  # op.branch_lt_s_imm
                        self.branch(v_y, pvm_Z(w_a, 8) < pvm_Z(v_x, 8))
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 88:  # op.branch_le_s_imm
                        self.branch(v_y, pvm_Z(w_a, 8) <= pvm_Z(v_x, 8))
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 89:  # op.branch_ge_s_imm
                        self.branch(v_y, pvm_Z(w_a, 8) >= pvm_Z(v_x, 8))
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    elif opcode == 90:  # op.branch_gt_s_imm
                        self.branch(v_y, pvm_Z(w_a, 8) > pvm_Z(v_x, 8))
                        #self.log and #self.log(reg1=r_a, imm1=v_x, off1=v_y)

                    else:
                        raise InvalidOpcode(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.9
                elif inst_type == 8:  # InstructionType.reg_reg

                    r_d = min(12, self.code[self.pc + 1] % 16)
                    r_a = min(12, self.code[self.pc + 1] // 16)

                    if opcode == 100:  # op.move_reg
                        self.reg[r_d] = self.reg[r_a]
                        #self.log and #self.log(reg1=r_d, reg2=r_a)

                    elif opcode == 101:  # op.sbrk
                        # Note: set break / set break pointer (extend heap memory)
                        self.reg[r_d] = self.mem.extend_heap(self.reg[r_a])
                        #self.log and #self.log(reg1=r_d, reg2=r_a)

                    elif opcode == 102:  # op.count_set_bits_64
                        self.reg[r_d] = np.bitwise_count(self.reg[r_a])
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 103:  # op.count_set_bits_32
                        self.reg[r_d] = np.bitwise_count(np.uint32(self.reg[r_a]))
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 104:  # op.leading_zero_bits_64
                        #self.reg[r_d] = count_leading_zeroes(reverse_bits_64(self.reg[r_a]))
                        self.reg[r_d] = count_leading_zeroes(self.reg[r_a])
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 105:  # op.leading_zero_bits_32
                        #self.reg[r_d] = count_leading_zeroes(np.uint32(reverse_bits_32(self.reg[r_a])), 32)
                        self.reg[r_d] = count_leading_zeroes(np.uint32(self.reg[r_a]), 32)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 106:  # op.trailing_zero_bits_64
                        self.reg[r_d] = count_trailing_zeroes(self.reg[r_a])
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 107:  # op.trailing_zero_bits_32
                        self.reg[r_d] = count_trailing_zeroes(np.uint32(self.reg[r_a]), 32)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 108:  # op.sign_extend_8
                        self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**8, 1), 8)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 109:  # op.sign_extend_16
                        self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a] % 2**16, 2), 8)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 110:  # op.zero_extend_16
                        self.reg[r_d] = self.reg[r_a] % 2**16
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    elif opcode == 111:  # op.reverse_bytes
                        self.reg[r_d] = reverse_bytes(self.reg[r_a])
                        #self.log and #self.log(reg1=r_d, reg2=r_a, context={"w'_d": self.reg[r_d]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.10
                elif inst_type == 9:  # InstructionType.reg_reg_imm

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = int(min(4, max(0, self.inst_arg_len[inst_index] - 1)))
                    v_x = pvm_X(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == 120:  # op.store_ind_u8
                        self.mem_write(opcode, w_b + v_x, w_a % 2**8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**8, "w_b": w_b})

                    elif opcode == 121:  # op.store_ind_u16
                        self.mem_write(opcode, w_b + v_x, w_a % 2**16)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**16, "w_b": w_b})

                    elif opcode == 122:  # op.store_ind_u32
                        self.mem_write(opcode, w_b + v_x, w_a % 2**32)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a % 2**32, "w_b": w_b})

                    elif opcode == 123:  # op.store_ind_u64
                        self.mem_write(opcode, w_b + v_x, w_a)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 124:  # op.load_ind_u8
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 125:  # op.load_ind_i8
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 1), 8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 126:  # op.load_ind_u16
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 127:  # op.load_ind_i16
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 2), 8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 128:  # op.load_ind_u32
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 129:  # op.load_ind_i32
                        self.reg[r_a] = pvm_Z_inv(pvm_Z(self.mem_read(opcode, w_b + v_x), 4), 8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 130:  # op.load_ind_u64
                        self.reg[r_a] = self.mem_read(opcode, w_b + v_x)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_a": w_a, "w_b": w_b})

                    elif opcode == 131:  # op.add_imm_32
                        self.reg[r_a] = pvm_X((w_b + v_x) % 2**32, 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 132:  # op.and_imm
                        self.reg[r_a] = w_b & v_x
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 133:  # op.xor_imm
                        self.reg[r_a] = w_b ^ v_x
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 134:  # op.or_imm
                        self.reg[r_a] = w_b | v_x
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 135:  # op.mul_imm_32
                        self.reg[r_a] = pvm_X((w_b * v_x) % 2**32, 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 136:  # op.set_lt_u_imm
                        self.reg[r_a] = w_b < v_x and 1 or 0
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 137:  # op.set_lt_s_imm
                        self.reg[r_a] = pvm_Z(w_b, 8) < pvm_Z(v_x, 8) and 1 or 0
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 138:  # op.shlo_l_imm_32
                        self.reg[r_a] = pvm_X((w_b * 2**(v_x % 32)) % 2 ** 32, 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 139:  # op.shlo_r_imm_32
                        self.reg[r_a] = pvm_X(riscv_div((w_b % 2 ** 32), (2 ** (v_x % 32))), 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b})

                    elif opcode == 140:  # op.shar_r_imm_32
                        self.reg[r_a] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(w_b % 2 ** 32, 4),
                                (2 ** (v_x % 32))
                            ),
                         8
                        )
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 141:  # op.neg_add_imm_32
                        self.reg[r_a] = pvm_X((v_x + 2**32 - w_b) % 2**32, 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 142:  # op.set_gt_u_imm
                        self.reg[r_a] = w_b > v_x and 1 or 0
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 143:  # op.set_gt_s_imm
                        self.reg[r_a] = pvm_Z(w_b, 8) > pvm_Z(v_x, 8) and 1 or 0
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 144:  # op.shlo_l_imm_alt_32
                        self.reg[r_a] = pvm_X((v_x * (2 ** (w_b % 32))) % 2**32, 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 145:  # op.shlo_r_imm_alt_32
                        self.reg[r_a] = pvm_X(riscv_div(v_x % 2**32, (2 ** (w_b % 32))), 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 146:  # op.shar_r_imm_alt_32
                        self.reg[r_a] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(v_x % 2**32, 4),
                                2 ** (w_b % 32)
                            ),
                            8
                        )
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 147:  # op.cmov_iz_imm
                        if w_b == 0:
                            self.reg[r_a] = v_x
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 148:  # op.cmov_nz_imm
                        if w_b != 0:
                            self.reg[r_a] = v_x
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 149:  # op.add_imm_64
                        self.reg[r_a] = (w_b + v_x) #% 2**64
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 150:  # op.mul_imm_64
                        self.reg[r_a] = (w_b * v_x) #% 2**64
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 151:  # op.shlo_l_imm_64
                        self.reg[r_a] = pvm_X((w_b * 2**(v_x % 64)), 8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 152:  # op.shlo_r_imm_64
                        self.reg[r_a] = pvm_X(riscv_div(w_b, np.uint64(2**(v_x % 64))), 8)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 153:  # op.shar_r_imm_64
                        self.reg[r_a] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(w_b, 8),
                                2**(v_x % 64)
                            ),
                            8
                        )
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 154:  # op.neg_add_imm_64
                        self.reg[r_a] = ((int(v_x) + 2**64 - int(w_b)) % 2**64)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 155:  # op.shlo_l_imm_alt_64
                        self.reg[r_a] = (v_x * 2**(w_b % 64)) #% 2**64
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 156:  # op.shlo_r_imm_alt_64
                        self.reg[r_a] = riscv_div(v_x, np.uint64(2**(w_b % 64)))
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 157:  # op.shar_r_imm_alt_64
                        self.reg[r_a] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(v_x, 8),
                                2**(w_b % 64)),
                            8
                        )
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 158:  # op.rot_r_64_imm
                        self.reg[r_a] = rori64(w_b, v_x)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 159:  # op.rot_r_64_imm_alt
                        self.reg[r_a] = rori64(v_x, w_b)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 160:  # op.rot_r_32_imm
                        self.reg[r_a] = pvm_X(rori32(np.uint32(w_b), np.uint32(v_x)), 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    elif opcode == 161:  # op.rot_r_32_imm_alt
                        self.reg[r_a] = pvm_X(rori32(np.uint32(v_x), np.uint32(w_b)), 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, context={"w_b": w_b, "w'_a": self.reg[r_a]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.11
                elif inst_type == 10:  # InstructionType.reg_reg_offset
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = min(4, max(0, self.inst_arg_len[inst_index] - 1))
                    v_x = pvm_Z(read_uint(self.code, self.pc + 2, l_x), l_x)

                    if opcode == 170:  # op.branch_eq
                        self.branch(v_x, w_a == w_b)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == 171:  # op.branch_ne
                        self.branch(v_x, w_a != w_b)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == 172:  # op.branch_lt_u
                        self.branch(v_x, w_a < w_b)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == 173:  # op.branch_lt_s
                        self.branch(v_x, pvm_Z(w_a, 8) < pvm_Z(w_b, 8))
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == 174:  # op.branch_ge_u
                        self.branch(v_x, w_a >= w_b)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    elif opcode == 175:  # op.branch_ge_s
                        self.branch(v_x, pvm_Z(w_a, 8) >= pvm_Z(w_b, 8))
                        #self.log and #self.log(reg1=r_a, reg2=r_b, off1=v_x)

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.12
                elif inst_type == 11:  # InstructionType.reg_reg_imm_imm
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = self.code[self.pc + 1] // 16

                    #w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = int(min(4, self.code[self.pc + 2] % 8))
                    v_x = pvm_X(read_uint(self.code, self.pc + 3, l_x), l_x)

                    l_y = int(min(4, max(0, self.inst_arg_len[inst_index] - l_x - 2)))
                    v_y = pvm_X(read_uint(self.code, self.pc + 3 + l_x, l_y), l_y)

                    if opcode == 180:  # op.load_imm_jump_ind
                        self.reg[r_a] = v_x
                        self.skip_len = self.djump(int(w_b + v_y) % 2**32)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, imm1=v_x, imm2=v_y, context={"skip_len": self.skip_len})
                    else:
                        raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                #GP-0.6.7-section:A.5.13
                elif inst_type == 12:  # InstructionType.reg_reg_reg

                    r_a = min(12, self.code[self.pc + 1] % 16)
                    r_b = min(12, self.code[self.pc + 1] // 16)
                    r_d = min(12, self.code[self.pc + 2])

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    if opcode == 190:  # op.add_32
                        self.reg[r_d] = pvm_X((w_a + w_b) % 2**32, 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 191:  # op.sub_32
                        self.reg[r_d] = pvm_X((w_a + 2**32 - (w_b % 2**32)) % 2**32, 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 192:  # op.mul_32
                        self.reg[r_d] = pvm_X((w_a * w_b) % 2**32, 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 193:  # op.div_u_32
                        if self.reg[r_b] == 0:
                            self.reg[r_d] = 2**64-1
                        else:
                            self.reg[r_d] = pvm_X(riscv_div(w_a % 2**32, w_b % 2**32), 4)

                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 194:  # op.div_s_32
                        a = np.int32(pvm_Z(w_a % 2**32, 4))
                        b = np.int32(pvm_Z(w_b % 2**32, 4))

                        if b == 0:
                            self.reg[r_d] = 2**64-1
                        elif a == -2**31 and b == -1:
                            self.reg[r_d] = pvm_Z_inv(a, 8)
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_rtz_div(a, b), 8)

                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 195:  # op.rem_u_32
                        if w_b % 2**32 == 0:
                            self.reg[r_d] = pvm_X(w_a % 2**32, 4)
                        else:
                            self.reg[r_d] = pvm_X((w_a % 2**32) % (w_b % 2**32), 4)

                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 196:  # op.rem_s_32
                        a = pvm_Z(w_a % 2**32, 4)
                        b = pvm_Z(w_b % 2**32, 4)

                        if b == 0:
                            self.reg[r_d] = pvm_Z_inv(a, 8)
                        elif a == -2**31 and b == -1:
                            self.reg[r_d] = 0
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 197:  # op.shlo_l_32
                        self.reg[r_d] = pvm_X((w_a * 2**(w_b % 32)) % 2**32, 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 198:  # op.shlo_r_32
                        self.reg[r_d] = pvm_X(riscv_div(w_a % 2**32, 2**(w_b % 32)), 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 199:  # op.shar_r_32
                        self.reg[r_d] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(w_a % 2**32, 4),
                                2**(w_b % 32)
                            ),
                         8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 200:  # op.add_64
                        self.reg[r_d] = (w_a + w_b) #% 2**64
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 201:  # op.sub_64
                        self.reg[r_d] = (int(w_a) + 2**64 - int(w_b)) % 2**64
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 202:  # op.mul_64
                        self.reg[r_d] = (w_a * w_b) #% 2**64
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 203:  # op.div_u_64
                        if w_b == 0:
                            self.reg[r_d] = 2**64 - 1
                        else:
                            self.reg[r_d] = riscv_div(w_a, w_b)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 204:  # op.div_s_64
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
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 205:  # op.rem_u_64
                        if w_b == 0:
                            self.reg[r_d] = w_a
                        else:
                            self.reg[r_d] = w_a % w_b
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 206:  # op.rem_s_64
                        a = pvm_Z(w_a, 8)
                        b = pvm_Z(w_b, 8)

                        if w_b == 0:
                            self.reg[r_d] = w_a
                        elif a == -2**63 and b == -1:
                            self.reg[r_d] = 0
                        else:
                            self.reg[r_d] = pvm_Z_inv(pvm_smod(a, b), 8)

                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 207:  # op.shlo_l_64
                        self.reg[r_d] = (w_a * 2**(w_b % 64)) #% 2**64
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 208:  # op.shlo_r_64
                        self.reg[r_d] = riscv_div(w_a, 2**(w_b % 64))
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 209:  # op.shar_r_64
                        self.reg[r_d] = pvm_Z_inv(
                            riscv_div(
                                pvm_Z(w_a, 8),
                                2**(w_b % 64)
                            ),
                            8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 210:  # op._and
                        self.reg[r_d] = self.reg[r_a] & self.reg[r_b]
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 211:  # op.xor
                        self.reg[r_d] = self.reg[r_a] ^ self.reg[r_b]
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 212:  # op._or
                        self.reg[r_d] = self.reg[r_a] | self.reg[r_b]
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 213:  # op.mul_upper_s_s
                        self.reg[r_d] = pvm_Z_inv(
                            riscv_div((pvm_Z(w_a, 8) * pvm_Z(w_b, 8)), 2**64),
                            8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 214:  # op.mul_upper_u_u
                        self.reg[r_d] = riscv_div(int(w_a) * int(w_b), 2**64)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 215:  # op.mul_upper_s_u
                        self.reg[r_d] = pvm_Z_inv(
                            riscv_div(pvm_Z(w_a, 8) * int(w_b), 2**64),
                            8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 216:  # op.set_lt_u
                        self.reg[r_d] = np.uint64(w_a < w_b)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 217:  # op.set_lt_s
                        self.reg[r_d] = np.int64(pvm_Z(w_a, 8) < pvm_Z(w_b,8))
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 218:  # op.cmov_iz
                        if w_b == 0:
                            self.reg[r_d] = w_a
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 219:  # op.cmov_nz
                        if w_b != 0:
                            self.reg[r_d] = w_a
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 220:  # op.rot_l_64
                        self.reg[r_d] = roli64(w_a, w_b % 64)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 221:  # op.rot_l_32
                        self.reg[r_d] = pvm_X(roli32(np.uint32(w_a), w_b % 32), 4)
                        #self.log and #self.log(reg1=r_a, reg2=r_b, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 222:  # op.rot_r_64
                        self.reg[r_d] = rori64(w_a, w_b % 64)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 223:  # op.rot_r_32
                        self.reg[r_d] = pvm_X(rori32(np.uint32(w_a), w_b % 32), 4)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 224:  # op.and_inv
                        self.reg[r_d] = w_a & ~w_b
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 225:  # op.or_inv
                        self.reg[r_d] = w_a | ~w_b
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 226:  # op.xnor
                        self.reg[r_d] = np.uint64(~(w_a ^ w_b))
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 227:  # op._max
                        #TODO: should probably just cast to np.uint64 <-> np.int64 ??
                        self.reg[r_d] = pvm_Z_inv(
                            max(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                            8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 228:  # op.max_u
                        self.reg[r_d] = max(w_a,  w_b)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 229:  # op._min
                        self.reg[r_d] = pvm_Z_inv(
                            min(pvm_Z(w_a, 8), pvm_Z(w_b, 8)),
                            8
                        )
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    elif opcode == 230:  # op.min_u
                        self.reg[r_d] = min(w_a,  w_b)
                        #self.log and #self.log(reg1=r_d, reg2=r_a, reg3=r_d, context={"w'_d": self.reg[r_d]})

                    else:
                        raise InvalidOpcode(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                else:
                    raise InvalidOpcode(f"Invalid instruction type: {inst_type}")

            except PVMMemoryError:
                self.status = ExitReason.page_fault.value
                # self.gas -= 1
                self.exit_value = self.mem._mem_addr
                break

            except PanicError as panic_error:
                self.status = ExitReason.panic.value
            
            # If single-step mode, exit after one instruction  
            if single_step:
                # In single-step mode, we need to manually advance PC for the next instruction
                # since the advancement happens at the start of the loop
                # Apply the skip_len that was just calculated for the next instruction
                # But only if we haven't hit a terminating condition
                if self.status == ExitReason.resume.value:
                    self.pc = int(self.pc) + self.skip_len
                break
