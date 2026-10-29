"""Native gas queries must match normal hostcall dispatch, including failures."""

from unittest.mock import Mock

import pytest

from pyjamaz import settings

if not settings.PVM_INTERPRETER.startswith("NUMBA_"):
    pytest.skip("Numba gas-query fast path", allow_module_level=True)

from pyjamaz.hostcalls.gas import GAS_QUERY_COST
from pyjamaz.hostcalls.general import hc_gas
from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_W, Opcode, PVM_PAGE_SIZE
from pyjamaz.pvm.invocation import InvocationMutationOutput, InvocationMutator, PVMInvocation
from pyjamaz.pvm.types import PVMCode, PVMProgram


class GasMutator(InvocationMutator):
    def __init__(self):
        self.calls = []

    def execute(self, host_call_instr_nr, gas_limit, registers, memory, invocation_context, _pvm):
        self.calls.append(host_call_instr_nr)
        output = InvocationMutationOutput(
            ExitCondition(ExitReason.resume), gas_limit, _pvm.reg, memory,
        )
        if host_call_instr_nr == 0:
            hc_gas(registers, memory, output, _pvm.log)
        else:
            output.registers[8] = 123
        return output


def program(instructions):
    code = [byte for instruction in instructions for byte in instruction]
    mask = [flag for instruction in instructions for flag in [True] + [False] * (len(instruction) - 1)]
    return PVMProgram(PVMCode(0, 0, len(code), [], code, mask), list(range(13)), PVMMemory())


def invocation(instructions, native):
    result = PVMInvocation(GasMutator(), None)
    result.pvm = PVMInterpreter(program(instructions))
    result.pvm.native_gas_cost = GAS_QUERY_COST if native else 0
    return result


def snapshot(call, output):
    return (
        output.exit_condition, output.instruction_counter, output.gas_limit, tuple(output.registers),
        int(call.pvm.pc), int(call.pvm.gas), int(call.pvm.inst_nr),
        call.pvm.current_block_start, int(call.pvm.skip_len),
    )


@pytest.mark.parametrize("remaining", [-1, 0, 47, 48, 49, 95, 96, 97, 2**63])
def test_repeated_queries_match_dispatch_at_gas_boundaries(remaining):
    instructions = [[Opcode.ecalli.value, 0], [Opcode.ecalli.value, 0], [Opcode.trap.value]]
    normal = invocation(instructions, False)
    native = invocation(instructions, True)
    budget = sum(normal.pvm.basic_block_gas.values()) + remaining

    expected = normal.pvm_invoke_host_call(0, budget)
    actual = native.pvm_invoke_host_call(0, budget)

    assert snapshot(native, actual) == snapshot(normal, expected)
    if remaining >= 96:
        assert normal.invocation_mutator.calls == [0, 0]
        assert native.invocation_mutator.calls == []
        assert actual.registers[7] == remaining - 96
    elif remaining >= 0:
        # Insufficient gas still reaches the decorator, including its negative result.
        assert native.invocation_mutator.calls == [0]
        assert actual.exit_condition.reason == ExitReason.out_of_gas
        assert actual.gas_limit < 0


def test_maximum_unsigned_gas_and_other_hostcalls():
    instructions = [[Opcode.ecalli.value, 0], [Opcode.ecalli.value, 99], [Opcode.trap.value]]
    normal = invocation(instructions, False)
    native = invocation(instructions, True)
    expected = normal.pvm_invoke_host_call(0, 2**64 - 1)
    actual = native.pvm_invoke_host_call(0, 2**64 - 1)

    assert snapshot(native, actual) == snapshot(normal, expected)
    assert normal.invocation_mutator.calls == [0, 99]
    assert native.invocation_mutator.calls == [99]
    assert actual.registers[8] == 123


def test_queries_in_a_loop_preserve_block_charging():
    # The jump at PC 2 goes back two bytes to the query at PC 0.
    instructions = [[Opcode.ecalli.value, 0], [Opcode.jump.value, 254]]
    normal = invocation(instructions, False)
    native = invocation(instructions, True)
    expected = normal.pvm_invoke_host_call(0, 1000)
    actual = native.pvm_invoke_host_call(0, 1000)

    assert snapshot(native, actual) == snapshot(normal, expected)
    assert actual.exit_condition.reason == ExitReason.out_of_gas
    assert len(normal.invocation_mutator.calls) > 1
    assert len(native.invocation_mutator.calls) <= 1


def test_page_fault_between_queries_preserves_resume_state():
    address = 0x20000
    instructions = [
        [Opcode.ecalli.value, 0], [Opcode.load_u8.value, 8, 0, 0, 2],
        [Opcode.ecalli.value, 0], [Opcode.trap.value],
    ]
    normal = invocation(instructions, False)
    native = invocation(instructions, True)
    expected = normal.pvm_invoke_host_call(0, 1000)
    actual = native.pvm_invoke_host_call(0, 1000)
    assert snapshot(native, actual) == snapshot(normal, expected)
    assert actual.exit_condition == ExitCondition(ExitReason.page_fault, address)

    for call in (normal, native):
        call.pvm.mem.add_segment(address, PVM_PAGE_SIZE, MEM_W, b"\x2a")
    expected = normal.pvm_invoke_host_call(expected.instruction_counter, expected.gas_limit)
    actual = native.pvm_invoke_host_call(actual.instruction_counter, actual.gas_limit)

    assert snapshot(native, actual) == snapshot(normal, expected)
    assert actual.registers[8] == 42
    assert normal.invocation_mutator.calls == [0, 0]
    assert native.invocation_mutator.calls == []


@pytest.mark.parametrize("logging", [False, True])
def test_raw_execution_and_logging_keep_the_host_boundary(logging):
    vm = PVMInterpreter(program([[Opcode.ecalli.value, 0], [Opcode.trap.value]]))
    if logging:
        vm.native_gas_cost = GAS_QUERY_COST
        vm.log = Mock()

    vm.invoke(0, 1000)

    assert vm.status == ExitReason.host_halt.value
    assert vm.exit_value == 0
    assert vm.pc == 0
    assert vm.reg[7] == 7


@pytest.mark.parametrize("native", [False, True])
def test_marshalling_requires_explicit_opt_in(monkeypatch, native):
    pvm_program = program([[Opcode.ecalli.value, 0], [Opcode.trap.value]])
    monkeypatch.setattr(PVMProgram, "from_serialized_bytes", lambda **kwargs: pvm_program)
    monkeypatch.setattr(settings, "PVM_DEBUGGER", False)
    options = {"native_gas_cost": GAS_QUERY_COST} if native else {}
    call = PVMInvocation(GasMutator(), None, **options)

    call.pvm_invoke_marshalling(b"", 0, 1000, b"", None)

    assert call.invocation_mutator.calls == ([] if native else [0])
