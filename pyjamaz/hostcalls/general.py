from copy import deepcopy
from typing import List, Optional

from jamcodec.types import U64, U32, VarInt64, U8, U16, Vec
from pyjamaz import graypaper_constants as gp_const
from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.common import WorkPackage, AccumulationOperand, WorkItem
from pyjamaz.models.state import ServiceAccount, ServicesState, DeferredTransfer
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemoryMode, PVMLogger, PVMMemory
from pyjamaz.hostcalls.constants import HostCallResult


def hc_gas(
        registers: List[int],
        memory: PVMMemory,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_G) | General host function: gas.

    Query the gas left.
    Returns the remaining gas in register 7.

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger.hc_regs(f"GAS", "general")
    invocation_output.gas_limit -= 10

    gas_value = invocation_output.gas_limit
    if gas_value < 0:
        # Note: convert to two's complement
        gas_value = (1 << 64) + gas_value

    invocation_output.registers[7] = gas_value
    invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)


def hc_lookup(
        registers: List[int],
        memory: PVMMemory,
        service: ServiceAccount,
        service_id: int,
        services: ServicesState,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_L) | General host function: lookup.

    Make a lookup into the service's preimage store.
    hash: The hash of the preimage to look up.
    Returns the preimage or None if the preimage was not available.
    --------------------------
    Puts a Service Preimage blob into PVM memory

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    service: ServiceAccount
    service_id: int
    services: ServicesState
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger.hc_regs(f"LOOKUP", "general")
    invocation_output.gas_limit -= 10

    service_account_id = registers[7]
    if service_account_id in (service_id, 2 ** 64 - 1):
        service_account_id = service_id
        service_account = service
    else:
        try:
            service_account = services.retrieve_service_account(registers[7])  # GP: bold_a
        except StateKeyNoResult:
            service_account = None  # bold_a = ∅

    preimage_hash = registers[8]  # GP: h (offset to read image hash from pvm mem)
    o = registers[9]  # offset to write image data to in pvm mem

    preimage_writable = True
    preimage_bytes = bytes()  # GP: bold_v
    preimage_hash_unreadable = False
    if not memory.is_accessible(preimage_hash, 32, PVMMemoryMode.readable):
        preimage_hash_unreadable = True  # GP: bold_v = ∇
    elif service_account is None:
        preimage_bytes = None  # GP: bold_v = ∅
    elif service_account is not None:
        try:
            preimage_bytes = services.retrieve_preimage(service_account_id, memory.read_bytes(preimage_hash, 32))
            f = min(registers[10], len(preimage_bytes))
            l = min(registers[11], len(preimage_bytes) - f)
            preimage_writable = memory.is_accessible(o, l, PVMMemoryMode.writable)  # bold_v = ∇
        except StateKeyNoResult:
            preimage_bytes = None  # GP: bold_v = ∅

    if preimage_hash_unreadable is True or preimage_writable is False:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("LOOKUP PANIC", f"s={service_account_id} h={preimage_hash} len(v)=none")
    elif preimage_bytes is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
        logger.hc_log("LOOKUP NONE", f"s={service_account_id} h={preimage_hash} len(v)=none")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(preimage_bytes)
        invocation_output.memory.write_bytes(o, preimage_bytes[f:f + l])
        logger.hc_log("LOOKUP OK",
                           f"s={service_account_id} h={preimage_hash} len(v)={len(preimage_bytes)} write_bytes({o},{o + l})")

def hc_read(
        registers: List[int],
        memory: PVMMemory,
        service: ServiceAccount,
        service_id: int,
        services: ServicesState,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_R) | General host function: read.

    Puts a Service StorageItem blob into PVM memory

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    service: ServiceAccount
    service_id: int
    services: ServicesState
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger.hc_regs(f"READ", "general")
    invocation_output.gas_limit -= 10

    # gp: s*
    if registers[7] == 2 ** 64 - 1:
        new_service_id = service_id
    else:
        new_service_id = registers[7]

    #state = ctx_in.invocation_context.context.state_context
    # gp: bold_a
    try:
        if new_service_id == service_id:
            service_account = service
        else:
            service_account = services.retrieve_service_account(new_service_id)
    except StateKeyNoResult as e:
        service_account = None  # GP: bold_a = ∅

    k_o = registers[8] # offset to read from memory
    k_z = registers[9] # length to read from memory
    o = registers[10]  # offset where to write to in pvm mem

    # GP: bold_v (storage_item)
    storage_key = None
    storage_item_mem_error = False
    storage_item = None  # bold_v
    if service_account is not None:
        try:
            storage_key = memory.read_bytes(k_o, k_z)
            storage_item = services.retrieve_storage_item(service_account_id=new_service_id, storage_item_hash=storage_key)
        except StateKeyNoResult:
            storage_item = None  # bold_v = ∅
        except PVMMemoryError:
            storage_item_mem_error = True  # bold_v = ∇
            storage_item = None

    f = min(registers[11], len(storage_item or bytes()))
    l = min(registers[12], len(storage_item or bytes()) - f)
    mem_writable = memory.is_accessible(o, l, PVMMemoryMode.writable)

    if storage_item_mem_error or not mem_writable:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("READ PANIC", f"s={new_service_id} k={storage_key}")
    elif storage_item is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
        logger.hc_log("READ NONE", f"s={new_service_id} k={storage_key}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(storage_item)
        invocation_output.memory.write_bytes(o, storage_item[f:f + l])
        logger.hc_log("READ OK",
                           f"s={new_service_id} k={storage_key.hex()} (len(storage_item)) write_bytes({o}, {o + l})")


def hc_write(
        registers: List[int],
        memory: PVMMemory,
        service: ServiceAccount,
        service_id: int,
        services: ServicesState,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_W) | General host function: write.

    Writes/deletes a Service StorageItem blob

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    service: ServiceAccount
    service_id: int
    services: ServicesState
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger.hc_regs(f"WRITE", "general")
    invocation_output.gas_limit -= 10

    k_o = registers[7]  # offset to read storage_item_key from memory
    k_z = registers[8]  # length to read storage_item_key from memory
    v_o = registers[9]  # offset to write storage_item_value from memory
    v_z = registers[10] # length to write storage_item_value from memory

    k = None
    l = None
    si = None
    service_account = deepcopy(service)
    storage_key_mem_error = False
    service_storage_item_mem_error = False
    service_storage_item = None

    try:
        k = memory.read_bytes(k_o, k_z)  # GP k: service storage key

        try:
            if v_z == 0:
                service_storage_item = None  # GP: bold_a (delete)
            else:
                service_storage_item = memory.read_bytes(v_o, v_z)  # GP: bold_a
        except PVMMemoryError:
            service_storage_item_mem_error = True  # GP: a = ∇

        try:
            si = services.retrieve_storage_item(service_id, k)
            l = len(si)
        except StateKeyNoResult:
            si = bytes()
            l = HostCallResult.NONE.value

    except PVMMemoryError:
        storage_key_mem_error = True  # GP: k= ∇

    if storage_key_mem_error or service_storage_item_mem_error:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("WRITE PANIC", f"l={l}  s={service_id} mu_k={k}")
    elif service_account.threshold_balance > service_account.balance:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.FULL.value
        logger.hc_log("WRITE FULL", f"l={l}  s={service_id} mu_k={k.hex()}")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = l
        if service_storage_item is None:
            # TODO: mark dirty? maybe register changes
            services.delete_storage_item(
                service_account_id=service_id,
                storage_item_hash=k
            )
            logger.hc_log("WRITE DELETE", f"l={l}  s={service_id} mu_k={k.hex()} si={len(si)} (delete_storage_item)")

            # Update storage footprint
            if l != HostCallResult.NONE.value:
                service_account.update_footprint_remove_storage_item(len(k), len(si))

        else:
            # TODO: mark dirty? maybe register changes
            services.store_storage_item(
                service_account_id=service_id,
                storage_key=k,
                value=service_storage_item,
            )

            # Update storage footprint
            if len(si) == 0:
                # TODO: mark dirty? maybe register changes
                service_account.update_footprint_add_storage_item(len(k), len(service_storage_item))
                logger.hc_log("WRITE NONE",
                                   f"l={l}  s={service_id} mu_k={k.hex()} si=null v={service_storage_item.hex()} (update_footprint_add_storage_item)")
            else:
                # TODO: mark dirty? maybe register changes
                service_account.update_footprint_update_storage_item(len(si), len(service_storage_item))
                logger.hc_log("WRITE OK",
                                   f"l={l}  s={service_id} mu_k={k.hex()} si={len(si)} v={service_storage_item.hex()} (update_footprint_add_storage_item)")

        services.store_service_account(service_id, service_account)

        logger.hc_log("WRITE storage",f"a_o={service_account.footprint_storage_bytes} a_i={service_account.footprint_storage_items}")


def hc_info(
        registers: List[int],
        memory: PVMMemory,
        service: ServiceAccount,
        service_id: int,
        services: ServicesState,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_I) | General host function: info.

    Writes ServiceAccount into PVM memory

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    service: ServiceAccount
    service_id: int
    services: ServicesState
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """
    logger.hc_regs(f"INFO", "general")
    invocation_output.gas_limit -= 10

    #state = ctx_in.invocation_context.context.state_context

    # GP: bold_t
    try:
        if registers[7] == 2 ** 64 - 1:
            # TODO: nieuwe functie: retrieve_service_account_bytes -> nalopen waar allemaal toepassen
            service_account = services.retrieve_service_account(service_id)
        else:
            service_account = services.retrieve_service_account(registers[7])
    except StateKeyNoResult:
        service_account = None  # GP: t = ∅

    o = registers[8]

    service_account_bytes = None  # GP: bold_v
    mem_write_error = False
    if service_account is not None:
        # GP: bold_v
        service_account_bytes = service_account.code_hash
        service_account_bytes += U64.encode(service_account.balance).to_bytes()
        service_account_bytes += U64.encode(service_account.threshold_balance).to_bytes()
        service_account_bytes += U64.encode(service_account.gas_limit_accumulate).to_bytes()
        service_account_bytes += U64.encode(service_account.gas_limit_on_transfer).to_bytes()
        service_account_bytes += U64.encode(service_account.footprint_storage_bytes).to_bytes()
        service_account_bytes += U32.encode(service_account.footprint_storage_items).to_bytes()
        service_account_bytes += U64.encode(service_account.deposit_offset).to_bytes()
        service_account_bytes += U32.encode(service_account.creation_slot).to_bytes()
        service_account_bytes += U32.encode(service_account.last_accumulation_slot).to_bytes()
        service_account_bytes += U32.encode(service_account.parent_service).to_bytes()

        f = min(registers[9], len(service_account_bytes))
        l = min(registers[10], len(service_account_bytes) - f)

        try:
            invocation_output.memory.write_bytes(o, service_account_bytes[f:f+l])
        except PVMMemoryError:
            mem_write_error = True

    if mem_write_error:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
        logger.hc_log("INFO PANIC", f"s={service_id}")
    elif service_account_bytes is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
        logger.hc_log("INFO NONE", f"s={service_id} bytes=none")
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(service_account_bytes)
        logger.hc_log("INFO OK", f"s={service_id} bytes={len(service_account_bytes)}")


def hc_fetch(
        registers: List[int],
        memory: PVMMemory,
        work_package: Optional[WorkPackage],    #GP: p
        entropy: Optional[bytes], # GP: n
        authorizer_output: Optional[bytes], # GP: bold_r
        work_item_index: Optional[int],    #GP: i
        work_item_segs: Optional[List[List[bytes]]], #GP: i_flat
        extrinsics: Optional[List[List[bytes]]], # GP: x_flat
        accumulation_operands: Optional[List[AccumulationOperand]], #GP: bold_o
        deferred_transfers: Optional[List[DeferredTransfer]], # GP: bold_t
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    GP-0.6.7-section:B.6 (Ω_F) | General host function: fetch.

    Fetch the data defined by this Fetch into the given target buffer.
    target: The buffer to write the fetched data into.
    skip: The number of bytes to skip from the start of the data to be fetched.
    Returns the full length of the data which is being fetched. If this is smaller than the target's length, then some of the buffer will not be written to. If the request does not identify any data to be fetched (e.g. because an index is out of range) then returns None.

    Parameters
    ----------
    registers: List[int]
    memory: PVMMemory
    work_package: Optional[WorkPackage]
    entropy: Optional[bytes]
    authorizer_output: Optional[bytes]
    work_item_index: Optional[int]
    work_item_segs: Optional[List[List[bytes]]]
    extrinsics: Optional[List[List[bytes]]]
    accumulation_operands: Optional[List[AccumulationOperand]]
    deferred_transfers: Optional[List[DeferredTransfer]]
    invocation_output: InvocationMutationOutput
    logger: PVMLogger

    Returns
    ----------
    None
    """

    logger.hc_regs(f"FETCH", "general")
    invocation_output.gas_limit -= 10

    w7 = registers[7]
    w8 = registers[8]
    w9 = registers[9]
    w10 = registers[10]
    w11 = registers[11]
    w12 = registers[12]

    def serialize_work_item(work_item: WorkItem) -> bytes:
        return (
            work_item.service.to_bytes(length=4, byteorder='little') + work_item.code_hash +
            work_item.refine_gas_limit.to_bytes(length=8, byteorder='little') +
            work_item.accumulate_gas_limit.to_bytes(length=8, byteorder='little') +
            work_item.export_count.to_bytes(length=2, byteorder='little') +
            len(work_item.import_segments).to_bytes(length=2, byteorder='little') +
            len(work_item.extrinsic).to_bytes(length=2, byteorder='little') +
            len(work_item.payload).to_bytes(length=4, byteorder='little')
        )

    bold_v = None

    if w10 == 0:
        # GP Constants
        const_bytes = (
            U64.encode(gp_const.MINIMUM_BALANCE_ITEM) + U64.encode(gp_const.MINIMUM_BALANCE_OCTET) + U64.encode(gp_const.MINIMUM_BALANCE_SERVICE) + U16.encode(gp_const.CORE_COUNT) + U32.encode(gp_const.PREIMAGE_EXPUNGE_TIMESLOTS) + U32.encode(gp_const.EPOCH_TIMESLOTS) + U64.encode(gp_const.GAS_ACCUMULATION) +
            U64.encode(gp_const.GAS_INVOKE) + U64.encode(gp_const.GAS_REFINE) + U64.encode(gp_const.GAS_TOTAL) + U16.encode(gp_const.HISTORY) + U16.encode(gp_const.MAXIMUM_WORK_ITEMS) + U16.encode(gp_const.MAXIMUM_DEPENDENCIES_WORK_REPORT) + U16.encode(gp_const.MAXIMUM_EXTRINSIC_TICKETS) +
            U32.encode(gp_const.MAXIMUM_AGE_LOOKUP_ANCHOR) + U16.encode(gp_const.TICKET_ENTRIES) + U16.encode(gp_const.MAXIMIM_AUTHORIZATION_POOL_ITEMS) +
            U16.encode(gp_const.SLOT_PERIOD) + U16.encode(gp_const.MAXIMUM_AUTHORIZATION_QUEUE_ITEMS) + U16.encode(gp_const.ROTATION_PERIOD_CORE) + U16.encode(gp_const.MAXIMUM_NUMBER_EXTRINSICS_WORK_PACKAGE) + U16.encode(gp_const.UNAVAILABLE_WORK_REPLACEMENT_PERIOD) +
            U16.encode(gp_const.VALIDATOR_COUNT) + U32.encode(gp_const.MAXIMUM_SIZE_IS_AUTH_CODE) + U32.encode(gp_const.MAXIMUM_SIZE_WORK_PACKAGE) + U32.encode(gp_const.MAXIMUM_SIZE_SERVICE_CODE) + U32.encode(gp_const.SIZE_ERASURE_CODED_PIECES)  + U32.encode(gp_const.MAXIMUM_NUMBER_IMPORTS_WORK_PACKAGE) +
            U32.encode(gp_const.MAXIMUM_SIZE_ENCODED_WORK_PACKAGE) + U32.encode(gp_const.MAXIMUM_SIZE_ENCODED_WORK_REPORT) + U32.encode(gp_const.SIZE_TRANSFER_MEMO) + U32.encode(gp_const.MAXIMUM_NUMBER_EXPORTS_WORK_PACKAGE) + U32.encode(gp_const.TICKET_SUBMISSION_END_SLOT)
        )
        bold_v = const_bytes.to_bytes()

    elif w10 == 1:
        # Entropy
        if entropy is not None:
            bold_v = entropy

    elif w10 == 2:
        # authorizer_output
        if authorizer_output is not None:
            bold_v = authorizer_output

    elif w10 == 3 and w11 < len(extrinsics) and w12 < len(extrinsics[w11]):
        # AnyExtrinsic
        bold_v = extrinsics[w11][w12]

    elif w10 == 4 and w11 < len(extrinsics[work_item_index]):
    # elif w10 == 6 and w11 < len(work_package.items[work_item_index].extrinsic): #TODO polkajam deviation
        # OurExtrinsic
        bold_v = extrinsics[work_item_index][w12]

    elif w10 == 5 and w11 < len(work_item_segs) and w12 < len(work_item_segs[w11]):

        bold_v = work_item_segs[w11][w12]

    elif w10 == 6 and work_item_index < len(work_item_segs) and w11 < len(work_item_segs[work_item_index]):

        bold_v = work_item_segs[work_item_index][w11]

    elif w10 == 7 and work_package is not None:
        bold_v = work_package.to_jam_bytes().to_bytes()

    elif w10 == 8 and work_package is not None:
        bold_v = work_package.authorizer.to_jam_bytes().to_bytes()

    elif w10 == 9 and work_package is not None:
        bold_v = work_package.authorization

    elif w10 == 10 and work_package is not None:
        bold_v = work_package.context.to_jam_bytes().to_bytes() # TODO check again with GP

    elif w10 == 11 and work_package is not None:
        serialized_work_items = [serialize_work_item(w) for w in work_package.items]
        bold_v = VarInt64.encode(len(serialized_work_items)).to_bytes() + b''.join(serialized_work_items)

    elif w10 == 12 and work_package and w11 < len(work_package.items):
        bold_v = serialize_work_item(work_package.items[w11])

    elif w10 == 13 and work_package and w11 < len(work_package.items):
        bold_v = work_package.items[w11].payload

    elif w10 == 14:
        bold_v = Vec(AccumulationOperand.to_codec_def()).encode([a.to_jam_bytes() for a in accumulation_operands]).to_bytes()

    elif w10 == 15 and w11 < len(accumulation_operands):
        bold_v = accumulation_operands[w11].to_jam_bytes().to_bytes()

    elif w10 == 16:
        bold_v = Vec(DeferredTransfer.to_codec_def()).encode(deferred_transfers).to_bytes()

    elif w10 == 17 and w11 < len(deferred_transfers):
        bold_v = deferred_transfers[w11].to_jam_bytes().to_bytes()

    o = w7
    f = min(w8, len(bold_v or []))
    l = min(w9, len(bold_v or []) - f)

    if not memory.is_accessible(o, l, PVMMemoryMode.writable):
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.panic)
    elif bold_v is None:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = HostCallResult.NONE.value
    else:
        invocation_output.exit_condition = ExitCondition(reason=ExitReason.resume)
        invocation_output.registers[7] = len(bold_v)
        invocation_output.memory.write_bytes(o, bold_v[f:f+l])
