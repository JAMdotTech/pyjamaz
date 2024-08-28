import numpy as np

from .opcodes import Opcode as op, OpcodeScheme, InstructionType


class PVM:

    def __init__(self, program, mem_size=4000):
        """
        Stub implementation of the PVM
        """
        self.reg = np.zeros(16, dtype=np.int32)
        self.pc = np.uint32(0)
        self.gas = np.uint32(0)
        self.mem = np.zeros(mem_size, dtype=np.uint8)
        # TODO: self.status = "trap"
        # TODO: self.jump_tables = np.array(program.code, dtype=np.int8)
        self.code = np.array(program.code, dtype=np.uint8)
        self.program_size = len(self.code)

    def initialize(self, initial_regs, initial_pc, initial_gas):
        """
        Initializes the PVM

        Parameters
        ----------
        initial_regs
        initial_pc
        initial_gas

        Returns
        -------

        """
        self.reg = np.array(initial_regs, dtype=np.int32)
        self.pc = np.uint32(initial_pc)
        self.gas = np.uint32(initial_gas)

    """
    def write_i32(s, x, addr):
        for i in range(4): s.mem[addr + i] = (x >> (8 * i)) & 0xff

    def read_i32(s, addr):
        #TODO: kunnen we niet niet altijd uitgaan van bytes in mem? -> gezien de input?
        byte0 = s.mem[addr + 0] & 0xFF
        byte1 = s.mem[addr + 1] & 0xFF
        byte2 = s.mem[addr + 2] & 0xFF
        byte3 = s.mem[addr + 3] & 0xFF
        return (byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0    
    """

    def invoke(self):

        while self.pc < self.program_size and self.gas > 0:

            opcode = self.code[self.pc]
            inst_type = OpcodeScheme[opcode]

            match inst_type:
                case InstructionType.reg_reg_reg:

                    r_a = self.code[self.pc + 1] % 16
                    r_b = self.code[self.pc + 1] // 16
                    r_d = self.code[self.pc + 2]
                    self.pc += 3

                    match opcode:
                        # TODO: lookup voor gas usage
                        case op.add.value:
                            self.gas -= 2
                            self.reg[r_d] = self.reg[r_a] + self.reg[r_b]
                        case op.sub.value:
                            self.gas -= 2
                            self.reg[r_d] = self.reg[r_a] - self.reg[r_b]
                        case op._or.value:
                            self.gas -= 2
                            self.reg[r_d] = self.reg[r_a] | self.reg[r_b]

                        case _:
                            raise Exception(f"Invalid opcode: {opcode} for instruction type {inst_type}")
                case _:
                    raise Exception(f"Invalid instruction type: {inst_type}")



        self.status = "trap"