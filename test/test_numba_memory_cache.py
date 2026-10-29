import pytest

from pyjamaz import settings


if not settings.PVM_INTERPRETER.startswith("NUMBA_"):
    pytest.skip("Numba memory view cache", allow_module_level=True)

from pyjamaz.hostcalls.general import hc_grow_heap
from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_I, MEM_R, MEM_W, Opcode, PVM_PAGE_SIZE
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMCode, PVMProgram


ADDRESS = 0x20000


def make_vm(memory, opcode=Opcode.load_u8, addresses=(ADDRESS, ADDRESS)):
    # Two memory instructions separated by host calls, within one basic block.
    code = b"".join(
        bytes([opcode.value, 7]) + address.to_bytes(3, "little") + bytes([Opcode.ecalli.value, 0])
        for address in addresses
    ) + bytes([Opcode.trap.value])
    bitmask = [True, False, False, False, False, True, False] * len(addresses) + [True]
    program_code = PVMCode(0, 0, len(code), [], list(code), bitmask)
    interpreter = PVMInterpreter(PVMProgram(program_code, [0] * 13, memory))
    interpreter.gas = 10000
    return interpreter


def run(interpreter):
    if interpreter.status == ExitReason.host_halt.value:
        interpreter.next_instruction()
    interpreter.invoke(int(interpreter.pc), int(interpreter.gas))


@pytest.fixture
def memory():
    memory = PVMMemory()
    memory.add_segment(ADDRESS, PVM_PAGE_SIZE, MEM_W, b"\x01")
    return memory


@pytest.mark.parametrize("opcode", [Opcode.load_u8, Opcode.store_u8])
def test_hostcall_resume_reuses_views_and_shares_memory_writes(memory, opcode, monkeypatch):
    interpreter = make_vm(memory, opcode)
    from pyjamaz.pvm.interpreters.numba import interpreter_numba_jit

    buffers = []
    original = interpreter_numba_jit.invoke_native

    def invoke(*args):
        buffers.append(args[-3:])
        return original(*args)

    monkeypatch.setattr(interpreter_numba_jit, "invoke_native", invoke)
    interpreter.reg[7] = 9
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert memory.read_bytes(ADDRESS, 1) == (b"\x09" if opcode == Opcode.store_u8 else b"\x01")
    views = interpreter._prepare_memory_for_jit()
    remaining_gas = interpreter.gas

    memory.write_bytes(ADDRESS, b"\x02")
    interpreter.reg[7] = 10
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.gas == remaining_gas  # Resuming must not charge the block again.
    if opcode == Opcode.load_u8:
        assert interpreter.reg[7] == 2
    else:
        assert memory.read_bytes(ADDRESS, 1) == b"\x0a"
    assert all(before is after for before, after in zip(views, interpreter._prepare_memory_for_jit()))
    assert len(buffers) == 2
    assert all(first is second for first, second in zip(*buffers))


@pytest.mark.parametrize("permission", [MEM_I, MEM_R])
@pytest.mark.parametrize("direct_edit", [False, True])
def test_revoked_permissions_take_effect_on_resume(memory, permission, direct_edit):
    interpreter = make_vm(memory, Opcode.store_u8)
    interpreter.reg[7] = 9
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value

    if direct_edit:
        memory.pages_w.discard(ADDRESS // PVM_PAGE_SIZE)
        if permission == MEM_I:
            memory.pages_r.discard(ADDRESS // PVM_PAGE_SIZE)
    else:
        memory.change_acl(ADDRESS // PVM_PAGE_SIZE, 1, permission)
    interpreter.reg[7] = 10
    run(interpreter)
    assert interpreter.status == ExitReason.page_fault.value
    assert interpreter.exit_value == ADDRESS
    assert bytes(memory.view(ADDRESS, 1)) == b"\x09"
    remaining_gas = interpreter.gas

    memory.change_acl(ADDRESS // PVM_PAGE_SIZE, 1, MEM_W)
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.gas == remaining_gas
    assert memory.read_bytes(ADDRESS, 1) == b"\x0a"


def test_mapping_after_cross_page_fault_preserves_gas_and_atomic_writes(memory):
    address = ADDRESS + PVM_PAGE_SIZE - 4
    interpreter = make_vm(memory, Opcode.store_u64, (address,))
    value = 0x0807060504030201
    interpreter.reg[7] = value
    run(interpreter)
    assert interpreter.status == ExitReason.page_fault.value
    assert interpreter.exit_value == ADDRESS + PVM_PAGE_SIZE
    assert memory.read_bytes(address, 4) == bytes(4)
    remaining_gas = interpreter.gas

    memory.add_segment(ADDRESS + PVM_PAGE_SIZE, PVM_PAGE_SIZE, MEM_W)
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.gas == remaining_gas
    assert memory.read_bytes(address, 8) == value.to_bytes(8, "little")


@pytest.mark.parametrize("clone", [False, True])
def test_replacement_memory_with_identical_permissions_gets_its_own_views(memory, clone):
    interpreter = make_vm(memory)
    run(interpreter)
    assert interpreter.reg[7] == 1

    replacement = memory.clone() if clone else PVMMemory()
    if not clone:
        replacement.add_segment(ADDRESS, PVM_PAGE_SIZE, MEM_W)
    replacement.write_bytes(ADDRESS, b"\x03")
    interpreter.mem = replacement
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.reg[7] == 3
    assert memory.read_bytes(ADDRESS, 1) == b"\x01"


def test_replaced_backing_mmap_invalidates_views(memory):
    interpreter = make_vm(memory)
    run(interpreter)
    original_view = memory.view(ADDRESS, 1)

    replacement = PVMMemory()
    replacement.add_segment(ADDRESS, PVM_PAGE_SIZE, MEM_W, b"\x03")
    memory._mm = replacement._mm
    memory._mv = replacement._mv
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.reg[7] == 3
    assert bytes(original_view) == b"\x01"


def test_heap_growth_is_visible_on_resume():
    memory = PVMProgram.init_memory(b"", b"preserved", b"", 0, PVM_PAGE_SIZE)
    old_end = memory.heap_ptr
    interpreter = make_vm(memory, addresses=(memory.heap_base, old_end))
    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value

    registers = [0] * 13
    registers[7] = old_end // PVM_PAGE_SIZE + 1
    output = InvocationMutationOutput(ExitCondition(ExitReason.resume), 1000, registers.copy(), memory)
    hc_grow_heap(registers, memory, output, None)
    assert output.exit_condition.reason == ExitReason.resume
    memory.write_bytes(old_end, b"\x04")

    run(interpreter)
    assert interpreter.status == ExitReason.host_halt.value
    assert interpreter.reg[7] == 4
    assert memory.heap_ptr == old_end + PVM_PAGE_SIZE
    assert memory.read_bytes(memory.heap_base, 9) == b"preserved"
