from typing import List

from jamcodec.base import JamBytes
from jamcodec.types import U64

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, PVM_PAGE_SIZE
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants_new import ExitReason, ExitCondition
from pyjamaz.pvm.debug_logger import PVMDebugLog
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types_new import PVMLogger, PVMMemory, PVMMemoryMode, PVMProgram, PVMCode
from pyjamaz.hostcalls.constants import HostCallResult, InnerPVMResult
from pyjamaz.hostcalls.models import RefineInvocationContext, IntegratedPVM


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
    logger.hc_regs(f"HISTORICAL_LOOKUP", "refine")
    invocation_output.gas_limit -= 10

    try:
        service_account = services.retrieve_service_account(service_id)
    except StateKeyNoResult:
        service_account = None

    # GP: bold_a
    if registers[7] == 2 ** 64 - 1 and service_account:
        service_account_id = service_id
    else:
        try:
            service_account_id = registers[7]
            service_account = services.retrieve_service_account(service_account_id)
        except StateKeyNoResult:
            service_account = None  # bold_a = ∅

    h = registers[8]
    o = registers[9]

    # GP: bold_v
    preimage = None
    mem_inaccessible = False
    if service_account:
        if memory.is_accessible(h, 32, PVMMemoryMode.readable):
            try:
                preimage_hash = memory.read_bytes(h, 32)
                preimage = services.historical_preimage_lookup(service_account_id, timeslot, preimage_hash) #(EQ 9.5), historical lookup
            except PVMMemoryError:
                mem_inaccessible = True   # bold_v = ∇
        else:
            mem_inaccessible = True  # bold_v = ∇

    f = min(registers[10], len(preimage or []))
    l = min(registers[11], len(preimage or []) - f)

    if mem_inaccessible is True or not memory.is_accessible(o, l, PVMMemoryMode.writable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif preimage is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(preimage)
        invocation_output.memory.write_bytes(o, preimage[f:f+l])


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
    logger.hc_regs(f"EXPORT", "refine")

    p = registers[7]
    z = min(registers[8], EC_SEGMENT_SIZE)
    data_segment = None #GP: bold_x
    if memory.is_accessible(p, z, PVMMemoryMode.readable):
        data_segment = memory.read_bytes(p, z, padding=EC_SEGMENT_SIZE)

    if data_segment is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif export_segment_offset + len(m_e.export_segments) >= MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.FULL.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = export_segment_offset + len(m_e.export_segments)
        m_e.export_segments.append(data_segment)


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
    logger.hc_regs(f"MACHINE", "refine")

    p_o = registers[7]
    p_z = registers[8]
    i = registers[9]

    program_blob = None
    if memory.is_accessible(p_o, p_z, PVMMemoryMode.readable):
        program_blob = memory.read_bytes(p_o, p_z)

    pvm_code = None
    try:
        pvm_code = PVMCode.from_jam_bytes(JamBytes(program_blob))
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
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif pvm_code is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.HUH.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = n
        m_e.inner_pvm_lookup[n] = IntegratedPVM(
            code=pvm_code,
            memory=PVMMemory(None, None, None, None),
            program_counter=i
        )


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
    logger.hc_regs(f"PEEK", "refine")

    n = registers[7]
    o = registers[8]
    s = registers[9]
    z = registers[10]

    if not memory.is_accessible(o, z, PVMMemoryMode.writable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif n not in m_e.inner_pvm_lookup:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif not m_e.inner_pvm_lookup[n].memory.is_accessible(s, z, PVMMemoryMode.readable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OOB.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        invocation_output.memory.write_bytes(o, m_e.inner_pvm_lookup[n].memory.read_bytes(s, z))


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
    logger.hc_regs(f"POKE", "refine")

    n = registers[7]
    s = registers[8]
    o = registers[9]
    z = registers[10]

    if not memory.is_accessible(s, z, PVMMemoryMode.readable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif n not in m_e.inner_pvm_lookup:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif not m_e.inner_pvm_lookup[n].memory.is_accessible(s, z, PVMMemoryMode.writable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OOB.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.OK.value
        m_e.inner_pvm_lookup[n].memory.write_bytes(o, memory.read_bytes(s, z))


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
    logger.hc_regs(f"PAGES", "refine")

    n = registers[7]
    p = registers[8]
    c = registers[9]
    r = registers[10]

    mem: PVMMemory = None
    if n in m_e.inner_pvm_lookup:
        mem = m_e.inner_pvm_lookup[n].memory

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    if mem is None:
        invocation_output.registers[7] = HostCallResult.WHO.value
    elif r > 4 or p < 16 or p+c >= 2**32 // PVM_PAGE_SIZE:
        invocation_output.registers[7] = HostCallResult.HUH.value
    elif r > 2 and mem.has_inaccessible_acl(p, c):
        invocation_output.registers[7] = HostCallResult.HUH.value
    else:
        invocation_output.registers[7] = HostCallResult.OK.value

        if r == 0:
            acl = PVMMemoryMode.inaccesible
        elif r == 1 or r == 3:
            acl = PVMMemoryMode.readable
        elif r == 2 or r == 4:
            acl = PVMMemoryMode.writable
        else:
            raise ValueError('invalid r')

        if r < 3:
            mem.zero(p, c, acl)
        else:
            mem.void(p, c, acl)


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
    logger.hc_regs(f"INVOKE", "refine")

    n = registers[7]
    o = registers[8]

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    gas = None
    reg = []
    if memory.is_accessible(o, 112, PVMMemoryMode.writable):
        jam_bytes = JamBytes(memory.read_bytes(o, 112))
        gas = U64.decode(jam_bytes)
        for _ in range(13):
            reg.append(U64.decode(jam_bytes))

    pvm_program = None
    if n in m_e.inner_pvm_lookup:
        pvm_program = PVMProgram(
            code=m_e.inner_pvm_lookup[n].code,
            registers=reg,
            memory=m_e.inner_pvm_lookup[n].memory
        )
        """
        Invokes general PVM function (Ψ) on an inner PVM
        """
        #pvm: PVMInterpreter = PVMInterpreter(pvm_program, logger_cls=None)
        pvm: PVMInterpreter = PVMInterpreter(pvm_program, logger_cls=PVMDebugLog)
        pvm.invoke(
            m_e.inner_pvm_lookup[n].program_counter,
            gas
        )
        pvm_exit_condition = pvm.get_exit_condition()

    def update_inner_pvm(pc: int):
        invocation_output.memory.write_bytes(o, int(pvm.gas).to_bytes(8, byteorder='little'))
        for idx in range(13):
            invocation_output.memory.write_bytes(o+8+idx*8, int(pvm.reg[idx]).to_bytes(8, byteorder='little'))

        m_e.inner_pvm_lookup[n].memory = pvm.mem #TODO: is nu een reference, moet een deepclone worden!
        m_e.inner_pvm_lookup[n].program_counter = pc


    if gas is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif pvm_program is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.WHO.value

    elif pvm_exit_condition.reason == ExitReason.host_halt.value:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.HOST.value
        invocation_output.registers[8] = pvm_exit_condition.value
        update_inner_pvm(pvm.pc + 1)

    elif pvm_exit_condition.reason == ExitReason.page_fault.value:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.FAULT.value
        invocation_output.registers[8] = pvm_exit_condition.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.out_of_gas.value:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.OOG.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.panic.value:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.PANIC.value
        update_inner_pvm(pvm.pc)

    elif pvm_exit_condition.reason == ExitReason.halt.value:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = InnerPVMResult.HALT.value
        update_inner_pvm(pvm.pc)


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
    logger.hc_regs(f"EXPUNGE", "refine")

    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)

    # TODO not idiomatic -> convert to if registers[7] not in m_e.inner_pvm_lookup
    if not registers[7] in m_e.inner_pvm_lookup:
        invocation_output.registers[7] = HostCallResult.WHO.value
    else:
        del m_e.inner_pvm_lookup[registers[7]]
