from typing import List

from jamcodec.base import JamBytes
from jamcodec.types import U64

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.graypaper_constants import EC_SEGMENT_SIZE, MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE, PVM_PAGE_SIZE
from pyjamaz.models.common import WorkPackage
from pyjamaz.models.state import ServicesState
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import ExitReason, ExitCondition
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMLogger, PVMMemory, PVMMemoryMode, PVMProgram, PVMCode
from pyjamaz.pvm_interface.hostcalls.constants import HostCallResult, InnerPVMResult
from pyjamaz.pvm_interface.models import RefineInvocationContext


def hc_historical_lookup(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        services: ServicesState,    #GP: bold_d
        service_id: int,    #GP: s
        timeslot: int,  #GP: t
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    # haal preimage op adv serviceaccount, timeslot en preimagehash en schrijf (deel?) deze weg in memory
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


def hc_fetch(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        work_item_index: int,    #GP: i
        work_package: WorkPackage,    #GP: p
        auth_output: bytes, #GP: bold_o
        work_item_segs: List[List[bytes]], #GP: i_flat
        extrinsics: dict[bytes, bytes],
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    logger.hc_regs(f"FETCH", "refine")
    invocation_output.gas_limit -= 10

    w7 = registers[7]
    w8 = registers[8]
    w9 = registers[9]
    w10 = registers[10]
    w11 = registers[11]
    w12 = registers[12]

    bold_v = None
    if w10 == 0:
        bold_v = work_package.to_jam_bytes().to_bytes()

    elif w10 == 1:
        bold_v = auth_output
    elif w10 == 2 and w11 < len(work_package.items):
        bold_v = work_package.items[w11].payload

    elif w10 == 3 and w11 < len(work_package.items) and w12 < len(work_package.items[w11].extrinsic):
        extrinsic = extrinsics.get(work_package.items[w11].extrinsic[w12].hash)
        if extrinsic and len(extrinsic) == work_package.items[w11].extrinsic[w12].len:
            bold_v = extrinsic

    elif w10 == 4 and w11 < len(work_package.items[work_item_index].extrinsic):
        extrinsic = extrinsics.get(work_package.items[work_item_index].extrinsic[w11].hash)
        if extrinsic and len(extrinsic) == work_package.items[work_item_index].extrinsic[w11].len:
            bold_v = extrinsic

    elif w10 == 5 and w11 < len(work_item_segs) and w12 < len(work_item_segs[w11]):
        bold_v = work_item_segs[w11][w12]

    elif w10 == 6 and w11 < len(work_item_segs[w11]):
        bold_v = work_item_segs[work_item_index][w11]

    elif w10 == 7:
        bold_v = work_package.authorizer.params

    o = w7
    f = min(w8, len(bold_v or []))
    l = min(w9, len(bold_v or [])-f)

    if not memory.is_accessible(o, l, PVMMemoryMode.writable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif bold_v is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(bold_v)
        invocation_output.memory.write_bytes(o, bold_v[f:f+l])


def hc_export(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        export_segment_offset: int, #GP: c_cedie
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    # leest iets uit geheugen en append een blob toe aan e (export segments)
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
        # TODO: hoeveel pages, dynamisch groeiend mem mogelijk maken??????????????
        mem = PVMMemory.allocate(0, 0, 0, 0)
        m_e.inner_pvm_lookup[n] = IntegratedPVM(
            code=pvm_code,
            memory=mem,
            program_counter=i
        )


def hc_peek(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

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


def hc_zero(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    n = registers[7]
    p = registers[8]
    c = registers[9]

    mem: PVMMemory = None
    if n in m_e.inner_pvm_lookup:
        mem = m_e.inner_pvm_lookup[n].memory

    if p < 16 or p+c >= 2**32//PVM_PAGE_SIZE:
        invocation_output.registers[7] = HostCallResult.HUH.value
    elif mem is None:
        invocation_output.registers[7] = HostCallResult.WHO.value
    else:
        invocation_output.registers[7] = HostCallResult.OK.value
        mem.reset(p, c, PVMMemoryMode.writable)


def hc_void(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    n = registers[7]
    p = registers[8]
    c = registers[9]

    mem = None
    if n in m_e.inner_pvm_lookup:
        mem = m_e.inner_pvm_lookup[n].memory

    if mem is None:
        invocation_output.registers[7] = HostCallResult.HUH.value
    elif p < 16 or p+c >= 2**32//PVM_PAGE_SIZE or mem.is_accessible(p, c, PVMMemoryMode.readable):
        invocation_output.registers[7] = HostCallResult.WHO.value
    else:
        invocation_output.registers[7] = HostCallResult.OK.value
        mem.reset(p, c, PVMMemoryMode.non_readable)


def hc_invoke(
        registers: List[int],
        memory: PVMMemory,
        m_e: RefineInvocationContext,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):

    n = registers[7]
    o = registers[8]

    gas = None
    reg = []
    if memory.is_accessible(o, 112, PVMMemoryMode.writable):
        jam_bytes = JamBytes(memory.read_bytes(o, 112))
        gas = U64.decode(jam_bytes)
        for idx in range(13):
            reg[idx] = U64.decode(jam_bytes)

    pvm_program = None
    if n in m_e.inner_pvm_lookup:
        pvm_program = PVMProgram(
            code=m_e.inner_pvm_lookup[n].code,
            registers=reg,
            memory=m_e.inner_pvm_lookup[n].memory #TODO: eigenlijk een clone van mem maken :S
        )

        # invoke general PVM function (Ψ)
        pvm: PVMInterpreter = PVMInterpreter(pvm_program, logger_cls=None)
        pvm.invoke(
            m_e.inner_pvm_lookup[n].program_counter,
            gas
        )
        pvm_exit_condition = pvm.get_exit_condition()

    def update_inner_pvm(pc: int):
        invocation_output.memory.write_bytes(o, pvm.gas)
        for idx in range(13):
            invocation_output.memory.write_bytes(o+8+idx*8, pvm.reg[idx])

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

    if not registers[7] in m_e.inner_pvm_lookup:
        invocation_output.registers[7] = HostCallResult.WHO.value
    else:
        del m_e.inner_pvm_lookup[registers[7]]
