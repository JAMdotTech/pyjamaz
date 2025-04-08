from copy import deepcopy
from typing import List

from pyjamaz.exceptions import StateKeyNoResult
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.models.state import ServiceAccount, ServicesState
from pyjamaz.pvm.constants import ExitCondition, ExitReason
from pyjamaz.pvm.exceptions import PVMMemoryError
from pyjamaz.pvm.invocation import InvocationMutationOutput
from pyjamaz.pvm.types import PVMMemoryMode, PVMLogger, PVMMemory
from pyjamaz.pvm_interface.hostcalls.constants import HostCallResult


def hc_gas(
        registers: List[int],   #TODO: weg?
        memory: PVMMemory,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    logger.hc_regs(f"GAS", "accumulate")
    invocation_output.gas_limit -= 10
    invocation_output.registers[7] = invocation_output.gas_limit
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
    Puts a Service Preimage blob into PVM memory
    """
    logger.hc_regs(f"LOOKUP", "accumulate")
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
    Puts a Service StorageItem blob into PVM memory
    """
    logger.hc_regs(f"READ", "accumulate")
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
            new_service_id_bytes = new_service_id.to_bytes(length=4, byteorder="little")
            storage_key = blake2b_256_hash(new_service_id_bytes + memory.read_bytes(k_o, k_z))
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


#TODO: should work without services (bold_d??)
def hc_write(
        registers: List[int],
        memory: PVMMemory,
        service: ServiceAccount,
        service_id: int,
        services: ServicesState,
        invocation_output: InvocationMutationOutput,
        logger: PVMLogger):
    """
    Writes/deletes a Service StorageItem blob
    """
    logger.hc_regs(f"WRITE", "accumulate")
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
        k = memory.read_bytes(k_o, k_z)  # Note: service local storage key
        storage_key = blake2b_256_hash(service_id.to_bytes(length=4, byteorder="little") + k)  # GP: k
        try:
            if v_z == 0:
                service_storage_item = None  # GP: bold_a (delete)
            else:
                service_storage_item = memory.read_bytes(v_o, v_z)  # GP: bold_a
        except PVMMemoryError:
            service_storage_item_mem_error = True  # GP: a = ∇

        try:
            si = services.retrieve_storage_item(service_id, storage_key)
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
                storage_item_hash=storage_key
            )
            logger.hc_log("WRITE DELETE", f"l={l}  s={service_id} mu_k={k.hex()} si={len(si)} (delete_storage_item)")

            # Update storage footprint
            if l != HostCallResult.NONE.value:
                service_account.update_footprint_remove_storage_item(len(si))

        else:
            # TODO: mark dirty? maybe register changes
            services.store_storage_item(
                service_account_id=service_id,
                storage_item_hash=storage_key,
                value=service_storage_item,
            )

            # Update storage footprint
            if len(si) == 0:
                # TODO: mark dirty? maybe register changes
                service_account.update_footprint_add_storage_item(len(service_storage_item))
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
    Writes ServiceAccount into PVM memory
    """
    logger.hc_regs(f"INFO", "accumulate")
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

    service_account_bytes = None  # GP: bold_m
    mem_write_error = False
    if service_account is not None:
        service_account_bytes = service_account.to_serialized_bytes2()  # GP: bold_m
        try:
            invocation_output.memory.write_bytes(o, service_account_bytes)
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
        invocation_output.registers[7] = HostCallResult.OK.value
        logger.hc_log("INFO OK", f"s={service_id} bytes={len(service_account_bytes)}")
