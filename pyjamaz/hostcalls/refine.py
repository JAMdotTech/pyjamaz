from typing import List

from pyjamaz import settings

from jamcodec.base import JamBytes
from jamcodec.types import U64

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, PVM_PAGE_SIZE
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.types import PVMProgram, PVMCode
from pyjamaz.pvm import PVMMemory
from pyjamaz.pvm.constants import ExitReason, ExitCondition, MEM_W, MEM_R, MEM_I
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput, PVMLogger
from pyjamaz.hostcalls.constants import HostCallResult, InnerPVMResult
from pyjamaz.hostcalls.models import RefineInvocationContext, IntegratedPVM
from pyjamaz.hostcalls import hostcall
from pyjamaz.hostcalls.gas import sized, pages_cost, invoke_cost
from pyjamaz.settings import PVM_DEBUGGER

U32_MAX = 2 ** 32
U64_MAX = 2 ** 64


@hostcall(sized(1125, (264, 11)))
def hc_historical_lookup(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        services: ServicesState,    #GP: bold_d
        service_id: int,    #GP: s
        timeslot: int,  #GP: t
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    """
    Make a lookup into the service's preimage store.
    hash: The hash of the preimage to look up.
    Returns the preimage or None if the preimage was not available.
    --------------------------
    haal preimage op adv serviceaccount, timeslot en preimagehash en schrijf (deels?) deze weg in memory
    """
    logger and logger.hc_regs(f"HISTORICAL_LOOKUP", "refine")
    try:
        service_account = services.retrieve_service_account(service_id)
    except StateKeyNoResult:
        service_account = None

    reg7 = registers[7]
    if reg7 == U64_MAX - 1 and service_account:
        service_account_id = service_id
    else:
        try:
            service_account_id = reg7 % U32_MAX
            service_account = services.retrieve_service_account(service_account_id)
        except StateKeyNoResult:
            service_account = None  # bold_a = ∅

    h = int(registers[8])
    o = int(registers[9])

    # GP: bold_v
    preimage = None
    mem_inaccessible = False
    if service_account:
        if memory.is_accessible(h, 32, MEM_R):
            try:
                preimage_hash = memory.read_bytes(h, 32)
                preimage = services.historical_preimage_lookup(service_account_id, timeslot, preimage_hash) #(EQ 9.5), historical lookup
            except PVMMemoryError:
                mem_inaccessible = True   # bold_v = ∇
        else:
            mem_inaccessible = True  # bold_v = ∇

    f = min(registers[10], len(preimage or []))
    l = min(registers[11], len(preimage or []) - f)

    if mem_inaccessible is True or not memory.is_accessible(o, l, MEM_W):
        logger and logger.hc_log("HISTORICAL LOOKUP PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif preimage is None:
        logger and logger.hc_log("HISTORICAL LOOKUP NONE", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
    else:
        logger and logger.hc_log("HISTORICAL LOOKUP OK", reg7)
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(preimage)
        invocation_output.memory.write_bytes(o, preimage[f:f+l])


@hostcall(3521)
def hc_export(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        export_segment_offset: int, #GP: c_cedie
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    """
    Export a segment of data into the JAM Data Lake.
    segment: The segment of data to export.
    Returns the export index or Err if the export was unsuccessful.
    --------------------------
    Leest een stuk geheugen uit en plaatst voegt dit toe aan e (export segments)
    """
    logger and logger.hc_regs(f"EXPORT", "refine")

    p = int(registers[7])
    z = min(registers[8], EC_SEGMENT_SIZE)
    data_segment = None #GP: bold_x
    if memory.is_accessible(p, z, MEM_R):
        data_segment = memory.read_bytes(p, z, padding=EC_SEGMENT_SIZE)

    if data_segment is None:
        logger and logger.hc_log("EXPORT PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif export_segment_offset + len(m_e.export_segments) >= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE:
        logger and logger.hc_log("EXPORT FULL", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.FULL.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = export_segment_offset + len(m_e.export_segments)
        m_e.export_segments.append(data_segment)
        logger and logger.hc_log("EXPORT OK", invocation_output.registers[7])


@hostcall(sized(1862, (112, 8)))
def hc_machine(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Create a new instance of a PVM.
    code: The code of the PVM.
    program_counter: The initial program counter value of the PVM.
    Returns the handle of the PVM or Err if the creation was unsuccessful.
    --------------------------
    Initializeerd een nieuwe PVM instance
    """
    logger and logger.hc_regs(f"MACHINE", "refine")

    p_o = int(registers[7])
    p_z = int(registers[8])
    i = int(registers[9])

    program_blob = None
    if memory.is_accessible(p_o, p_z, MEM_R):
        program_blob = memory.read_bytes(p_o, p_z)

    pvm_code = None
    try:
        pvm_code = PVMCode.from_jam_bytes(JamBytes(program_blob))
    except Exception as e:
        pass

    n = next((key for key in range(63) if key not in m_e.inner_pvm_lookup), 63)

    if len(m_e.inner_pvm_lookup) >= 63:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.FULL.value
        return

    if program_blob is None:
        logger and logger.hc_log("MACHINE PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif pvm_code is None or not pvm_code.is_valid(i):
        logger and logger.hc_log("MACHINE HUH", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = n
        m_e.inner_pvm_lookup[n] = IntegratedPVM(
            code=pvm_code,
            memory=type(memory)(),
            program_counter=i
        )
        logger and logger.hc_log("MACHINE OK", f"idx={n} pc={i}")


@hostcall(sized(377, (336, 10)))
def hc_peek(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Inspect the raw memory of an inner PVM.
    vm_handle: The handle of the PVM whose memory to inspect.
    inner_src: The address in the PVM's memory to start reading from.
    len: The number of bytes to read.
    Returns the data in the PVM vm_handle at memory inner_src or Err if the inspection failed.
    --------------------------
    Leest een stuk geheugen uit een inner PVM instance
    """
    logger and logger.hc_regs(f"PEEK", "refine")

    n = registers[7]  # pvm handle (UInt64)
    o = int(registers[8])  # outer dst address (UInt32 for memory access)
    s = int(registers[9])  # inner src address (UInt32 for inner memory)
    z = registers[10]  # length (UInt64)

    logger and logger.hc_log("PEEK start", f'n={n} o={o} s={s} z={z}')

    if not memory.is_accessible(o, z, MEM_W):
        logger and logger.hc_log("PEEK PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif n not in m_e.inner_pvm_lookup:
        logger and logger.hc_log("PEEK WHO", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif not m_e.inner_pvm_lookup[n].memory.is_accessible(s, z, MEM_R):
        logger and logger.hc_log("PEEK OOB", f"s={s} z={z}")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OOB.value
    else:
        data = m_e.inner_pvm_lookup[n].memory.read_bytes(s, z)
        invocation_output.memory.write_bytes(o, data)

        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        logger and logger.hc_log("PEEK OK", invocation_output.registers[7])


@hostcall(sized(297, (224, 10)))
def hc_poke(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Copy some data into the memory of an inner PVM.
    vm_handle: The handle of the PVM whose memory to mutate.
    outer_src: The data to be copied.
    inner_dst: The address in memory of inner PVM vm_handle to copy the data to.
    Returns Ok on success or Err if the inspection failed.
    --------------------------
    Plaatst een stuk geheugen in een inner PVM instance
    """
    logger and logger.hc_regs(f"POKE", "refine")

    n = registers[7]  # pvm handle (UInt64)
    s = int(registers[8])  # outer src address (UInt32 for memory access)
    o = int(registers[9])  # inner dst address (UInt32 for inner memory)
    z = registers[10]  # length (UInt64)

    if not memory.is_accessible(s, z, MEM_R):
        logger and logger.hc_log("POKE PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif n not in m_e.inner_pvm_lookup:
        logger and logger.hc_log("POKE WHO", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif not m_e.inner_pvm_lookup[n].memory.is_accessible(o, z, MEM_W):
        logger and logger.hc_log("POKE RESUME OOB", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OOB.value
    else:
        data = memory.read_bytes(s, z)
        m_e.inner_pvm_lookup[n].memory.write_bytes(o, data)

        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        logger and logger.hc_log("POKE RESUME OK", "")


@hostcall(pages_cost)
def hc_pages(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    """
    Initialize memory pages in an inner PVM with zeros, allocating if needed.
    - `vm_handle`: The handle of the PVM whose memory to mutate.
    - `page`: The index of the first page of inner PVM `vm_handle` to initialize.
    - `count`: The number of pages to initialize.
    Returns `Ok` on success or `Err` if the operation failed.
    Pages are initialized to be filled with zeroes. If the pages are not yet allocated, they will
    be allocated.
    --------------------------
    Alloceert een stuk geheugfen van een inner PVM instance
    """
    logger and logger.hc_regs(f"PAGES", "refine")

    n = registers[7]  # pvm handle (UInt64)
    p = int(registers[8])  # page index (UInt64)
    c = int(registers[9])  # count (UInt64)
    r = registers[10] # variant (UInt64)

    mem: PVMMemory = None
    if n in m_e.inner_pvm_lookup:
        mem = m_e.inner_pvm_lookup[n].memory

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    if mem is None:
        logger and logger.hc_log("PAGES WHO", "")
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif r > 4 or p < 16 or p + c >= 2**32 // PVM_PAGE_SIZE:
        logger and logger.hc_log("PAGES HUH", "")
        invocation_output.registers[7] = HostCallResult.HUH.value
    elif r > 2 and not mem.is_accessible(p * PVM_PAGE_SIZE, c * PVM_PAGE_SIZE, MEM_R):
        # Note: for r > 2 (preserve operations), pages must already be accessible (not None) because we're preserving their content
        logger and logger.hc_log("PAGES HUH (pages are null, cannot preserve)", "")
        invocation_output.registers[7] = HostCallResult.HUH.value
    else:
        logger and logger.hc_log("PAGES OK", r)
        invocation_output.registers[7] = HostCallResult.OK.value

        if r == 0:
            acl = MEM_I
        elif r == 1 or r == 3:
            acl = MEM_R
        elif r == 2 or r == 4:
            acl = MEM_W

        try:
            if r < 3:
                mem.zero(p, c, acl)
            mem.change_acl(p, c, acl)
        except PVMMemoryError:
            logger and logger.hc_log("PAGES PANIC", "huhhhhh???")
            invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)


@hostcall(invoke_cost)
def hc_invoke(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Invoke an inner PVM.
    vm_handle: The handle of the PVM to invoke.
    gas: The maximum amount of gas which the inner PVM may use in this invocation.
    regs: The initial register values of the inner PVM.
    Returns the outcome of the invocation, together with any remaining gas, and the final register values.
    """
    n, o = int(registers[7]), int(registers[8])
    if not memory.is_accessible(o, 112, MEM_W):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        return
    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
    if n not in m_e.inner_pvm_lookup:
        invocation_output.registers[7] = HostCallResult.WHO.value
        return

    frame = memory.read_bytes(o, 112)
    gas = int.from_bytes(frame[:8], 'little')
    reg = [int.from_bytes(frame[i:i + 8], 'little') for i in range(8, 112, 8)]
    inner = m_e.inner_pvm_lookup[n]
    pvm = PVMInterpreter(PVMProgram(code=inner.code, registers=reg, memory=inner.memory), logger=PVM_DEBUGGER)
    pvm.gas_paid = inner.gas_paid
    pvm.invoke(inner.program_counter, gas)
    result = pvm.get_exit_condition()
    invocation_output.gas_limit += int(pvm.gas)
    frame = int(pvm.gas).to_bytes(8, 'little') + b''.join(int(r).to_bytes(8, 'little') for r in pvm.reg)
    invocation_output.memory.write_bytes(o, frame)
    inner.memory = pvm.mem
    inner.gas_paid = pvm.gas_paid
    inner.program_counter = int(pvm.pc)
    outcomes = {
        ExitReason.host_halt: InnerPVMResult.HOST,
        ExitReason.page_fault: InnerPVMResult.FAULT,
        ExitReason.out_of_gas: InnerPVMResult.OOG,
        ExitReason.panic: InnerPVMResult.PANIC,
        ExitReason.halt: InnerPVMResult.HALT,
    }
    invocation_output.registers[7] = outcomes[result.reason].value
    if result.reason in (ExitReason.host_halt, ExitReason.page_fault):
        invocation_output.registers[8] = result.value
    if result.reason == ExitReason.host_halt:
        inner.program_counter += int(pvm.skip_len)
    elif result.reason in (ExitReason.halt, ExitReason.panic):
        inner.program_counter = 0



@hostcall(335)
def hc_expunge(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Delete an inner PVM instance, freeing any associated resources.
    vm_handle: The handle of the PVM to delete.
    Returns the inner PVM's final instruction counter value on success or Err if the operation failed.
    --------------------------
    Verwijderd een inner PVM
    """
    logger and logger.hc_regs(f"EXPUNGE", "refine")

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    n = registers[7]

    if n not in m_e.inner_pvm_lookup:
        logger and logger.hc_log("EXPUNGE WHO", "")
        invocation_output.registers[7] = HostCallResult.WHO.value
    else:
        invocation_output.registers[7] = m_e.inner_pvm_lookup[n].program_counter
        del m_e.inner_pvm_lookup[n]
        logger and logger.hc_log("EXPUNGE OK", invocation_output.registers[7])
