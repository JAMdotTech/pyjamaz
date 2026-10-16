import pytest

from jamcodec.base import JamBytes
from jamcodec.types import VarInt64

from pyjamaz.hostcalls.constants import HostCallResult
from pyjamaz.hostcalls.models import RefineInvocationContext
from pyjamaz.hostcalls.refine import hc_machine
from pyjamaz.pvm import types as pvm_types
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMCode, PVMProgram


def code_header(jump_table_entries=0, code_length=1):
    return (
        VarInt64.encode(jump_table_entries).to_bytes()
        + b"\x01"
        + VarInt64.encode(code_length).to_bytes()
    )


OVERSIZED_HEADERS = [
    pytest.param(code_header(code_length=2**25 + 1), "code length", id="code"),
    pytest.param(code_header(jump_table_entries=2**24 + 1), "jump table", id="jump-table"),
    pytest.param(code_header(code_length=2**64 - 1), "code length", id="u64-code"),
    pytest.param(code_header(jump_table_entries=2**64 - 1), "jump table", id="u64-jump-table"),
]


def fail_payload(*args, **kwargs):
    pytest.fail("Oversized PVM payload must be rejected before decoding or allocating it")


@pytest.mark.parametrize("header,error", OVERSIZED_HEADERS)
@pytest.mark.parametrize("strict_decoding", [False, True])
def test_oversized_header_rejected_before_payload(monkeypatch, header, error, strict_decoding):
    monkeypatch.setattr(pvm_types, "Array", fail_payload)
    with pytest.raises(ValueError, match=error):
        PVMCode.from_jam_bytes(JamBytes(header), strict_decoding=strict_decoding)


@pytest.mark.parametrize("jump_table_entries,code_length", [
    (0, 2**25),
    (2**24, 1),
    (2**24, 2**25),
])
def test_limits_are_inclusive_without_allocating_payload(monkeypatch, jump_table_entries, code_length):
    class PayloadReached(Exception):
        pass

    def payload_decoder(*args, **kwargs):
        raise PayloadReached

    # Exact-limit headers must get past validation. Stop before huge payloads
    # are constructed; the small-program tests below exercise real decoding.
    monkeypatch.setattr(pvm_types, "Array", payload_decoder)
    with pytest.raises(PayloadReached):
        PVMCode.from_jam_bytes(JamBytes(code_header(jump_table_entries, code_length)))


def test_small_program_still_decodes():
    blob = code_header() + b"\x00\x01"  # trap; instruction bit set.
    code = PVMCode.from_bytes_cached(blob)
    assert code.code == b"\x00"
    assert code.jump_table == []
    assert code.is_valid(0)


@pytest.mark.parametrize("header,error", OVERSIZED_HEADERS)
def test_standard_program_rejects_oversized_code_before_memory_initialization(monkeypatch, header, error):
    monkeypatch.setattr(pvm_types, "Array", fail_payload)
    monkeypatch.setattr(PVMProgram, "init_memory", fail_payload)
    # Empty ROM/heap/stack followed by the independently sized code blob.
    program = bytes(11) + len(header).to_bytes(4, "little") + header
    assert PVMProgram.from_serialized_bytes(program, b"", "oversized") is None


@pytest.mark.parametrize("header,error", OVERSIZED_HEADERS)
def test_machine_rejects_oversized_code_without_creating_vm(monkeypatch, header, error):
    memory = PVMProgram.init_memory(b"", header, b"", 0, 0)
    registers = [0] * 13
    registers[7] = memory.heap_base
    registers[8] = len(header)
    output = InvocationMutationOutput(ExitCondition(ExitReason.resume), 10000, registers.copy(), memory)
    context = RefineInvocationContext(inner_pvm_lookup={}, export_segments=[])
    monkeypatch.setattr(pvm_types, "Array", fail_payload)

    hc_machine(registers, memory, context, output, None)

    assert output.exit_condition.reason == ExitReason.resume
    assert output.registers[7] == HostCallResult.HUH.value
    assert context.inner_pvm_lookup == {}


def test_machine_accepts_small_program():
    blob = code_header() + b"\x00\x01"
    memory = PVMProgram.init_memory(b"", blob, b"", 0, 0)
    registers = [0] * 13
    registers[7] = memory.heap_base
    registers[8] = len(blob)
    output = InvocationMutationOutput(ExitCondition(ExitReason.resume), 10000, registers.copy(), memory)
    context = RefineInvocationContext(inner_pvm_lookup={}, export_segments=[])

    hc_machine(registers, memory, context, output, None)

    assert output.exit_condition.reason == ExitReason.resume
    assert output.registers[7] == 0
    assert context.inner_pvm_lookup[0].code.code == b"\x00"
