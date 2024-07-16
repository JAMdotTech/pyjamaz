class PVM:
    def __init__(self):
        self.regs = []
        self.pc = 0
        self.gas = 0
        self.memory = []
        self.status = "trap"
        self.program = []

    def initialize(self, initial_regs, initial_pc, initial_gas):
        self.regs = initial_regs[:]
        self.pc = initial_pc
        self.gas = initial_gas

    def fetch(self):
        if self.pc + 2 >= len(self.program):
            return None, None

        instruction_length = self.program[self.pc]

        new_pc = self.pc + instruction_length
        output = self.program[self.pc + 1], self.program[self.pc + 2: self.pc + 3 + instruction_length]
        self.pc = new_pc
        return output

    def decode(self, opcode):
        if opcode == 8:
            return "ADD"
        if opcode == 8:
            return "ADD"
        elif opcode == 9:
            return "SUB"
        elif opcode == 10:
            return "MUL"
        elif opcode == 11:
            return "DIV"
        elif opcode == 12:
            return "MOD"
        elif opcode == 13:
            return "AND"
        elif opcode == 14:
            return "OR"
        elif opcode == 15:
            return "XOR"
        elif opcode == 16:
            return "NOT"
        elif opcode == 17:
            return "SHL"
        elif opcode == 18:
            return "SHR"
        elif opcode == 19:
            return "LOAD"
        elif opcode == 20:
            return "STORE"
        return "UNKNOWN"

    def execute(self, instruction):
        if instruction == "ADD":
            self.regs[9] = self.regs[7] + self.regs[8]
            self.gas -= 2
        if instruction == "ADD":
            self.regs[9] = self.regs[7] + self.regs[8]
        elif instruction == "SUB":
            self.regs[9] = self.regs[7] - self.regs[8]
        elif instruction == "MUL":
            self.regs[9] = self.regs[7] * self.regs[8]
        elif instruction == "DIV":
            self.regs[9] = self.regs[7] // self.regs[8]
        elif instruction == "MOD":
            self.regs[9] = self.regs[7] % self.regs[8]
        elif instruction == "AND":
            self.regs[9] = self.regs[7] & self.regs[8]
        elif instruction == "OR":
            self.regs[9] = self.regs[7] | self.regs[8]
        elif instruction == "XOR":
            self.regs[9] = self.regs[7] ^ self.regs[8]
        elif instruction == "NOT":
            self.regs[9] = ~self.regs[7]
        elif instruction == "SHL":
            self.regs[9] = self.regs[7] << self.regs[8]
        elif instruction == "SHR":
            self.regs[9] = self.regs[7] >> self.regs[8]
        elif instruction == "LOAD":
            self.regs[9] = self.memory[self.regs[7]]
        elif instruction == "STORE":
            self.memory[self.regs[7]] = self.regs[8]
        else:
            raise Exception("Unknown instruction")

    def run(self, program):
        scale_encoded = program[0]
        dyn_jump_table = program[1]

        self.program = program[2:]

        while self.gas > 0:
            opcode, _ = self.fetch()
            if opcode is None:
                break
            instruction = self.decode(opcode)
            self.execute(instruction)

