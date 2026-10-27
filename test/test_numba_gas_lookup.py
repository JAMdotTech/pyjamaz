import pytest

from pyjamaz import settings


if not settings.PVM_INTERPRETER.startswith("NUMBA_"):
    pytest.skip("Numba basic-block gas lookup", allow_module_level=True)

from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.constants import ExitReason, MEM_W, Opcode, PVM_PAGE_SIZE
from pyjamaz.pvm.types import PVMCode, PVMProgram


# Keep block addresses distinct from their indexes, including a late block.
PREFIX = [Opcode.unlikely.value, Opcode.fallthrough.value] * 64
BLOCK_START = len(PREFIX)


def make_vm(tail, bitmask=None):
    code = PREFIX + tail
    bitmask = [True] * len(PREFIX) + (bitmask if bitmask is not None else [True] * len(tail))
    program = PVMProgram(PVMCode(0, 0, len(code), [], code, bitmask), [0] * 13, PVMMemory())
    return PVMInterpreter(program)


@pytest.mark.parametrize("entry_offset", [0, 1])
@pytest.mark.parametrize("extra_gas", [-1, 0, 7])
def test_late_block_entry_charges_the_whole_block(entry_offset, extra_gas):
    interpreter = make_vm([Opcode.unlikely.value, Opcode.unlikely.value, Opcode.trap.value])
    cost = interpreter.basic_block_gas[BLOCK_START]
    entry = BLOCK_START + entry_offset

    interpreter.invoke(entry, cost + extra_gas)

    if extra_gas < 0:
        assert interpreter.status == ExitReason.out_of_gas.value
        assert interpreter.gas == cost - 1
        assert interpreter.pc == entry
    else:
        assert interpreter.status == ExitReason.panic.value
        assert interpreter.gas == extra_gas
        assert interpreter.pc == BLOCK_START + 2


def test_fallthrough_charges_each_visited_block_once():
    interpreter = make_vm([Opcode.trap.value])
    total_cost = sum(interpreter.basic_block_gas.values())

    interpreter.invoke(0, total_cost + 7)

    assert interpreter.status == ExitReason.panic.value
    assert interpreter.pc == BLOCK_START
    assert interpreter.gas == 7


def test_hostcall_resume_preserves_the_late_block_charge():
    interpreter = make_vm(
        [Opcode.ecalli.value, 7, Opcode.unlikely.value, Opcode.trap.value],
        [True, False, True, True],
    )
    cost = interpreter.basic_block_gas[BLOCK_START]
    interpreter.invoke(BLOCK_START, cost + 7)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.exit_value == 7
    assert interpreter.current_block_start == BLOCK_START
    assert interpreter.gas == 7

    interpreter.next_instruction()
    interpreter.invoke(int(interpreter.pc), int(interpreter.gas))

    assert interpreter.status == ExitReason.panic.value
    assert interpreter.pc == BLOCK_START + 3
    assert interpreter.gas == 7


def test_page_fault_resume_preserves_the_late_block_charge():
    address = 0x20000
    interpreter = make_vm(
        [Opcode.unlikely.value, Opcode.load_u8.value, 7, 0, 0, 2, Opcode.trap.value],
        [True, True, False, False, False, False, True],
    )
    cost = interpreter.basic_block_gas[BLOCK_START]
    interpreter.invoke(BLOCK_START, cost + 7)
    assert interpreter.status == ExitReason.page_fault.value
    assert interpreter.pc == BLOCK_START + 1
    assert interpreter.exit_value == address
    assert interpreter.current_block_start == BLOCK_START
    assert interpreter.gas == 7

    interpreter.mem.add_segment(address, PVM_PAGE_SIZE, MEM_W, b"\x2a")
    interpreter.invoke(int(interpreter.pc), int(interpreter.gas))

    assert interpreter.status == ExitReason.panic.value
    assert interpreter.pc == BLOCK_START + 6
    assert interpreter.reg[7] == 42
    assert interpreter.gas == 7
