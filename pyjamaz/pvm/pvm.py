from math import floor
from typing import Any, List, Dict

import numpy as np
import numpy.typing as npt

from .exceptions import InvalidOpcode
from .types import PVMProgram

from .utils import (
    pvm_Z,
    pvm_X,
    pvm_Z_inv,
    read_uint,
    write_uint,
    count_trailing_zeroes,
    count_leading_zeroes,
    reverse_bytes,
    rori64,
    rori32,
    pvm_floor_div,
    pvm_mod
)

from .constants import (
    Opcode as op,
    OpcodeScheme,
    InstructionType,
    ExitCondition,
    MemOps,
)


class PVM:

    def __init__(self):
        self.reg = np.zeros(13, dtype=np.uint64)
        self.pc:np.uint32 = np.uint32(0)
        self.gas:np.uint64 = np.uint64(0)
        self.mem:npt.NDArray[np.uint8] = np.zeros(1, dtype=np.uint8)
        self.jump_table = []
        self.rom:npt.NDArray[np.uint8] = np.array(1, dtype=np.uint8)
        self.program_size: np.uint64 = np.uint64(0)
        self.inst_bitmask: List[bool] = []
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_len: List[int] = []
        self.status = ExitCondition.none.value


    def create_instruction_lookup(self):
        """
        Create lookups for byte_pos -> instruction_nr and instruction_nr->instruction_length
        """
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


    def reset(
            self,
            program: PVMProgram,
            initial_regs: list[int],
            initial_pc: int,
            initial_gas: int,
            initial_page_map: list[Any],
            initial_memory: list[Any],
            mem_size: np.uint32 = 4096,
            mem_offset: np.uint32 = 0
    ):
        self.mem:npt.NDArray[np.uint8] = np.zeros(mem_size, dtype=np.uint8)
        self.rom:npt.NDArray[np.uint8] = np.array(program.code, dtype=np.uint8)
        self.program_size: np.uint64 = np.uint64(len(self.rom))
        self.inst_bitmask: List[bool] = program.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_len: List[int] = []
        self.reg = np.array(initial_regs, dtype=np.uint64)
        self.pc = np.uint32(initial_pc)
        self.gas = np.uint64(initial_gas)
        self.status = ExitCondition.none.value

        self.jump_table = [x.value for x in program.jump_table]

        #TODO: initial_page_map.address, length, is-writable
        self.mem_offset = mem_offset
        if initial_page_map:
            self.mem_offset = initial_page_map[0]["address"]    #TODO: memory addressing uitwerken
            for idx in range(initial_page_map[0]["length"]):
                self.mem[idx] = np.uint8(0)

        if initial_memory:
            for block_idx, mem_block in enumerate(initial_memory):
                for idx, byt in enumerate(mem_block["contents"]):
                    self.mem[initial_page_map[block_idx]["address"] - mem_block["address"] + idx] = np.uint8(byt)

        self.create_instruction_lookup()

    def check_mem_op(self, op: int, mapped_addr: int):
        valid_op = True
        bytes_needed = MemOps[op]["bytes"]
        if mapped_addr+bytes_needed > len(self.mem):
            valid_op = False
        # TODO: register writable&readable memory banks
        #if MemOps[op]["read"]:
        #if MemOps[op]["write"]:
        # if write_value:
        #     if mapped_addr + (write_value.bit_length() + 7) // 8 > len(self.mem):
        #         valid_op = False

        if not valid_op:
            self.status = ExitCondition.page_fault.value
            self.gas -= 1

        return valid_op

    # GP_A.15
    def djump(self, a: int):
        Z_a = 2  # TODO: add to constants
        if a == np.uint64(2 ** 32 - 2 ** 16):
            self.status = ExitCondition.halt.value
        elif a == 0 or a > len(self.jump_table) * Z_a or a % Z_a != 0:  # or self.jump_table[a//Z_a-1]:
            self.status = ExitCondition.panic.value
        else:
            return self.jump_table[a//Z_a-1] - self.pc

    def invoke(
        self,
        program: PVMProgram,
        initial_regs: list[int],
        initial_pc: int,
        initial_gas: int,
        initial_page_map: list[Any],
        initial_memory: list[Any],
        mem_size: np.uint32 = 4096,
        mem_offset: np.uint32 = 0
    ):

        self.reset(
            program,
            initial_regs,
            initial_pc,
            initial_gas,
            initial_page_map,
            initial_memory,
            mem_size,
            mem_offset
        )

        #self.pc = 0
        skip_len:int = 0

        while self.status == ExitCondition.none.value and self.gas > 0:

            self.gas -= 1
            self.pc += skip_len

            #gp_0.3.6-eq:215
            if self.pc >= self.program_size:
                self.status = ExitCondition.panic.value
                break

            inst_index = self.inst_pos[self.pc]
            opcode = self.rom[self.pc]
            inst_type = OpcodeScheme[opcode]
            skip_len = self.inst_len[inst_index] + 1

            match inst_type:

                #GP_A.5.1
                case InstructionType.none:

                    match opcode:
                        case op.trap.value:
                            self.status = ExitCondition.panic.value
                        case op.fallthrough.value:
                            pass

                        case _:
                            raise InvalidOpcode(f"Invalid noargs opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.2
                case InstructionType.imm:

                    match opcode:
                        case op.ecalli.value:
                            l_x = min(4, max(0, skip_len - 2))
                            #TODO: ook l_x == 0 check?
                            v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)
                            self.status = ExitCondition.host_halt.value
                            self.invoke_host_call(v_x)

                        case _:
                            raise InvalidOpcode(f"Invalid imm opcode: {opcode} for instruction type {inst_type}")

                #GP_A.5.3
                case InstructionType.reg_ext_imm:

                    match opcode:
                        case op.load_imm_64.value:
                            r_a = min(12, self.rom[self.pc + 1] % 16)
                            v_x = read_uint(self.rom, self.pc + 2, 8)
                            self.reg[r_a] = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid reg_ext_imm opcode: {opcode} for instruction type {inst_type}")

                #GP_A.5.4
                case InstructionType.imm_imm:

                    l_x = min(4, self.rom[self.pc + 1] % 8)
                    l_y = min(4, max(0, skip_len - l_x - 2))
                    #TODO: ook l_x == 0 check
                    v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)
                    v_y = pvm_X(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    mapped_addr = v_x - self.mem_offset
                    if opcode in MemOps and not self.check_mem_op(opcode, mapped_addr):
                        continue

                    match opcode:
                        case op.store_imm_u8.value:
                            write_uint(self.mem, self.reg[mapped_addr], 1, v_y % 2**8)
                        case op.store_imm_u16.value:
                            write_uint(self.mem, self.reg[mapped_addr], 2, v_y % 2**16)
                        case op.store_imm_u32.value:
                            write_uint(self.mem, self.reg[mapped_addr], 4, v_y % 2**32) #TODO: why modulus instead casting to uint32?
                        case op.store_imm_u64.value:
                            write_uint(self.mem, self.reg[mapped_addr], 8, v_y)

                        case _:
                            raise InvalidOpcode(f"Invalid imm_imm opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.5
                case InstructionType.offset:

                    #TODO: skip_len uit GP lijkt altijd voor te lopen, dus overal nalopen en -1 doen?
                    l_x = min(4, max(0, skip_len - 1) )
                    v_x = pvm_Z(read_uint(self.rom, self.pc + 1, l_x), l_x)

                    match opcode:
                        case op.jump.value:
                            skip_len = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.6
                case InstructionType.reg_imm:
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    l_x = min(4, max(0, skip_len - 2))
                    v_x = 0
                    if l_x > 0:
                        v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)

                    mapped_addr = v_x - self.mem_offset
                    if opcode in MemOps and not self.check_mem_op(opcode, mapped_addr):
                        continue

                    match opcode:
                        case op.jump_ind.value:
                            skip_len = self.djump(np.uint32(self.reg[r_a]+v_x))

                        case op.load_imm.value:
                            self.reg[r_a] = v_x

                        case op.load_u8.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 1)

                        case op.load_i8.value:
                            self.reg[r_a] = pvm_X(read_uint(self.mem, mapped_addr, 1), 1)

                        case op.load_u16.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 2)

                        case op.load_i16.value:
                            self.reg[r_a] = pvm_X(read_uint(self.mem, mapped_addr, 2), 2)

                        case op.load_u32.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 4)

                        case op.load_i32.value:
                            self.reg[r_a] = pvm_X(read_uint(self.mem, mapped_addr, 4), 4)

                        case op.load_u64.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 8)

                        case op.store_u8.value:
                            write_uint(self.mem, mapped_addr, 1, self.reg[r_a])

                        case op.store_u16.value:
                            write_uint(self.mem, mapped_addr, 2, self.reg[r_a])

                        case op.store_u32.value:
                            write_uint(self.mem, mapped_addr, 4, self.reg[r_a])

                        case op.store_u64.value:
                            write_uint(self.mem, mapped_addr, 8, self.reg[r_a])

                        case _:
                            raise InvalidOpcode(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.7
                case InstructionType.reg_imm_imm:
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    w_a = self.reg[r_a]

                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16,32 or 64)
                    l_x = min(4, (self.rom[self.pc + 1] // 16) % 8)
                    l_y = min(4, max(0, skip_len - l_x - 2))

                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    if l_x > 0:
                        v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)
                    else:
                        v_x = 0

                    #read_uint(self.rom, self.pc + 2, 2)!!!!!!
                    v_y = pvm_X(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    mapped_addr = w_a + v_x - self.mem_offset
                    if opcode in MemOps and not self.check_mem_op(opcode, mapped_addr):
                        continue

                    match opcode:

                        case op.store_imm_ind_u8.value:
                            write_uint(self.mem, mapped_addr, 1, v_y)

                        case op.store_imm_ind_u16.value:
                            write_uint(self.mem, mapped_addr, 2, v_y)

                        case op.store_imm_ind_u32.value:
                            write_uint(self.mem, mapped_addr, 4, v_y)

                        case op.store_imm_ind_u64.value:
                            write_uint(self.mem, mapped_addr, 8, v_y)

                        case _:
                            raise InvalidOpcode(f"Invalid reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.8
                case InstructionType.reg_imm_offset:
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    w_a = self.reg[r_a]
                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                    l_x = min(4, (self.rom[self.pc + 1] // 16) % 8)
                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    if l_x > 0:
                        v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)
                    else:
                        v_x = 0

                    l_y = min(4, max(0, skip_len - l_x - 2))
                    v_y = pvm_Z(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    match opcode:
                        case op.load_imm_jump.value:
                            skip_len = v_y
                            self.reg[r_a] = v_x

                        case op.branch_eq_imm.value:
                            if w_a == v_x:
                                skip_len = v_y

                        case op.branch_ne_imm.value:
                            if w_a != v_x:
                                skip_len = v_y

                        case op.branch_lt_u_imm.value:
                            if w_a < v_x:
                                skip_len = v_y

                        case op.branch_le_u_imm.value:
                            if w_a <= v_x:
                                skip_len = v_y

                        case op.branch_ge_u_imm.value:
                            if w_a >= v_x:
                                skip_len = v_y

                        case op.branch_gt_u_imm.value:
                            if w_a > v_x:
                                skip_len = v_y

                        case op.branch_lt_s_imm.value:
                            if pvm_Z(w_a, 8) < pvm_Z(v_x, 8):
                                skip_len = v_y

                        case op.branch_le_s_imm.value:
                            if pvm_Z(w_a, 8) <= pvm_Z(v_x, 8):
                                skip_len = v_y

                        case op.branch_ge_s_imm.value:
                            if pvm_Z(w_a, 8) >= pvm_Z(v_x, 8):
                                skip_len = v_y

                        case op.branch_gt_s_imm.value:
                            if pvm_Z(w_a, 8) > pvm_Z(v_x, 8):
                                skip_len = v_y

                        case _:
                            raise InvalidOpcode(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")

                #GP_A.5.9
                case InstructionType.reg_reg:

                    r_d = min(12, self.rom[self.pc + 1] % 16)
                    r_a = min(12, self.rom[self.pc + 1] // 16)

                    match opcode:
                        case op.move_reg.value:
                            self.reg[r_d] = self.reg[r_a]

                        #TODO: NO_TEST:
                        #case op.sbrk.value:
                        #!!!!!!! TODO: implementeer wanneer memory management is geimplementeerd
                        #!!!!!!! TODO: zie note in GP onderaan deze sectie

                        case op.count_set_bits_64:
                            self.reg[r_d] = np.bitwise_count(self.reg[r_a])

                        case op.count_set_bits_32:
                            self.reg[r_d] = np.bitwise_count(np.uint32(self.reg[r_a]))

                        case op.leading_zero_bits_64:
                            v = self.reg[r_a]
                            self.reg[r_d] = count_leading_zeroes(self.reg[r_a])

                        case op.leading_zero_bits_32:
                            self.reg[r_d] = count_leading_zeroes(np.uint32(self.reg[r_a]), 32)

                        case op.trailing_zero_bits_64:
                            self.reg[r_d] = count_trailing_zeroes(self.reg[r_a])

                        case op.trailing_zero_bits_32:
                            self.reg[r_d] = count_trailing_zeroes(np.uint32(self.reg[r_a]), 32)

                        case op.sign_extend_8:
                            self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a], 1), 8)

                        case op.sign_extend_16:
                            self.reg[r_d] = pvm_Z_inv(pvm_Z(self.reg[r_a], 1), 8)

                        case op.zero_extend_16:
                            self.reg[r_d] = self.reg[r_a] % 2**16

                        case op.reverse_bytes:
                            self.reg[r_d] = reverse_bytes(self.reg[r_a])

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.10
                case InstructionType.reg_reg_imm:

                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = min(4, max(0, skip_len - 2) )
                    if l_x > 0:
                        #!!!!!!!!!!!!!!!!!!!!!!!!!!!dees moet resulteren in:np.uint64(18446744073709486080)
                        #llx = l_x if l_x%2 == 0 else 4
                        t = read_uint(self.rom, self.pc + 2 , l_x)
                        v_x = pvm_X(t, l_x)
                        #v_x = pvm_X(16711681, 3)
                        #v_x = pvm_X(4294901761, 4)
                        #v_x = np.uint64(18446744073709486080)
                    else:
                        v_x = 0

                    mapped_addr = w_b + v_x - self.mem_offset
                    if opcode in MemOps and not self.check_mem_op(opcode, mapped_addr):
                        continue

                    match opcode:

                        case op.store_ind_u8.value:
                            write_uint(self.mem, mapped_addr, 1, w_a) #TODO: parameter toevoegen aan read & write functies om modulus uit te voeren

                        case op.store_ind_u16.value:
                            write_uint(self.mem, mapped_addr, 2, w_a)

                        case op.store_ind_u32.value:
                            write_uint(self.mem, mapped_addr, 4, w_a)

                        case op.store_ind_u64.value:
                            write_uint(self.mem, mapped_addr, 8, w_a)

                        case op.load_ind_u8.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 1)

                        case op.load_ind_i8.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_Z(read_uint(self.mem, mapped_addr, 1), 1), 8)

                        case op.load_ind_u16.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 2)

                        case op.load_ind_i16.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_Z(read_uint(self.mem, mapped_addr, 2), 2), 8)

                        case op.load_ind_u32.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 4)

                        case op.load_ind_i32.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_Z(read_uint(self.mem, mapped_addr, 4), 4), 8)

                        case op.load_ind_u64.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 8)

                        case op.add_imm_32.value:
                            self.reg[r_a] = pvm_X((w_b + v_x) % 2**32, 4)

                        case op.and_imm.value:
                            self.reg[r_a] = w_b & v_x

                        case op.xor_imm.value:
                            self.reg[r_a] = w_b ^ v_x

                        case op.or_imm.value:
                            self.reg[r_a] = w_b | v_x

                        case op.mul_imm_32.value:
                            self.reg[r_a] = pvm_X((w_b * v_x) % 2**32, 4)

                        case op.set_lt_u_imm.value:
                            self.reg[r_a] = w_b < v_x and 1 or 0

                        case op.set_lt_s_imm.value:
                            self.reg[r_a] = pvm_Z(w_b, 8) < pvm_Z(v_x, 8) and 1 or 0

                        case op.shlo_l_imm_32.value:
                            self.reg[r_a] = pvm_X((w_b * 2**(v_x % 32)) % 2**32, 4)

                        case op.shlo_r_imm_32.value:
                            self.reg[r_a] = pvm_X(pvm_floor_div((w_b % 2**32), (2**(v_x%32))), 4)

                        case op.shar_r_imm_32.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_floor_div(pvm_Z(w_b % 2 ** 32, 4), (2 ** (v_x % 32))), 8)

                        case op.neg_add_imm_32.value:
                            self.reg[r_a] = pvm_X((v_x + 2**32 - w_b) % 2**32, 4)

                        case op.set_gt_u_imm.value:
                            self.reg[r_a] = w_b > v_x and 1 or 0

                        case op.set_gt_s_imm.value:
                            self.reg[r_a] = pvm_Z(w_b, 8) > pvm_Z(v_x, 8) and 1 or 0

                        case op.shlo_l_imm_alt_32.value:
                            self.reg[r_a] = pvm_X((v_x * (2 ** (w_b % 32))) % 2**32, 4)

                        case op.shlo_r_imm_alt_32.value:
                            self.reg[r_a] = pvm_X(pvm_floor_div(v_x % 2**32, (2 ** (w_b % 32))), 4)

                        case op.shar_r_imm_alt_32.value:
                            self.reg[r_a] = pvm_Z_inv(
                                pvm_floor_div(
                                    pvm_Z(v_x % 2**32, 4),
                                    2 ** (w_b % 32)
                                ),
                                8
                            )

                        case op.cmov_iz_imm.value:
                            if w_b == 0:
                                self.reg[r_a] = v_x

                        case op.cmov_nz_imm.value:
                            if w_b != 0:
                                self.reg[r_a] = v_x

                        case op.add_imm_64.value:
                            self.reg[r_a] = (w_b + v_x) #% 2**64

                        case op.mul_imm_64.value:
                            self.reg[r_a] = (w_b * v_x) #% 2**64

                        case op.shlo_l_imm_64.value:
                            self.reg[r_a] = pvm_X((w_b * 2**(v_x % 64)), 8)

                        case op.shlo_r_imm_64.value:
                            self.reg[r_a] = pvm_X(pvm_floor_div(w_b, np.uint64(2**(v_x % 64))), 8)

                        case op.shar_r_imm_64.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_floor_div(pvm_Z(w_b, 8), 2**(v_x % 64)), 8)

                        case op.neg_add_imm_64.value:
                            self.reg[r_a] = ((int(v_x) + 2**64 - int(w_b)) % 2**64)

                        case op.shlo_l_imm_alt_64.value:
                            self.reg[r_a] = (v_x * 2**(w_b % 64)) #% 2**64

                        case op.shlo_r_imm_alt_64.value:
                            self.reg[r_a] = pvm_floor_div(v_x, np.uint64(2**(w_b % 64)))

                        case op.shar_r_imm_alt_64.value:
                            self.reg[r_a] = pvm_Z_inv(pvm_floor_div(pvm_Z(v_x, 8), 2**(w_b % 64)), 8)

                        case op.rot_r_64_imm:
                            self.reg[r_a] = rori64(w_b, v_x)

                        case op.rot_r_64_imm_alt:
                            self.reg[r_a] = rori64(v_x, w_b)

                        case op.rot_r_32_imm:
                            self.reg[r_a] = pvm_X(rori32(np.uint32(w_b), np.uint32(v_x)), 4)

                        case op.rot_r_32_imm_alt:
                            self.reg[r_a] = pvm_X(rori32(np.uint32(v_x), np.uint32(w_b)), 4)

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.11
                case InstructionType.reg_reg_offset:
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)
                    l_x = min(4, max(0, skip_len - 2) )
                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]
                    v_x = pvm_Z(read_uint(self.rom, self.pc + 2, l_x), l_x)

                    match opcode:
                        case op.branch_eq.value:
                            if w_a == w_b:
                                skip_len = v_x

                        case op.branch_ne.value:
                            if w_a != w_b:
                                skip_len = v_x

                        case op.branch_lt_u.value:
                            if w_a < w_b:
                                skip_len = v_x

                        case op.branch_lt_s.value:
                            if pvm_Z(w_a, 8) < pvm_Z(w_b, 8):
                                skip_len = v_x

                        case op.branch_ge_u.value:
                            if w_a >= w_b:
                                skip_len = v_x

                        case op.branch_ge_s.value:
                            if pvm_Z(w_a, 8) >= pvm_Z(w_b, 8):
                                skip_len = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")


                # GP_A.5.12
                case InstructionType.reg_reg_imm_imm:
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = self.rom[self.pc + 1] // 16

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = min(4, self.rom[self.pc + 2] % 8)
                    #TODO: ook l_x == 0 check
                    v_x = pvm_X(read_uint(self.rom, self.pc + 3, l_x), l_x)

                    l_y = min(4, max(0, skip_len - l_x - 2))
                    v_y = pvm_X(read_uint(self.rom, self.pc + 3 + l_x, l_y), l_y)

                    match opcode:

                        case op.load_imm_jump_ind.value:
                            self.reg[r_a] = v_x
                            skip_len = self.djump(np.uint32(w_b + v_y))

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.13
                case InstructionType.reg_reg_reg:

                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)
                    r_d = min(12, self.rom[self.pc + 2])

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    match opcode:
                        case op.add_32.value:
                            self.reg[r_d] = pvm_X((w_a + w_b) % 2**32, 4)

                        case op.sub_32.value:
                            self.reg[r_d] = pvm_X((w_a + 2**32 - (w_b % 2**32)) % 2**32, 4)

                        case op.mul_32.value:
                            self.reg[r_d] = pvm_X((w_a * w_b) % 2**32, 4)

                        case op.div_u_32.value:
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = 2**64-1
                            else:
                                self.reg[r_d] = pvm_X(pvm_floor_div(w_a % 2**32, w_b % 2**32), 4)

                        case op.div_s_32.value:
                            a = np.int32(pvm_Z(w_a % 2**32, 4))
                            b = np.int32(pvm_Z(w_b % 2**32, 4))

                            if b == 0:
                                self.reg[r_d] = 2**64-1
                            elif a == -2**31 and b == -1:
                                self.reg[r_d] = a
                            else:
                                self.reg[r_d] = pvm_Z_inv(pvm_floor_div(a, b), 8)

                        case op.rem_u_32.value:
                            if w_b % 2**32 == 0:
                                self.reg[r_d] = pvm_X(w_a, 4)
                            else:
                                self.reg[r_d] = pvm_X((w_a % 2**32) % (w_b % 2**32), 4)

                        case op.rem_s_32.value:
                            a = pvm_Z(w_a % 2**32, 4)
                            b = pvm_Z(w_b % 2**32, 4)

                            if b == 0:
                                self.reg[r_d] = pvm_Z_inv(a, 8)
                            elif a == -2**31 and b == -1:
                                self.reg[r_d] = 0
                            else:
                                self.reg[r_d] = pvm_Z_inv(pvm_mod(a, b), 8)

                        case op.shlo_l_32.value:
                            self.reg[r_d] = pvm_X((w_a * 2**(w_b % 32)) % 2**32, 4)

                        case op.shlo_r_32.value:
                            self.reg[r_d] = pvm_X(pvm_floor_div(w_a % 2**32, 2**(w_b % 32)), 4)

                        case op.shar_r_32.value:
                            self.reg[r_d] = pvm_Z_inv(
                                pvm_floor_div(
                                    pvm_Z(w_a % 2**32, 4),
                                    2**(w_b % 32)
                                ),
                             8
                            )

                        case op.add_64.value:
                            self.reg[r_d] = (w_a + w_b) #% 2**64

                        case op.sub_64.value:
                            self.reg[r_d] = (int(w_a) + 2**64 - int(w_b)) % 2**64

                        case op.mul_64.value:
                            self.reg[r_d] = (w_a * w_b) #% 2**64

                        case op.div_u_64.value:
                            if w_b == 0:
                                self.reg[r_d] = 2**64 - 1
                            else:
                                self.reg[r_d] = pvm_floor_div(w_a, w_b)

                        case op.div_s_64.value:
                            if w_b == 0:
                                self.reg[r_d] = 2**64 - 1
                            elif pvm_Z(w_a, 8) == -2**63 and pvm_Z(w_b, 8) == -1:
                                self.reg[r_d] = w_a
                            else:
                                self.reg[r_d] = pvm_Z_inv(
                                    pvm_floor_div(
                                        pvm_Z(w_a, 8),
                                        pvm_Z(w_b, 8)
                                    ),
                                    8
                                )

                        case op.rem_u_64.value:
                            if w_b == 0:
                                self.reg[r_d] = w_a
                            else:
                                self.reg[r_d] = w_a % w_b

                        case op.rem_s_64.value:
                            a = pvm_Z(w_a, 8)
                            b = pvm_Z(w_b, 8)

                            if w_b == 0:
                                self.reg[r_d] = w_a
                            elif a == -2**63 and b == -1:
                                self.reg[r_d] = 0
                            else:
                                self.reg[r_d] = pvm_Z_inv(pvm_mod(a, b), 8)

                        case op.shlo_l_64.value:
                            self.reg[r_d] = (w_a * 2**(w_b % 64)) #% 2**64

                        case op.shlo_r_64.value:
                            self.reg[r_d] = pvm_floor_div(w_a, 2**(w_b % 64))

                        case op.shar_r_64.value:
                            self.reg[r_d] = pvm_Z_inv(pvm_floor_div(pvm_Z(w_a, 8), 2**(w_b % 64)), 8)

                        case op._and.value:
                            self.reg[r_d] = self.reg[r_a] & self.reg[r_b]

                        case op.xor.value:
                            self.reg[r_d] = self.reg[r_a] ^ self.reg[r_b]

                        case op._or.value:
                            self.reg[r_d] = self.reg[r_a] | self.reg[r_b]

                        case op.mul_upper_s_s.value:
                            self.reg[r_d] = pvm_Z_inv(pvm_floor_div((pvm_Z(w_a, 8) * pvm_Z(w_b, 8)), 2**64), 8)

                        case op.mul_upper_u_u.value:
                            self.reg[r_d] = pvm_floor_div(w_a * w_b, 2**64)

                        case op.mul_upper_s_u.value:
                            self.reg[r_d] = pvm_Z_inv(pvm_floor_div(pvm_Z(w_a, 8) * w_b, 2**64), 8)

                        case op.set_lt_u.value:
                            self.reg[r_d] = np.int64(w_a < w_b)

                        case op.set_lt_s.value:
                            self.reg[r_d] = np.int64(pvm_Z(w_a, 8) < pvm_Z(w_b,8))

                        case op.cmov_iz.value:
                            if w_b == 0:
                                self.reg[r_d] = w_a

                        case op.cmov_nz.value:
                            if w_b != 0:
                                self.reg[r_d] = w_a

                        case op.rot_l_64.value:
                            self.reg[r_d] = rori64(w_a, w_b)

                        case op.rot_l_32.value:
                            self.reg[r_a] = pvm_X(rori32(np.uint32(w_a), np.uint32(w_b)), 4)

                        case op.rot_r_64.value:
                            self.reg[r_d] = rori64(w_a, w_b)

                        case op.rot_r_32.value:
                            self.reg[r_a] = pvm_X(rori32(np.uint32(w_a), np.uint32(w_b)), 4)

                        case op.and_inv.value:
                            self.reg[r_a] = self.reg[w_a] & ~self.reg[w_b]

                        case op.or_inv.value:
                            self.reg[r_a] = self.reg[w_a] | ~self.reg[w_b]

                        case op.xnor.value:
                            self.reg[r_a] = ~(self.reg[w_a] | self.reg[w_b])

                        case op._max.value:
                            self.reg[r_a] = max(pvm_Z(self.reg[w_a], 8),  pvm_Z(self.reg[w_b], 8))

                        case op.max_u.value:
                            self.reg[r_a] = max(self.reg[w_a],  self.reg[w_b])

                        case op._min.value:
                            self.reg[r_a] = min(pvm_Z(self.reg[w_a], 8),  pvm_Z(self.reg[w_b], 8))

                        case op.min_u.value:
                            self.reg[r_a] = min(self.reg[w_a],  self.reg[w_b])

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                case _:
                    raise InvalidOpcode(f"Invalid instruction type: {inst_type}")