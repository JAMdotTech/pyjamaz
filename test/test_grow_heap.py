import pytest

from pyjamaz import settings
from pyjamaz.hostcalls.general import hc_grow_heap
from pyjamaz.pvm.constants import ExitCondition, ExitReason, MEM_W, PVM_PAGE_SIZE, PVM_INIT_ZONE_SIZE, PVM_INPUT_DATA_SIZE
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMProgram


@pytest.fixture
def memory(monkeypatch):
    monkeypatch.setattr(settings, "GP_VERSION", "0.8.0")
    return PVMProgram.init_memory(b"", b"preserved", b"", 0, PVM_PAGE_SIZE)


def grow(memory, request, gas):
    registers = list(range(13))
    registers[7] = request
    output = InvocationMutationOutput(ExitCondition(ExitReason.resume), gas, registers, memory)
    hc_grow_heap(registers.copy(), memory, output, None)
    return output


@pytest.mark.parametrize("compatibility,remaining", [(False, 395), (True, 0)])
def test_unaffordable_growth_preserves_registers_and_memory(memory, monkeypatch, compatibility, remaining):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", compatibility)
    end = memory.heap_ptr // PVM_PAGE_SIZE
    pages = set(memory.pages_w)
    output = grow(memory, end + 1, 395)  # One page requires 275 + 121 = 396.

    assert output.exit_condition.reason == ExitReason.out_of_gas
    assert output.gas_limit == remaining
    assert output.registers == list(range(7)) + [end + 1] + list(range(8, 13))
    assert memory.pages_w == pages
    assert memory.heap_ptr == end * PVM_PAGE_SIZE
    assert memory.read_bytes(memory.heap_base, 9) == b"preserved"
    assert not memory.is_accessible(end * PVM_PAGE_SIZE, PVM_PAGE_SIZE, MEM_W)


@pytest.mark.parametrize("compatibility,remaining", [(False, -199), (True, 0)])
def test_equal_boundary_query_stops_before_resuming_with_negative_gas(memory, monkeypatch, compatibility, remaining):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", compatibility)
    end = memory.heap_ptr // PVM_PAGE_SIZE
    pages = set(memory.pages_w)
    output = grow(memory, end, 76)  # Regression: fuzzy/00000109.bin.

    assert output.exit_condition.reason == ExitReason.out_of_gas
    assert output.gas_limit == remaining
    assert output.registers[7] == end
    assert memory.pages_w == pages
    assert memory.heap_ptr == end * PVM_PAGE_SIZE


@pytest.mark.parametrize("compatibility", [False, True])
def test_exact_growth_budget_allocates_pages_and_preserves_contents(memory, monkeypatch, compatibility):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", compatibility)
    end = memory.heap_ptr // PVM_PAGE_SIZE
    output = grow(memory, end + 2, 275 + 2 * 121)

    assert output.exit_condition.reason == ExitReason.resume
    assert output.gas_limit == 0
    assert output.registers[7] == end + 2
    assert memory.heap_ptr == (end + 2) * PVM_PAGE_SIZE
    assert memory.read_bytes(memory.heap_base, 9) == b"preserved"
    assert memory.is_accessible(end * PVM_PAGE_SIZE, 2 * PVM_PAGE_SIZE, MEM_W)
    assert memory.read_bytes(end * PVM_PAGE_SIZE, 2 * PVM_PAGE_SIZE) == bytes(2 * PVM_PAGE_SIZE)


def test_compatibility_is_scoped_to_gp080(memory, monkeypatch):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", True)
    monkeypatch.setattr(settings, "GP_VERSION", "0.7.2")
    end = memory.heap_ptr // PVM_PAGE_SIZE
    output = grow(memory, end + 1, 395)
    assert output.exit_condition.reason == ExitReason.out_of_gas
    assert output.gas_limit == 395


@pytest.mark.parametrize("request_kind", ["below", "equal", "above_limit"])
@pytest.mark.parametrize("gas", [76, 275, 1000])
def test_compatible_queries_charge_base_cost_without_growing(memory, monkeypatch, request_kind, gas):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", True)
    end = memory.heap_ptr // PVM_PAGE_SIZE
    limit = (memory.stack_base - PVM_INIT_ZONE_SIZE) // PVM_PAGE_SIZE
    request = {"below": 0, "equal": end, "above_limit": limit + 1}[request_kind]
    pages = set(memory.pages_w)
    output = grow(memory, request, gas)

    assert output.gas_limit == max(0, gas - 275)
    assert output.exit_condition.reason == (ExitReason.out_of_gas if gas < 275 else ExitReason.resume)
    assert output.registers[7] == (request if gas < 275 else end)
    assert memory.pages_w == pages
    assert memory.heap_ptr == end * PVM_PAGE_SIZE


def test_printed_pdf_oversized_query_applies_nominal_cost_guard(memory, monkeypatch):
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", False)
    request = (memory.stack_base - PVM_INIT_ZONE_SIZE) // PVM_PAGE_SIZE + 1
    end = memory.heap_ptr
    pages = set(memory.pages_w)
    output = grow(memory, request, 1000)

    assert output.exit_condition.reason == ExitReason.out_of_gas
    assert output.gas_limit == 725
    assert output.registers[7] == request
    assert memory.pages_w == pages
    assert memory.heap_ptr == end


@pytest.mark.parametrize("stack_size", [0, 1, PVM_PAGE_SIZE, PVM_INIT_ZONE_SIZE - 1,
                                        PVM_INIT_ZONE_SIZE, PVM_INIT_ZONE_SIZE + 1])
@pytest.mark.parametrize("above_limit", [False, True])
def test_zone_rounded_stack_reservation_limits_growth(monkeypatch, stack_size, above_limit):
    monkeypatch.setattr(settings, "GP_VERSION", "0.8.0")
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", True)
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_STACK_COMPAT", True)
    memory = PVMProgram.init_memory(b"", b"preserved", b"", 0, stack_size)
    # GP #538 uses Z(s), independently of the page rounding used to map the stack.
    stack_zones = (stack_size + PVM_INIT_ZONE_SIZE - 1) // PVM_INIT_ZONE_SIZE
    limit = (2 ** 32 - 3 * PVM_INIT_ZONE_SIZE - PVM_INPUT_DATA_SIZE
             - stack_zones * PVM_INIT_ZONE_SIZE) // PVM_PAGE_SIZE
    request = limit + int(above_limit)
    pages = set(memory.pages_w)
    heap_ptr = memory.heap_ptr
    stack_base = memory.stack_base
    output = grow(memory, request, 275)

    # At the limit growth is permitted but unaffordable; beyond it is a query.
    assert output.exit_condition.reason == (ExitReason.resume if above_limit else ExitReason.out_of_gas)
    assert output.registers[7] == (heap_ptr // PVM_PAGE_SIZE if above_limit else request)
    assert output.gas_limit == 0
    assert memory.pages_w == pages
    assert memory.heap_ptr == heap_ptr
    assert memory.stack_base == stack_base
    assert memory.read_bytes(memory.heap_base, 9) == b"preserved"


@pytest.mark.parametrize("version,compatibility", [("0.8.0", False), ("0.7.2", True)])
def test_stack_rounding_compatibility_preserves_printed_bound(memory, monkeypatch, version, compatibility):
    monkeypatch.setattr(settings, "GP_VERSION", version)
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_STACK_COMPAT", compatibility)
    monkeypatch.setattr(settings, "GP080_GROW_HEAP_OOG_COMPAT", True)
    request = (memory.stack_base - PVM_INIT_ZONE_SIZE) // PVM_PAGE_SIZE
    pages = set(memory.pages_w)
    heap_ptr = memory.heap_ptr
    output = grow(memory, request, 275)

    assert output.exit_condition.reason == ExitReason.out_of_gas
    assert output.registers[7] == request
    assert memory.pages_w == pages
    assert memory.heap_ptr == heap_ptr
