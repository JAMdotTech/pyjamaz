import numpy as np

from .opcodes import Opcode as op, OpcodeScheme, InstructionType, BITMASK_MAX


#gp_0.3.6_eq_223
def sign_extend(x,n):
    term = (2 ** 32 - 2 ** (8 * n))
    factor = x // (2 ** (8 * n - 1))
    return x + factor * term


def transform_signed(a, n):
    boundary = 2 ** (8 * n - 1)
    if a < boundary:
        return a
    else:
        return a - 2 ** (8 * n)


class PVM:

    def __init__(self, program, mem_size=4096):
        self.reg = np.zeros(13, dtype=np.uint32)
        self.pc = np.uint32(0)
        self.gas = np.uint32(0)
        self.mem = np.zeros(mem_size, dtype=np.uint8)
        # TODO: self.jump_tables = np.array(program.code, dtype=np.int8)
        self.rom = np.array(program.code, dtype=np.uint8)
        self.program_size = len(self.rom)
        self.inst_bitmask = program.opcode_bitmask
        self.inst_pos = {0: 0}
        self.inst_len = []
        self.trap = 0   #TODO: lookup maken voor mogelijke trap exit codes

    def create_instruction_lookup(self):
        self.inst_pos = {0: 0}
        self.inst_len = []

        inst_nr = 0
        inst_bitmask = self.inst_bitmask
        inst_bitmask_idx = 1

        # Note: In the exceptional case we only have 1 instruction (trap or fallthrough), we add it manually and be done
        if len(inst_bitmask) == 1:
            self.inst_len.append(0)
            return

        # Parse instruction bitmask and create a opcode offset and instruction length lookup
        while inst_bitmask_idx < len(inst_bitmask):
            inst_args = 0

            # Note: wellicht willen we deze later als numpy typen definieeren, dus voor nu hier alvast gedefinieerd
            is_opcode = False

            while not is_opcode:

                is_opcode = inst_bitmask[inst_bitmask_idx]
                if not is_opcode:
                    inst_args += 1

                inst_bitmask_idx += 1

                if inst_bitmask_idx > len(inst_bitmask) - 1:
                    is_opcode = True

            self.inst_len.append(inst_args)
            inst_nr += 1
            self.inst_pos[inst_bitmask_idx - 1] = inst_nr
            # print(f"added instruction {len(self.inst_len) - 1} (byte {op_bit_idx-1} == opcode {self.inst_pos[op_bit_idx-1]}) with args {op_args} (next byte: {op_bit_idx - 1})")


    def initialize(self, initial_regs, initial_pc, initial_gas, initial_page_map, initial_memory):
        self.reg = np.array(initial_regs, dtype=np.uint32)
        self.pc = np.uint32(initial_pc)
        self.gas = np.uint32(initial_gas)
        #TODO: initial_page_map.address, length, is-writable
        self.mem_offset = 0
        if initial_page_map:
            self.mem_offset = initial_page_map[0]["address"]    #TODO: memory addressing uitwerken
        if initial_memory:
            for block_idx, mem_block in enumerate(initial_memory):
                for idx, byt in enumerate(mem_block["contents"]):
                    self.mem[initial_page_map[block_idx]["address"] - mem_block["address"] + idx] = np.uint8(byt)

        self.create_instruction_lookup()


    # TODO: typings
    def read_uint(s, source, addr, l):
        if l == 1:
            return np.uint32(source[addr + 0])
        elif l == 2:
            byte0 = np.uint8(source[addr + 0])
            byte1 = np.uint16(source[addr + 1])
            return np.uint32((byte1 << 8) + byte0)
        elif l == 3:
            byte0 = np.uint8(source[addr + 0])
            byte1 = np.uint16(source[addr + 1])
            byte2 = np.uint32(source[addr + 2])
            return np.uint32((byte2 << 16) + (byte1 << 8) + byte0)
        elif l == 4:
            byte0 = np.uint8(source[addr + 0])
            byte1 = np.uint16(source[addr + 1])
            byte2 = np.uint32(source[addr + 2])
            byte3 = np.uint32(source[addr + 3])
            return np.uint32((byte3 << 24) + (byte2 << 16) + (byte1 << 8) + byte0)
        else:
            raise Exception(f"Invalid uint length: {l}")

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

    #TODO: typings
    def read_mem(s, addr):
        mapped_addr = addr - s.mem_offset
        if mapped_addr >= len(s.mem):
            s.trap = 1
            return 0
        return s.mem[mapped_addr]

    def invoke(self):

        self.pc = 0
        skip_len = 0

        while self.trap == 0 and self.gas > 0:

            self.gas -= 1
            self.pc += skip_len

            if self.pc >= self.program_size:
                self.trap = 1
                break

            inst_index = self.inst_pos[self.pc]
            opcode = self.rom[self.pc]
            inst_type = OpcodeScheme[opcode]
            skip_len = self.inst_len[inst_index] + 1

            #TODO:!!!!!!!!!!!!!!!!allo op. instructies prefixen met i_ en dan de GP benaming voor de operator!!!!
            match inst_type:

                case InstructionType.none:

                    match opcode:
                        case op.trap.value:
                            self.trap = 1
                        case op.fallthrough.value:
                            pass

                case InstructionType.reg_imm:
                    r_a = self.rom[self.pc + 1] % 16
                    #w_a = self.reg[r_a]
                    l_x = min(4, max(0, skip_len - 2) )
                    v_x = sign_extend(self.read_uint(self.rom, self.pc + 2, l_x), l_x)

                    # Note: in case of an immediate, we dont have to check memory access
                    if opcode != op.load_imm.value:
                        mapped_addr = v_x - self.mem_offset
                        if mapped_addr >= len(self.mem):
                            #TODO:!!!!!!!!!!!!!!!!!!!dit moet ook netter kunnen
                            self.trap = 1
                            self.gas -= 1
                            continue

                    match opcode:
                        #case op.jump_indirect.value:   #TODO:NO_TEST

                        case op.load_imm.value:
                            self.reg[r_a] = v_x

                        case op.load_u8.value:
                            self.reg[r_a] = self.mem[mapped_addr]

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
                            self.mem[mapped_addr] = np.uint8(self.reg[r_a] & 0xFF)

                        case op.store_u16.value:
                            self.mem[mapped_addr + 0] = np.uint8(self.reg[r_a] & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((self.reg[r_a] & 0xFF00) >> 8)

                        case op.store_u32.value:
                            self.mem[mapped_addr + 0] = np.uint8(self.reg[r_a] & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((self.reg[r_a] & 0xFF00) >> 8)
                            self.mem[mapped_addr + 2] = np.uint8((self.reg[r_a] & 0xFF0000) >> 16)
                            self.mem[mapped_addr + 3] = np.uint8((self.reg[r_a] & 0xFF000000) >> 24)

                        case _:
                            raise Exception(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                case InstructionType.reg_imm_offset:
                    r_a = self.rom[self.pc + 1] % 16
                    w_a = self.reg[r_a]
                    l_x = min(4, (self.rom[self.pc + 1] // 16) % 8)
                    v_x = self.read_uint(self.rom, self.pc + 2, l_x)
                    l_y = skip_len - l_x - 2
                    # TODO: mag ook negatief zijn? zie gp_3.0.6_eq_219&220
                    # impl helper func Z_l_y
                    v_y = transform_signed(self.read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    match opcode:
                        #TODO:NO_TEST: case op.load_imm_and_jump.value:

                        case op.branch_eq_imm.value:
                            if w_a == v_x:
                                skip_len = v_y

                        case op.branch_not_eq_imm.value:
                            if w_a != v_x:
                                skip_len = v_y

                        case op.branch_less_unsigned_imm.value:
                            if w_a < v_x:
                                skip_len = v_y

                        case op.branch_greater_or_equal_unsigned_imm.value:
                            if w_a >= v_x:
                                skip_len = v_y

                        case op.branch_less_or_equal_unsigned_imm.value:
                            if w_a <= v_x:
                                skip_len = v_y

                        case op.branch_greater_unsigned_imm.value:
                            if w_a > v_x:
                                skip_len = v_y

                        case op.branch_less_signed_imm.value:
                            if transform_signed(w_a, 4) < transform_signed(v_x, 4):
                                skip_len = v_y

                        case op.branch_greater_or_equal_signed_imm.value:
                            if transform_signed(w_a, 4) >= transform_signed(v_x, 4):
                                skip_len = v_y

                        case op.branch_less_or_equal_signed_imm.value:
                            if transform_signed(w_a, 4) <= transform_signed(v_x, 4):
                                skip_len = v_y

                        case op.branch_greater_signed_imm.value:
                            if transform_signed(w_a, 4) > transform_signed(v_x, 4):
                                skip_len = v_y

                        case _:
                            raise Exception(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")

                #TODO:NO_TEST: case InstructionType.reg_imm_imm:

                case InstructionType.reg_reg_imm:

                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)
                    w_b = self.reg[r_b]
                    l_x = min(4, max(0, skip_len - 2) )
                    v_x = sign_extend(self.read_uint(self.rom, self.pc + 2, l_x), l_x)

                    #TODO:!!!!!!!!!!!!! check de overflow flags

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
                            self.reg[r_a] = (w_b + v_x) #% 2**31

                        case op.and_imm.value:
                            self.reg[r_a] = w_b & v_x

                        case op.xor_imm.value:
                            self.reg[r_a] = w_b ^ v_x

                        case op.or_imm.value:
                            self.reg[r_a] = w_b | v_x

                        case op.mul_imm.value:
                            #TODO: check op overflow? alle add/mul/div ops?
                            self.reg[r_a] = w_b * v_x

                        case op.shift_arithmetic_right_imm.value:
                            self.reg[r_a] = np.int32(w_b) >> v_x

                        case op.shift_logical_right_imm.value:
                            self.reg[r_a] = w_b >> v_x

                        #TODO: bestaat niet???
                        # case op.shift_arithmetic_left_imm.value:
                        #     self.reg[r_d] = np.int32(self.reg[r_a]) << imm

                        case op.shift_logical_left_imm.value:
                            self.reg[r_a] = (w_b * (2**v_x % 32)) % 2**31

                        case op.shift_arithmetic_right_imm_alt.value:
                            self.reg[r_a] = w_b >> v_x #np.int32(w_b) >> v_x

                        case op.shift_logical_right_imm_alt.value:
                            self.reg[r_a] = w_b >> v_x


                case InstructionType.reg_reg_reg:

                    r_a = self.rom[self.pc + 1] % 16
                    r_b = self.rom[self.pc + 1] // 16
                    r_d = self.rom[self.pc + 2]
                    #self.pc += 3 # note: we read 1 opcode byte plus three instruction bytes (zero based index)

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
