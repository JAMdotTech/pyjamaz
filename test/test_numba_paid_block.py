"""Block lookup shortcuts must preserve gas charging and saved block state."""

import pytest

from pyjamaz import settings

if not settings.PVM_INTERPRETER.startswith("NUMBA_"):
    pytest.skip("Numba basic-block gas charging", allow_module_level=True)

from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.constants import ExitReason, Opcode
from pyjamaz.pvm.types import PVMCode, PVMProgram


def make_vm(instructions):
    code = [byte for instruction in instructions for byte in instruction]
    bitmask = [
        flag
        for instruction in instructions
        for flag in [True] + [False] * (len(instruction) - 1)
    ]
    program = PVMProgram(PVMCode(0, 0, len(code), [], code, bitmask), [0] * 13, PVMMemory())
    return PVMInterpreter(program)


@pytest.mark.parametrize("taken", [False, True])
@pytest.mark.parametrize("extra_gas", [-1, 0, 7])
def test_conditional_branch_charges_the_visited_destination(taken, extra_gas):
    # PC 2 branches to PC 10; the other path starts at PC 6.
    vm = make_vm([
        [Opcode.unlikely.value],
        [Opcode.unlikely.value],
        [Opcode.branch_eq_imm.value, 0x17, 1, 8],
        [Opcode.load_imm.value, 8, 11],
        [Opcode.trap.value],
        [Opcode.unlikely.value],
        [Opcode.trap.value],
    ])
    vm.reg[7] = int(taken)
    destination = 10 if taken else 6
    destination_cost = vm.basic_block_gas[destination]
    vm.invoke(0, vm.basic_block_gas[0] + destination_cost + extra_gas)

    if extra_gas < 0:
        assert vm.status == ExitReason.out_of_gas.value
        assert vm.pc == destination
        assert vm.gas == destination_cost - 1
        assert vm.current_block_start == -1
        assert vm.inst_nr == 3
        # An unpaid destination is charged normally when execution resumes.
        vm.invoke(destination, destination_cost + 7)
        extra_gas = 7

    assert vm.status == ExitReason.panic.value
    assert vm.pc == (11 if taken else 9)
    assert vm.gas == extra_gas
    assert vm.current_block_start == destination
    assert vm.reg[8] == (0 if taken else 11)


def test_backward_jump_charges_each_loop_iteration():
    vm = make_vm([[Opcode.unlikely.value], [Opcode.jump.value, 255]])
    cost = vm.basic_block_gas[0]

    vm.invoke(0, 4 * cost - 1)

    assert vm.status == ExitReason.out_of_gas.value
    assert vm.pc == 0
    assert vm.gas == cost - 1
    assert vm.inst_nr == 6
    assert vm.current_block_start == -1


@pytest.mark.parametrize("offset", [1, 255])
def test_paid_block_still_rejects_invalid_jump_destinations(offset):
    # PC 2 targets either its operand at PC 3 or a non-block-start at PC 1.
    vm = make_vm([
        [Opcode.unlikely.value],
        [Opcode.unlikely.value],
        [Opcode.jump.value, offset],
        [Opcode.trap.value],
    ])

    vm.invoke(0, vm.basic_block_gas[0] + 7)

    assert vm.status == ExitReason.panic.value
    assert vm.pc == 2
    assert vm.gas == 7
    assert vm.inst_nr == 3
    assert vm.current_block_start == 0


@pytest.mark.parametrize("restore_paid_state", [False, True])
def test_paid_external_entry_refreshes_the_exact_block_start(restore_paid_state):
    prefix = [[Opcode.ecalli.value, 7], [Opcode.fallthrough.value]]
    prefix += [[Opcode.unlikely.value], [Opcode.fallthrough.value]] * 8
    late_block_start = 19
    vm = make_vm(prefix + [[Opcode.unlikely.value], [Opcode.trap.value]])
    if restore_paid_state:
        vm.gas_paid = True
    else:
        vm.invoke(0, vm.basic_block_gas[0] + 7)
        assert vm.status == ExitReason.host_halt.value
    assert vm.current_block_start == 0

    vm.invoke(late_block_start + 1, 7)

    assert vm.status == ExitReason.panic.value
    assert vm.pc == late_block_start + 1
    assert vm.gas == 7
    assert vm.current_block_start == late_block_start


@pytest.mark.parametrize("invalid_pc", [1, 4, 2**32 - 1])
def test_invalid_resume_pc_preserves_paid_block_state(invalid_pc):
    vm = make_vm([
        [Opcode.ecalli.value, 7],
        [Opcode.unlikely.value],
        [Opcode.trap.value],
    ])
    vm.invoke(0, vm.basic_block_gas[0] + 7)
    assert vm.status == ExitReason.host_halt.value
    assert vm.current_block_start == 0

    vm.invoke(invalid_pc, 7)

    assert vm.status == ExitReason.panic.value
    assert vm.pc == invalid_pc
    assert vm.gas == 7
    assert vm.inst_nr == 1
    assert vm.current_block_start == 0
