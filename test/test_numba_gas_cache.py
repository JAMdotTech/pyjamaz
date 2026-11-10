import pytest

from pyjamaz import settings


if not settings.PVM_INTERPRETER.startswith("NUMBA_"):
    pytest.skip("Numba gas metadata cache", allow_module_level=True)

from pyjamaz.pvm import PVMInterpreter, PVMMemory
from pyjamaz.pvm.constants import ExitReason, Opcode
from pyjamaz.pvm.gas_model import GasModel
from pyjamaz.pvm.interpreters.numba import interpreter_numba_jit
from pyjamaz.pvm.types import PVMCode, PVMProgram


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(interpreter_numba_jit, "_CODE_METADATA_CACHE", {})


@pytest.fixture
def gas_calculations(monkeypatch):
    calls = []
    original = GasModel.compute_block_gas_cost

    def compute(self, start, *args, **kwargs):
        calls.append(start)
        return original(self, start, *args, **kwargs)

    monkeypatch.setattr(GasModel, "compute_block_gas_cost", compute)
    return calls


def code(*opcodes):
    return PVMCode(0, 0, len(opcodes), [], list(opcodes), [True] * len(opcodes))


def vm(program_code):
    return PVMInterpreter(PVMProgram(program_code, [0] * 13, PVMMemory()))


def test_reused_code_calculates_gas_once_but_charges_each_vm(gas_calculations):
    program_code = code(Opcode.trap.value)
    first = vm(program_code)
    cost = first.basic_block_gas[0]
    first.invoke(0, cost)
    assert first.status == ExitReason.panic.value
    assert first.gas == 0

    second = vm(program_code)
    assert second.current_block_start == -1
    second.invoke(0, cost + 3)
    assert second.status == ExitReason.panic.value
    assert second.gas == 3

    insufficient = vm(program_code)
    insufficient.invoke(0, cost - 1)
    assert insufficient.status == ExitReason.out_of_gas.value
    assert insufficient.gas == cost - 1
    assert gas_calculations == [0]


def test_instance_mutations_do_not_corrupt_cached_gas(gas_calculations):
    program_code = code(Opcode.trap.value)
    first = vm(program_code)
    cost = first.basic_block_gas[0]
    first.basic_block_gas[0] = 999
    first.basic_block_starts_sorted[0] = 99
    first.block_starts_array[0] = 99
    first.block_gas_costs_array[0] = 999
    first.gas_model.sim_code = b"\xff"
    first.current_block_start = 0

    second = vm(program_code)
    assert second.basic_block_gas == {0: cost}
    assert second.basic_block_starts_sorted == [0]
    assert second.block_starts_array.tolist() == [0]
    assert second.block_gas_costs_array.tolist() == [cost]
    second.invoke(0, cost)
    assert second.status == ExitReason.panic.value
    assert second.gas == 0
    assert gas_calculations == [0]


def test_different_code_uses_its_own_gas_cost(gas_calculations):
    first = vm(code(Opcode.trap.value))
    second = vm(code(Opcode.unlikely.value, Opcode.trap.value))
    assert second.basic_block_gas[0] > first.basic_block_gas[0]
    second.invoke(0, first.basic_block_gas[0])
    assert second.status == ExitReason.out_of_gas.value
    assert gas_calculations == [0, 0]


@pytest.mark.parametrize("opcodes", [(), (255,), (Opcode.unlikely.value,)])
def test_invalid_code_panics_without_gas_calculation_on_cache_hit(opcodes, gas_calculations):
    program_code = code(*opcodes)
    for _ in range(2):
        interpreter = vm(program_code)
        assert not interpreter.code_valid
        assert interpreter.basic_block_gas == {}
        assert interpreter.block_starts_array.size == 0
        assert interpreter.block_gas_costs_array.size == 0
        interpreter.invoke(0, 100)
        assert interpreter.status == ExitReason.panic.value
        assert interpreter.gas == 100
    assert gas_calculations == []
