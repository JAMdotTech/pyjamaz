from math import floor
from typing import Any, List, Dict

import numpy as np
import numpy.typing as npt

from .exceptions import InvalidOpcode
from .codec import PVMProgram

from .utils import (
    pvm_Zn,
    pvm_X,
    pvm_Zn_inv,
    read_uint
)

from .constants import (
    Opcode as op,
    OpcodeScheme,
    InstructionType,
    ExitCondition,
    MemOps
)

from pyjamaz.types import AppType


class PVM:

    def __init__(self, app:AppType):
        self.app = app
        self.reg = np.zeros(13, dtype=np.uint32)
        self.pc:np.uint32 = np.uint32(0)
        self.gas:np.uint64 = np.uint64(0)
        self.mem:npt.NDArray[np.uint8] = np.zeros(1, dtype=np.uint8)
        # TODO: self.jump_tables = np.array(program.code, dtype=np.int8)
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
        # TODO: self.jump_tables = np.array(program.code, dtype=np.int8)
        self.rom:npt.NDArray[np.uint8] = np.array(program.code, dtype=np.uint8)
        self.program_size: np.uint64 = np.uint64(len(self.rom))
        self.inst_bitmask: List[bool] = program.opcode_bitmask
        self.inst_pos: Dict[int,int] = {0: 0}
        self.inst_len: List[int] = []
        self.reg = np.array(initial_regs, dtype=np.uint32)
        self.pc = np.uint32(initial_pc)
        self.gas = np.uint64(initial_gas)
        self.status = ExitCondition.none.value

        #TODO: initial_page_map.address, length, is-writable
        self.mem_offset = mem_offset
        if initial_page_map:
            self.mem_offset = initial_page_map[0]["address"]    #TODO: memory addressing uitwerken
        if initial_memory:
            for block_idx, mem_block in enumerate(initial_memory):
                for idx, byt in enumerate(mem_block["contents"]):
                    self.mem[initial_page_map[block_idx]["address"] - mem_block["address"] + idx] = np.uint8(byt)

        self.create_instruction_lookup()

    def is_readable(self, mem, offset, length):
        # TODO: support pages, readable book keeping
        return offset < len(mem) >= offset + length

    def is_writable(self, mem, offset, length):
        #TODO: support pages, writable book keeping
        return offset < len(mem) >= offset + length

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
                            #TODO: NO_TESTS
                            l_x = min(4, max(0, skip_len - 1))
                            v_x = pvm_X(read_uint(self.rom, self.pc + 1, l_x), l_x)
                            self.status = ExitCondition.host.value
                            #TODO: we do not exit the main loop on this, since the program may be continued?
                            # or is this also a exit condition which we handfle differently?
                            #TODO: self.pc += skip_len for resuming later?
                            result = self.app.hostcalls.invoke_from_pvm(self, v_x)

                        case _:
                            raise InvalidOpcode(f"Invalid imm opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.3
                case InstructionType.imm_imm:

                    l_x = min(4, self.rom[self.pc + 1] % 8)
                    l_y = min(4, max(0, skip_len - l_x - 2))    #TODO: GP::228 l is al met 1 opgehoogd hier zo te zijn???
                    v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)
                    v_y = pvm_X(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    mapped_addr = v_x - self.mem_offset
                    if mapped_addr >= len(self.mem):
                        self.status = ExitCondition.panic.value
                        self.gas -= 1
                        continue

                    match opcode:
                        case op.store_imm_u8.value:
                            self.mem[self.reg[mapped_addr]] = np.uint8(v_y & 0xFF)
                        case op.store_imm_u16.value:
                            self.mem[self.reg[mapped_addr] + 0] = np.uint8(v_y & 0xFF)
                            self.mem[self.reg[mapped_addr] + 1] = np.uint8((v_y & 0xFF00) >> 8)
                        case op.store_imm_u32.value:
                            self.mem[self.reg[mapped_addr] + 0] = np.uint8(v_y & 0xFF)
                            self.mem[self.reg[mapped_addr] + 1] = np.uint8((v_y & 0xFF00) >> 8)
                            self.mem[self.reg[mapped_addr] + 2] = np.uint8((v_y & 0xFF0000) >> 16)
                            self.mem[self.reg[mapped_addr] + 3] = np.uint8((v_y & 0xFF000000) >> 24)

                        case _:
                            raise InvalidOpcode(f"Invalid imm_imm opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.4
                case InstructionType.offset:

                    #TODO: skip_len uit GP lijkt altijd voor te lopen, dus overal nalopen en -1 doen?
                    l_x = min(4, max(0, skip_len - 1) )
                    v_x = pvm_Zn(read_uint(self.rom, self.pc + 1, l_x), l_x)

                    match opcode:
                        case op.jump.value:
                            skip_len = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid offset opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.5
                case InstructionType.reg_imm:
                    r_a = self.rom[self.pc + 1] % 16
                    #w_a = self.reg[r_a]
                    l_x = min(4, max(0, skip_len - 2) )
                    v_x = 0
                    if l_x > 0:
                        v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)

                    if opcode in MemOps:
                        mapped_addr = v_x - self.mem_offset
                        if mapped_addr >= len(self.mem):
                            self.status = ExitCondition.panic.value
                            self.gas -= 1
                            continue

                    match opcode:
                        case op.jump_ind.value:
                            #GP.226
                            if self.reg[0] == 0xffff0000:
                                self.status = ExitCondition.halt.value
                            elif l_x == 0:
                                self.status = ExitCondition.panic.value
                                self.pc = 0

                            #TODO:implementeer
                            pass

                        case op.load_imm.value:
                            self.reg[r_a] = v_x

                        case op.load_u8.value:
                            self.reg[r_a] = self.mem[mapped_addr]

                        case op.load_i8.value:
                            self.reg[r_a] = pvm_Zn_inv(pvm_Zn(read_uint(self.mem, mapped_addr, 1), 1),4)

                        case op.load_u16.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 2)

                        case op.load_i16.value:
                            self.reg[r_a] = pvm_Zn_inv(pvm_Zn(read_uint(self.mem, mapped_addr, 2), 2), 4)

                        case op.load_u32.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 4)

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
                            raise InvalidOpcode(f"Invalid reg_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.6
                # TODO:NO_TEST:
                case InstructionType.reg_imm_imm:
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    w_a = self.reg[r_a]
                    # The other 4 bits from this byte are reserved for the length of our uint (uint8,16 or 32)
                    l_x = min(4, (self.rom[self.pc + 1] // 16) % 8)
                    # Next we read l_x (max 4 bytes) from our rom into v_x as a uint(8,16 or 32), we always convert this to a uint32
                    v_x = pvm_X(read_uint(self.rom, self.pc + 2, l_x), l_x)

                    l_y = min(4, max(0, skip_len - l_x - 1))
                    v_y = pvm_X(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

                    mapped_addr = (w_a + v_x) - self.mem_offset
                    if mapped_addr >= len(self.mem):
                        self.status = ExitCondition.panic.value
                        self.gas -= 1
                        continue

                    match opcode:

                        # TODO:NO_TEST:
                        case op.store_imm_ind_u8.value:
                            self.mem[mapped_addr] = np.uint8(v_y & 0xFF)

                        # TODO:NO_TEST:
                        case op.store_imm_u16.value:
                            self.mem[mapped_addr + 0] = np.uint8(v_y & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((v_y & 0xFF00) >> 8)

                        # TODO:NO_TEST:
                        case op.store_imm_ind_u32.value:
                            self.mem[mapped_addr + 0] = np.uint8(v_y & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((v_y & 0xFF00) >> 8)
                            self.mem[mapped_addr + 2] = np.uint8((v_y & 0xFF0000) >> 16)
                            self.mem[mapped_addr + 3] = np.uint8((v_y & 0xFF000000) >> 24)

                        case _:
                            raise InvalidOpcode(f"Invalid reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.7
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
                    v_y = pvm_Zn(read_uint(self.rom, self.pc + 2 + l_x, l_y), l_y)

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
                            if pvm_Zn(w_a, 4) < pvm_Zn(v_x, 4):
                                skip_len = v_y

                        case op.branch_le_s_imm.value:
                            if pvm_Zn(w_a, 4) <= pvm_Zn(v_x, 4):
                                skip_len = v_y

                        case op.branch_ge_s_imm.value:
                            if pvm_Zn(w_a, 4) >= pvm_Zn(v_x, 4):
                                skip_len = v_y

                        case op.branch_gt_s_imm.value:
                            if pvm_Zn(w_a, 4) > pvm_Zn(v_x, 4):
                                skip_len = v_y

                        case _:
                            raise InvalidOpcode(f"Invalid reg_imm_offset opcode: {opcode} for instruction type {inst_type}")


                #GP_A.5.8
                case InstructionType.reg_reg:

                    r_d = min(12, self.rom[self.pc + 1] % 16)
                    r_a = min(12, self.rom[self.pc + 1] // 16)

                    match opcode:
                        case op.move_reg.value:
                            self.reg[r_d] = self.reg[r_a]

                        #TODO: NO_TEST:
                        #case op.sbrk.value:
                        #!!!!!!! TODO: implementeer wanneer memory management is geimplementeerd

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.9
                case InstructionType.reg_reg_imm:

                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]
                    l_x = min(4, max(0, skip_len - 2) )  #TODO: GP::234 l is al met 1 opgehoogd (gaat over current pos)?
                    if l_x > 0:
                        v_x = pvm_X(read_uint(self.rom, self.pc + 2 , l_x), l_x)
                    else:
                        v_x = 0

                    if opcode in MemOps:
                        mapped_addr = (w_b + v_x) - self.mem_offset
                        if mapped_addr >= len(self.mem):
                            self.status = ExitCondition.panic.value
                            self.gas -= 1
                            continue

                    match opcode:

                        # TODO:NO_TEST:
                        case op.store_ind_u8.value:
                            self.mem[mapped_addr] = np.uint8(w_a & 0xFF)

                        # TODO:NO_TEST:
                        case op.store_ind_u16.value:
                            self.mem[mapped_addr + 0] = np.uint8(w_a & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((w_a & 0xFF00) >> 8)

                        # TODO:NO_TEST:
                        case op.store_ind_u32.value:
                            self.mem[mapped_addr + 0] = np.uint8(w_a & 0xFF)
                            self.mem[mapped_addr + 1] = np.uint8((w_a & 0xFF00) >> 8)
                            self.mem[mapped_addr + 2] = np.uint8((w_a & 0xFF0000) >> 16)
                            self.mem[mapped_addr + 3] = np.uint8((w_a & 0xFF000000) >> 24)

                        case op.load_ind_u8.value:
                            self.reg[r_a] = np.uint32(self.mem[mapped_addr])

                        case op.load_ind_i8.value:
                            self.reg[r_a] = pvm_Zn_inv(pvm_Zn(read_uint(self.mem, mapped_addr, 1), 1), 4)

                        case op.load_ind_u16.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 2)

                        case op.load_ind_i16.value:
                            self.reg[r_a] = pvm_Zn_inv(pvm_Zn(read_uint(self.mem, mapped_addr, 2), 2), 4)

                        case op.load_ind_u32.value:
                            self.reg[r_a] = read_uint(self.mem, mapped_addr, 4)

                        case op.add_imm.value:
                            self.reg[r_a] = (w_b + v_x) % 2**31

                        case op.and_imm.value:
                            # Note: Bn is implicit
                            self.reg[r_a] = w_b & v_x

                        case op.xor_imm.value:
                            # Note: Bn is implicit
                            self.reg[r_a] = w_b ^ v_x

                        case op.or_imm.value:
                            # Note: Bn is implicit
                            self.reg[r_a] = w_b | v_x

                        case op.mul_imm.value:
                            # Note: modulus is implicit (32bit overflow)
                            self.reg[r_a] = w_b * v_x

                        #TODO:NO_TEST:
                        case op.mul_upper_s_s_imm.value:
                            self.reg[r_a] = pvm_Zn_inv((np.uint32(pvm_Zn(w_b, 4) * pvm_Zn(v_x, 4)) / 2**32), 4)

                        #TODO:NO_TEST:
                        case op.mul_upper_u_u_imm.value:
                            self.reg[r_a] = np.uint32((w_b * v_x) / 2 ** 32)

                        case op.set_lt_u_imm.value:
                            self.reg[r_a] = w_b < v_x and 1 or 0

                        case op.set_lt_s_imm.value:
                            self.reg[r_a] = pvm_Zn(w_b, 4) < pvm_Zn(v_x, 4) and 1 or 0

                        case op.shlo_l_imm.value:
                            # TODO: cast naar python int -> port naar numpy
                            self.reg[r_a] = (int(w_b) * (2**int(v_x) % 32)) % 2**32

                        case op.shlo_r_imm.value:
                            self.reg[r_a] = np.uint32(w_b / (2**(v_x%32)))

                        case op.shar_r_imm.value:
                            self.reg[r_a] = pvm_Zn_inv(floor(pvm_Zn(w_b, 4) / (2**(v_x%32))), 4)

                        case op.neg_add_imm.value:
                            #TODO: cast naar python int -> port naar numpy
                            self.reg[r_a] = (int(v_x) + 2**32 - int(w_b)) % 2**32

                        case op.set_gt_u_imm.value:
                            self.reg[r_a] = w_b > v_x and 1 or 0

                        case op.set_gt_s_imm.value:
                            self.reg[r_a] = pvm_Zn(w_b, 4) > pvm_Zn(v_x, 4) and 1 or 0

                        case op.shlo_l_imm_alt.value:
                            # TODO: cast naar python int -> port naar numpy
                            self.reg[r_a] = int(v_x) * (2 ** (int(w_b) % 32)) % 2**32

                        case op.shlo_r_imm_alt.value:
                            #TODO: cast naar python int -> port naar numpy
                            self.reg[r_a] = floor(v_x / (2 ** (int(w_b % 32))))

                        case op.shar_r_imm_alt.value:
                            # TODO: cast naar python int -> port naar numpy
                            self.reg[r_a] = pvm_Zn_inv(floor(pvm_Zn(v_x, 4) / (2 ** (int(w_b) % 32))), 4)

                        case op.cmov_iz_imm.value:
                            if w_b == 0:
                                self.reg[r_a] = v_x

                        case op.cmov_nz_imm.value:
                            if w_b != 0:
                                self.reg[r_a] = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.10
                case InstructionType.reg_reg_offset:
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = min(12, self.rom[self.pc + 1] // 16)
                    l_x = min(4, max(0, skip_len - 2) )
                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]
                    v_x = pvm_Zn(read_uint(self.rom, self.pc + 2, l_x), l_x)

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
                            if pvm_Zn(w_a, 4) < pvm_Zn(w_b, 4):
                                skip_len = v_x

                        case op.branch_ge_u.value:
                            if w_a >= w_b:
                                skip_len = v_x

                        case op.branch_ge_s.value:
                            if pvm_Zn(w_a, 4) >= pvm_Zn(w_b, 4):
                                skip_len = v_x

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg opcode: {opcode} for instruction type {inst_type}")


                # GP_A.5.11
                case InstructionType.reg_reg_imm_imm:
                    # For the first byte after the opcode, the 1st 4 bits are reserved for register address to read w_a into
                    r_a = min(12, self.rom[self.pc + 1] % 16)
                    r_b = self.rom[self.pc + 1] // 16

                    w_a = self.reg[r_a]
                    w_b = self.reg[r_b]

                    l_x = min(4, self.rom[self.pc + 2] % 8)
                    v_x = pvm_X(read_uint(self.rom, self.pc + 3, l_x), l_x)

                    l_y = min(4, max(0, skip_len - l_x - 2))
                    v_y = pvm_X(read_uint(self.rom, self.pc + 3 + l_x, l_y), l_y)

                    match opcode:

                        case op.load_imm_jump_ind:
                            if self.reg[0] == 0xffff0000:
                                self.status = ExitCondition.halt.value
                            elif l_x == 0:
                                self.status = ExitCondition.panic.value
                                self.pc = 0

                            self.reg[r_a] = v_x
                            skip_len = (w_b + v_y) % 2**32

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg_imm_imm opcode: {opcode} for instruction type {inst_type}")

                # GP_A.5.12
                case InstructionType.reg_reg_reg:

                    r_a = self.rom[self.pc + 1] % 16
                    r_b = self.rom[self.pc + 1] // 16
                    r_d = self.rom[self.pc + 2]

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

                        #TODO:NO_TEST:
                        case op.mul_upper_s_s.value:
                            self.reg[r_d] = np.uint32(pvm_Zn(self.reg[r_a], 4) * pvm_Zn(self.reg[r_b], 4) // 2**32)

                        #TODO:NO_TEST:
                        case op.mul_upper_u_u.value:
                            self.reg[r_d] = np.uint32((self.reg[r_a] * self.reg[r_b]) // 2**32)

                        #TODO:NO_TEST:
                        case op.mul_upper_s_u.value:
                            self.reg[r_d] = np.uint32(pvm_Zn((self.reg[r_a], 4) * self.reg[r_b]) // 2 ** 32)

                        case op.div_u.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = 0xffffffff
                            else:
                                self.reg[r_d] = np.fix(self.reg[r_a] / self.reg[r_b]).astype(int)

                        case op.div_s.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = np.int32(-1)
                            #TODO: edge case?:
                            # elif self.reg[r_a] == 0x7FFFFFFF and self.reg[r_b] == -1:
                            #     self.reg[r_d] = 0
                            else:
                                self.reg[r_d] = np.fix(np.int32(self.reg[r_a]) / np.int32(self.reg[r_b])).astype(int)

                        case op.rem_u.value:
                            # Note: Python integer division '//' and remainder '%' do not map to the definition of RISCV div/rem
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = self.reg[r_a]
                            else:
                                divr = np.fix(self.reg[r_a] / self.reg[r_b]).astype(int)
                                self.reg[r_d] = self.reg[r_a] - self.reg[r_b] * divr

                        case op.rem_s.value:
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

                        case op.set_lt_u.value:
                            self.reg[r_d] = self.reg[r_a] < self.reg[r_b]

                        case op.set_lt_s.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) < np.int32(self.reg[r_b])

                        case op.shlo_l.value:
                            self.reg[r_d] = self.reg[r_a] << (self.reg[r_b] & 0x1f)

                        case op.shlo_r.value:
                            self.reg[r_d] = self.reg[r_a] >> (self.reg[r_b] & 0x1f)

                        case op.shar_r.value:
                            self.reg[r_d] = np.int32(self.reg[r_a]) >> np.int32(self.reg[r_b] & 0x1f)

                        case op.cmov_iz.value:
                            if self.reg[r_b] == 0:
                                self.reg[r_d] = self.reg[r_a]

                        # TODO:NO_TEST
                        case op.cmov_nz.value:
                            if self.reg[r_b] != 0:
                                self.reg[r_d] = self.reg[r_a]

                        case _:
                            raise InvalidOpcode(f"Invalid reg_reg_reg opcode: {opcode} for instruction type {inst_type}")
                case _:
                    raise InvalidOpcode(f"Invalid instruction type: {inst_type}")