import struct
from typing import List

from pyjamaz import settings

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, PVM_PAGE_SIZE
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.types import PVMProgram, _pvm_code_from_bytes_cached
from pyjamaz.pvm import PVMMemory
from pyjamaz.pvm.constants import ExitReason, ExitCondition, MEM_W, MEM_R, MEM_I
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput, PVMLogger
from pyjamaz.hostcalls.constants import HostCallResult, InnerPVMResult
from pyjamaz.hostcalls.models import RefineInvocationContext, IntegratedPVM
from pyjamaz.hostcalls import hostcall
from pyjamaz.refine_profile import count as refine_profile_count, timer as refine_profile_timer
from pyjamaz.settings import PVM_DEBUGGER

U32_MAX = 2 ** 32
U64_MAX = 2 ** 64
_INNER_INVOKE_REG_BLOCK = struct.Struct("<14Q")


def _create_inner_pvm_memory(outer_memory: PVMMemory) -> PVMMemory:
    if settings.INNER_PVM_MEMORY == "sparse" and settings.PVM_INTERPRETER.startswith("NUMBA"):
        from pyjamaz.pvm.interpreters.numba.sparse_memory import SparsePVMMemory

        refine_profile_count("inner_memory_sparse")
        return SparsePVMMemory()

    refine_profile_count("inner_memory_mmap")
    return type(outer_memory)()


def _create_inner_pvm_runtime(pvm_code, memory: PVMMemory, program_counter: int) -> IntegratedPVM:
    with refine_profile_timer("inner_pvm_setup"):
        program = PVMProgram(
            code=pvm_code,
            registers=[0] * 13,
            memory=memory,
        )
        interpreter = PVMInterpreter(program, logger=PVM_DEBUGGER)
    return IntegratedPVM(
        code=pvm_code,
        memory=memory,
        program_counter=program_counter,
        program=program,
        interpreter=interpreter,
    )


@hostcall(10)
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

    h = registers[8] % U32_MAX
    o = registers[9] % U32_MAX

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


@hostcall(10)
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

    p = registers[7] % U32_MAX
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


@hostcall(10)
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

    p_o = registers[7] % U32_MAX
    p_z = registers[8] % U32_MAX
    i = registers[9] % U32_MAX

    program_blob = None
    if memory.is_accessible(p_o, p_z, MEM_R):
        program_blob = memory.read_bytes(p_o, p_z)

    pvm_code = None
    try:
        pvm_code = _pvm_code_from_bytes_cached(program_blob)
    except Exception as e:
        pass

    # TODO: GP states that this should be the first available key, which implies we should fill in gaps
    # sorted_keys = [x for x in m_e.inner_pvm_lookup.keys()].sort()
    # n = 0
    # prev_key = 0
    # for key in sorted_keys:
    #     if key > prev_key + 1:
    #         n = key + 1
    #         break
    n = 0
    keys = [x for x in m_e.inner_pvm_lookup.keys()]
    if keys:
        keys.sort()
        n = keys[-1] + 1

    if program_blob is None:
        logger and logger.hc_log("MACHINE PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif pvm_code is None:
        logger and logger.hc_log("MACHINE HUH", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = n
        inner_memory = _create_inner_pvm_memory(memory)
        m_e.inner_pvm_lookup[n] = _create_inner_pvm_runtime(pvm_code, inner_memory, i)
        logger and logger.hc_log("MACHINE OK", f"idx={n} pc={i}")


@hostcall(10)
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
    o = registers[8] % U32_MAX  # outer dst address (UInt32 for memory access)
    s = registers[9] % U32_MAX  # inner src address (UInt32 for inner memory)
    z = registers[10]  # length (UInt64)
    refine_profile_count("hc_peek_bytes", int(z))

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


@hostcall(10)
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
    s = registers[8] % U32_MAX  # outer src address (UInt32 for memory access)
    o = registers[9] % U32_MAX  # inner dst address (UInt32 for inner memory)
    z = registers[10]  # length (UInt64)
    refine_profile_count("hc_poke_bytes", int(z))

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


@hostcall(10)
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
    p = registers[8]  # page index (UInt64)
    c = registers[9]  # count (UInt64)
    r = registers[10] # variant (UInt64)
    refine_profile_count("hc_pages_pages", int(c))

    mem: PVMMemory = None
    if n in m_e.inner_pvm_lookup:
        mem = m_e.inner_pvm_lookup[n].memory

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    if mem is None:
        logger and logger.hc_log("PAGES WHO", "")
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif r > 4 or p < 16 or p + c > 2**32 // PVM_PAGE_SIZE:
        logger and logger.hc_log("PAGES HUH", "")
        invocation_output.registers[7] = HostCallResult.HUH.value
    elif r > 2 and mem.is_null(p, c):
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


@hostcall(10)
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
    logger and logger.hc_regs(f"INVOKE", "refine")

    n = registers[7]  # pvm handle (UInt64)
    o = registers[8] % U32_MAX  # memory address (UInt32)
    refine_profile_count("hc_invoke_calls")

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    gas = None
    reg = ()
    if memory.is_accessible(o, _INNER_INVOKE_REG_BLOCK.size, MEM_R) and memory.is_accessible(o, _INNER_INVOKE_REG_BLOCK.size, MEM_W):
        with refine_profile_timer("hc_invoke_decode_registers"):
            values = _INNER_INVOKE_REG_BLOCK.unpack(memory.read_bytes(o, _INNER_INVOKE_REG_BLOCK.size))
            gas = values[0]
            reg = values[1:]

    integrated_pvm = m_e.inner_pvm_lookup.get(n)
    pvm = None
    pvm_exit_condition = None
    if integrated_pvm is not None and gas is not None:
        """
        Invokes general PVM function (Ψ) on an inner PVM
        """
        logger and logger.hc_log("INVOKE START", f"gas={gas} reg={reg} pc={integrated_pvm.program_counter}")

        pvm = integrated_pvm.interpreter
        if pvm is None:
            integrated_pvm.program = PVMProgram(
                code=integrated_pvm.code,
                registers=[0] * 13,
                memory=integrated_pvm.memory,
            )
            integrated_pvm.interpreter = PVMInterpreter(integrated_pvm.program, logger=PVM_DEBUGGER)
            pvm = integrated_pvm.interpreter

        with refine_profile_timer("hc_invoke_register_setup"):
            pvm.mem = integrated_pvm.memory
            for idx, value in enumerate(reg):
                pvm.reg[idx] = value

        with refine_profile_timer("inner_pvm_execution"):
            pvm.invoke(
                integrated_pvm.program_counter,
                gas
            )
            pvm_exit_condition = pvm.get_exit_condition()

    def update_inner_pvm(pc: int):
        with refine_profile_timer("hc_invoke_writeback"):
            register_block = bytearray(_INNER_INVOKE_REG_BLOCK.size)
            _INNER_INVOKE_REG_BLOCK.pack_into(
                register_block,
                0,
                int(pvm.gas),
                *(int(pvm.reg[idx]) for idx in range(13)),
            )
            invocation_output.memory.write_bytes(o, register_block)

        integrated_pvm.memory = pvm.mem #TODO: is nu een reference, moet een deepclone worden?
        integrated_pvm.program_counter = int(pc)

    def next_pc_after_host() -> int:
        return int(pvm.pc) + int(pvm.skip_len)


    if gas is None:
        logger and logger.hc_log("INVOKE PANIC GAS", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)

    elif integrated_pvm is None:
        logger and logger.hc_log("INVOKE WHO", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value

    elif pvm_exit_condition.reason == ExitReason.host_halt:
        refine_profile_count("hc_invoke_host_halt")
        logger and logger.hc_log("INVOKE RESUME HOST",pvm_exit_condition.value)
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.HOST.value
        invocation_output.registers[8] = pvm_exit_condition.value
        update_inner_pvm(next_pc_after_host())

    elif pvm_exit_condition.reason == ExitReason.page_fault:
        refine_profile_count("hc_invoke_page_fault")
        logger and logger.hc_log("INVOKE RESUME FAULT", pvm_exit_condition.value)
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.FAULT.value
        invocation_output.registers[8] = pvm_exit_condition.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.out_of_gas:
        refine_profile_count("hc_invoke_out_of_gas")
        logger and logger.hc_log("INVOKE OOG", f"gas={pvm.gas} reg={[int(r) for r in pvm.reg]} pc={pvm.pc}")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.OOG.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.panic:
        refine_profile_count("hc_invoke_panic")
        logger and logger.hc_log("INVOKE PANIC", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.PANIC.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.halt:
        refine_profile_count("hc_invoke_halt")
        logger and logger.hc_log("INVOKE HALT", "")
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.HALT.value
        update_inner_pvm(pvm.pc)


@hostcall(10)
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
