import numpy as np

from .opcodes import Opcode as op, OpcodeScheme, InstructionType


class PVM:

    def __init__(self, program, mem_size=4096):
        """
        Stub implementation of the PVM
        """
        self.reg = np.zeros(16, dtype=np.uint32)
        self.pc = np.uint32(0)
        self.gas = np.uint32(0)
        self.mem = np.zeros(mem_size, dtype=np.uint8)
        # TODO: self.status = "trap"
        # TODO: self.jump_tables = np.array(program.code, dtype=np.int8)
        self.rom = np.array(program.code, dtype=np.uint8)   #TODO: program.code -> program.rom
        self.program_bitmask = program.checksum
        self.program_size = len(self.rom)

        self.status = "none"
        self.trap = False

    def initialize(self, initial_regs, initial_pc, initial_gas, initial_page_map, initial_memory):
        """
        Initializes the PVM

        Parameters
        ----------
        initial_regs
        initial_pc
        initial_gas
        initial_page_map
        initial_memory

        Returns
        -------

        """
        self.reg = np.array(initial_regs, dtype=np.uint32)
        self.pc = np.uint32(initial_pc)
        self.gas = np.uint32(initial_gas)
        #TODO: initial_page_map.address, length, is-writable
        if initial_memory:
            for block_idx, mem_block in enumerate(initial_memory):
                for idx, byt in enumerate(mem_block["contents"]):
                    self.mem[initial_page_map[block_idx]["address"] - mem_block["address"] + idx] = np.uint8(byt)

    """
    #TODO: typings
    def write_i32(s, value, addr):
        #for i in range(4): s.mem[addr + i] = (x >> (8 * i)) & 0xff
        s.mem[addr + 0] = np.uint8(value >> (8 * 0))
        s.mem[addr + 1] = np.uint8(value >> (8 * 1))
        s.mem[addr + 2] = np.uint8(value >> (8 * 2))
        s.mem[addr + 3] = np.uint8(value >> (8 * 3))
    """

    # TODO: typings
    def read_i16(s, source, addr):
        byte0 = np.uint16(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        return np.int32((byte1 << 8) + byte0)

    # TODO: typings
    def read_u16(s, source, addr):
        byte0 = np.uint16(source[addr + 0])
        byte1 = np.uint16(source[addr + 1])
        return (byte1 << 8) + byte0

    #TODO: typings
    def read_i32(s, source, addr):
        byte0 = np.uint32(source[addr + 0])
        byte1 = np.uint32(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        byte3 = np.uint32(source[addr + 3])
        return np.int32((byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0)

    #TODO: typings
    def read_u32(s, source, addr):
        byte0 = np.uint32(source[addr + 0])
        byte1 = np.uint32(source[addr + 1])
        byte2 = np.uint32(source[addr + 2])
        byte3 = np.uint32(source[addr + 3])
        return (byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0

    def invoke(self):

        while True:

            if self.pc >= self.program_size:
                self.trap = True

            if self.trap:
                self.status = "trap"
                break

            if self.gas <= 0:
                #TODO
                self.status = "trap"
                break

            opcode = self.rom[self.pc]
            inst_type = OpcodeScheme[opcode]

            match inst_type:

                case InstructionType.none:

                    match opcode:
                        case op.trap.value:
                            self.pc = self.program_size
                        case op.fallthrough.value:
                            self.gas -= 2
                            self.pc += 1

                case InstructionType.reg_imm:
                    r_a = self.rom[self.pc + 1]
                    imm = self.rom[self.pc + 2]
                    self.gas -= 2
                    self.pc += 2 # note: we read 1 opcode byte plus two instruction bytes (zero based index)

                    match opcode:
                        #case op.jump_indirect.value:   #TODO:NO_TEST

                        case op.load_imm.value:
                            self.reg[r_a] = self.read_i32(self.rom, self.pc)
                            self.pc += 4 # note, we read 4 mem bytes

                        case op.load_u8.value:
                            if imm >= len(self.mem):
                                self.trap = True
                                self.pc = 0
                                continue

                            self.reg[r_a] = self.mem[imm]
                            self.pc += 1 # note: we read 1 mem byte

                        #TODO:NO_TEST: case op.load_i8.value:
                        #     self.reg[r_a] = np.int8(self.mem[imm])
                        #     self.pc += 1 # note: we read 1 mem byte

                        #TODO:NO_TEST: case op.load_i16.value:
                        #     self.reg[r_a] = self.read_int16(self.mem, imm)
                        #     self.pc += 2 # note: we read 2 mem byte

                        #TODO:NO_TEST: case op.load_u16.value:
                        #     self.reg[r_a] = self.read_uint16(self.mem, imm)
                        #     self.pc += 2 # note: we read 2 mem byte

                        case op.store_u8.value:
                            if imm >= len(self.mem):
                                self.trap = True
                                self.pc = 0
                                continue

                            self.mem[imm] = np.uint8(self.reg[r_a] & 0xFF)
                            self.pc += 1 # note: we read 1 mem byte

                        case op.store_u16.value:
                            if imm >= len(self.mem)-1:
                                self.trap = True
                                self.pc = 0
                                continue

                            self.mem[imm + 0] = np.uint8(self.reg[r_a] & 0xFF)
                            self.mem[imm + 1] = np.uint8((self.reg[r_a] & 0xFF00) >> 8)
                            self.pc += 1 # note: we read 1 mem byte

                        case op.store_u32.value:
                            if imm >= len(self.mem)-3:
                                self.trap = True
                                self.pc = 0
                                continue

                            self.mem[imm + 0] = np.uint8(self.reg[r_a] & 0xFF)
                            self.mem[imm + 1] = np.uint8((self.reg[r_a] & 0xFF00) >> 8)
                            self.mem[imm + 2] = np.uint8((self.reg[r_a] & 0xFF0000) >> 16)
                            self.mem[imm + 3] = np.uint8((self.reg[r_a] & 0xFF000000) >> 24)
                            self.pc += 1 # note: we read 1 mem byte

                        case _:
                            raise Exception(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                #TODO: wtf!!!?
                # case InstructionType.reg_imm_offset:
                #     r_a = self.rom[self.pc + 1]
                #     imm = self.rom[self.pc + 2]
                #     off = self.rom[self.pc + 3]
                #     self.gas -= 2
                #     self.pc += 3 # note: we read 1 opcode byte plus three instruction bytes (zero based index)
                #
                #     match opcode:
                #         #TODO:NO_TEST: case op.load_imm_and_jump.value:
                #         case op.branch_eq_imm.value:
                #             if

                #TODO:NO_TEST: case InstructionType.reg_imm_imm:

                case InstructionType.reg_reg_imm:

                    r_d = self.rom[self.pc + 1] % 16
                    r_a = self.rom[self.pc + 1] // 16
                    imm = self.rom[self.pc + 2]
                    self.gas -= 2
                    self.pc += 3 # note: we read 1 opcode byte plus three instruction bytes (zero based index)

                    match opcode:

                        #TODO:NO_TEST: case op.store_indirect_u8.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.store_indirect_u16.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.store_indirect_u32.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.load_indirect_u8.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.load_indirect_i8.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.load_indirect_u16.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.load_indirect_i16.value: it.reg_reg_imm,
                        #TODO:NO_TEST: case op.load_indirect_u32.value: it.reg_reg_imm,

                        case op.add_imm.value:
                            self.reg[r_d] = self.reg[r_a] + imm

                        case op.and_imm.value:
                            self.reg[r_d] = self.reg[r_a] & imm

                        case op.xor_imm.value:
                            self.reg[r_d] = self.reg[r_a] ^ imm

                        case op.or_imm.value:
                            self.reg[r_d] = self.reg[r_a] | imm

                        case op.mul_imm.value:
                            #TODO: check op overflow? alle add/mul/div ops?
                            self.reg[r_d] = self.reg[r_a] * imm

                        case op.shift_arithmetic_right_imm.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) >> imm

                        case op.shift_logical_right_imm.value:
                            self.reg[r_d] = self.reg[r_a] >> imm

                        #TODO: bestaat niet???
                        # case op.shift_arithmetic_left_imm.value:
                        #     self.reg[r_d] = np.int32(self.reg[r_a]) << imm

                        case op.shift_logical_left_imm.value:
                            self.reg[r_d] = self.reg[r_a] << imm

                        case op.shift_arithmetic_right_imm_alt.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) >> imm

                        case op.shift_logical_right_imm_alt.value:
                            self.reg[r_d] = self.reg[r_a] >> imm


                case InstructionType.reg_reg_reg:

                    r_a = self.rom[self.pc + 1] % 16
                    r_b = self.rom[self.pc + 1] // 16
                    r_d = self.rom[self.pc + 2]
                    self.pc += 3 # note: we read 1 opcode byte plus three instruction bytes (zero based index)
                    self.gas -= 2

                    match opcode:
                        case op.add.value:
                            self.reg[r_d] = self.reg[r_a] + self.reg[r_b]

                        case op.sub.value:
                            self.reg[r_d] = self.reg[r_a] - self.reg[r_b]

                        case op._and.value:
                            self.reg[r_d] = self.reg[r_a] & self.reg[r_b]

                        case op.xor.value:
                            self.reg[r_d] = self.reg[r_a] ^ self.reg[r_b]

                        case op._or.value:
                            self.reg[r_d] = self.reg[r_a] | self.reg[r_b]

                        case op.mul.value:
                            self.reg[r_d] = self.reg[r_a] * self.reg[r_b]

                        #TODO:NO_TEST: case op.mul_upper_signed_signed.value:

                        #TODO:NO_TEST: case op.mul_upper_unsigned_unsigned.value:

                        #TODO:NO_TEST: case op.mul_upper_signed_unsigned.value:

                        case op.set_less_than_unsigned.value:
                            self.reg[r_d] = self.reg[r_a] < self.reg[r_b]

                        case op.set_less_than_signed.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) < np.int32(self.reg[r_b])
                        # Shift (note: 0x1f ensures that only the 5 LSBs are used as shift-amount)
                        # (For rv64, we would use the 6 LSBs, so 0x3f)

                        case op.shift_logical_left.value:
                            self.reg[r_d] = self.reg[r_a] << (self.reg[r_b] & 0x1f)

                        case op.shift_logical_right.value:
                            self.reg[r_d] = self.reg[r_a] >> (self.reg[r_b] & 0x1f)

                        case op.shift_arithmetic_right.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) >> np.int32(self.reg[r_b] & 0x1f)

                        case op.div_unsigned.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = 0xffffffff
                            else:
                                self.reg[r_d] = np.fix(self.reg[r_a] / self.reg[r_b]).astype(int)

                        case op.div_signed.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = np.int32(-1)
                            #TODO: edge case?:
                            # elif self.reg[r_a] == 0x7FFFFFFF and self.reg[r_b] == -1:
                            #     self.reg[r_d] = 0
                            else:
                                self.reg[r_d] = np.fix(np.int32(self.reg[r_a]) / np.int32(self.reg[r_b])).astype(int)

                        case op.rem_signed.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = self.reg[r_a]
                            #TODO: edge case?:
                            # elif self.reg[r_a] == 0x7FFFFFFF and self.reg[r_b] == -1:
                            #     self.reg[r_d] = 0
                            else:
                                divr = np.fix(np.int32(self.reg[r_a]) / np.int32(self.reg[r_b])).astype(int)
                                a = np.int32(self.reg[r_a])
                                b = np.int32(self.reg[r_b])
                                self.reg[r_d] = a - b * divr

                        case op.rem_unsigned.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = self.reg[r_a]
                            else:
                                divr = np.fix(self.reg[r_a] / self.reg[r_b]).astype(int)
                                self.reg[r_d] = self.reg[r_a] - self.reg[r_b] * divr

                        case op.cmov_if_zero.value:
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = self.reg[r_a]

                        #case op.cmov_if_not_zero.value: #TODO:NO_TEST

                        case _:
                            raise Exception(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                case _:
                    raise Exception(f"Invalid instruction type: {inst_type}")
